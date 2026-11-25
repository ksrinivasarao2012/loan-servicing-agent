r"""The agent: a LangGraph flow that handles one customer turn.

    understand -> verify -> escalate --(verified)--> act -> reply
                                     \--(not yet)--------------> reply

- understand: 1 LLM call turns the message into structured requests + flags,
  with keyword rules as a backup for fraud / "I want a human".
- verify:     plain code. Loan data only after verify_customer succeeds;
              two failures -> handoff.
- escalate:   plain code. Fraud, anger, human request, out-of-scope -> create_handoff
              (whether or not identity is verified).
- act:        mode "rules" (agent A): plain code runs each SOP's steps in order.
- reply:      1 LLM call writes the answer from tool outputs + SOP text only.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from . import prompts
from .retrieval import SOPIndex, default_index
from .tools import REFUND_TIMELINE, LoanSystem, find_duplicate_emi_debits, normalize_dob

SOP_INTENTS = ("duplicate_emi_debit", "foreclosure", "property_document_release")
HANDOFF_INTENTS = ("fraud_report", "human_request", "out_of_scope")

# Backup keyword rules (they can only ADD an escalation, never remove one).
FRAUD_RE = re.compile(
    r"\b(fraud\w*|unauthori[sz]ed|not authori[sz]ed|did ?n[o']?t (make|authori[sz]e|do)|"
    r"never (made|authori[sz]ed)|hack(ed)?|scam\w*|stolen)\b", re.I)
HUMAN_RE = re.compile(
    r"\b(human|real person|(talk|speak) to (a |an |some ?one|your )?(person|agent|manager|someone|executive|officer)|"
    r"representative)\b", re.I)
LOAN_ID_RE = re.compile(r"\bVL\d{4}\b", re.I)
DATE_RE = re.compile(r"\b(\d{4}[-/]\d{2}[-/]\d{2}|\d{2}[-/]\d{2}[-/]\d{4})\b")

HANDOFF_REASON = {
    "fraud_report": "fraud_or_unauthorised_transaction",
    "human_request": "customer_asked_for_human",
    "out_of_scope": "no_matching_sop",
    "angry": "very_angry_or_abusive",
    "verification": "verification_failed_twice",
}


# What the customer is told a handoff is about. Internal reason codes stay in
# the logs; they must never appear in a reply (an eval check enforces this).
HANDOFF_ABOUT = {
    "fraud_or_unauthorised_transaction": "your report of a transaction you did not authorise",
    "customer_asked_for_human": "your request to speak with a person",
    "no_matching_sop": "a request our specialist team handles",
    "very_angry_or_abusive": "your complaint",
    "verification_failed_twice": "confirming your identity",
}

# Most serious first: the first reason found becomes the handoff's main reason.
HANDOFF_PRIORITY = [
    "fraud_or_unauthorised_transaction",
    "verification_failed_twice",
    "customer_asked_for_human",
    "very_angry_or_abusive",
    "no_matching_sop",
]


@dataclass
class Session:
    """Everything the agent remembers between turns of one conversation."""
    system: LoanSystem = field(default_factory=LoanSystem)
    history: list[tuple[str, str]] = field(default_factory=list)
    pending: list[dict] = field(default_factory=list)  # SOP requests waiting for verification
    loan_id: str | None = None
    failed_verifications: int = 0
    handoffs_by_reason: dict[str, str] = field(default_factory=dict)


class TurnState(TypedDict, total=False):
    message: str
    understanding: dict
    requests: list[dict]
    sop_requests: list[dict]
    angry: bool
    dob: str | None
    handoffs: list[dict]
    verification: str
    blocked_requests: list[dict]
    results: list[dict]
    retrieval: list[dict]
    reply: str


class Agent:
    def __init__(self, llm, mode: str = "rules", session: Session | None = None,
                 index: SOPIndex | None = None):
        if mode != "rules":
            raise ValueError("Only mode='rules' (agent A) is implemented so far.")
        self.llm = llm
        self.mode = mode
        self.session = session or Session()
        self.index = index or default_index()
        self.graph = self._build()
        self._errors: list[str] = []  # LLM/API errors in the current turn

    # ------------------------------------------------------------------ graph
    def _build(self):
        g = StateGraph(TurnState)
        g.add_node("understand", self.understand)
        g.add_node("escalate", self.escalate)
        g.add_node("verify", self.verify)
        g.add_node("act", self.act)
        g.add_node("reply", self.reply)
        g.set_entry_point("understand")
        # verify runs before escalate so handoff summaries know if identity was confirmed.
        # Escalation never depends on verification: a fraud report from an unverified
        # caller still reaches a human.
        g.add_edge("understand", "verify")
        g.add_edge("verify", "escalate")
        g.add_conditional_edges("escalate", lambda s: "act" if s["verification"] == "ok" else "reply",
                                {"act": "act", "reply": "reply"})
        g.add_edge("act", "reply")
        g.add_edge("reply", END)
        return g.compile()

    def run_turn(self, message: str) -> dict[str, Any]:
        """Handle one customer message. Returns the reply plus a full trace
        of what the agent did (for the UI panel and the evals)."""
        log_start = len(self.session.system.log)
        calls_start = self.llm.calls
        self._errors = []
        out = self.graph.invoke({"message": message})
        self.session.history += [("customer", message), ("agent", out["reply"])]
        return {
            "reply": out["reply"],
            "intents": [r["intent"] for r in out.get("requests", [])]
                       + (["angry"] if out.get("angry") else []),
            "requests": out.get("requests", []),
            "sops_used": [r["sop_id"] for r in out.get("results", [])],
            "retrieval": out.get("retrieval", []),
            "verification": out.get("verification"),
            "tool_calls": self.session.system.log[log_start:],
            "handoffs": out.get("handoffs", []),
            "results": out.get("results", []),
            "llm_calls": self.llm.calls - calls_start,
            "llm_errors": list(self._errors),
        }

    # ------------------------------------------------------------------ nodes
    def understand(self, state: TurnState) -> dict:
        msg = state["message"]
        s = self.session
        history = "\n".join(f"{who}: {text}" for who, text in s.history[-6:]) or "(none)"
        pending = ", ".join(r["intent"] for r in s.pending) or "none"
        try:
            raw = self.llm.json(prompts.UNDERSTAND.format(
                intents="\n".join(f"- {k}: {v}" for k, v in prompts.INTENTS.items()),
                history=history, pending=pending, message=msg))
        except Exception as e:  # bad JSON or API failure -> safest path is a human
            self._errors.append(f"understand: {type(e).__name__}: {str(e)[:150]}")
            raw = {"requests": [{"intent": "out_of_scope", "text": msg}], "error": str(e)}

        requests: list[dict] = []
        seen = set()
        for r in raw.get("requests") or []:
            intent = r.get("intent") if r.get("intent") in prompts.INTENTS else "out_of_scope"
            if intent not in seen:
                seen.add(intent)
                requests.append({"intent": intent, "text": str(r.get("text") or msg)[:200]})

        # Keyword safety net.
        if FRAUD_RE.search(msg) and "fraud_report" not in seen:
            requests.append({"intent": "fraud_report", "text": msg[:200], "source": "rule"})
        if HUMAN_RE.search(msg) and "human_request" not in seen:
            requests.append({"intent": "human_request", "text": msg[:200], "source": "rule"})

        # Identity details: prefer what is literally in the message.
        m = LOAN_ID_RE.search(msg)
        loan_id = (m.group(0) if m else raw.get("loan_id")) or None
        if loan_id:
            s.loan_id = loan_id.upper()
        d = DATE_RE.search(msg)
        dob = normalize_dob(d.group(0)) if d else normalize_dob(raw.get("date_of_birth"))

        sop_requests = [r for r in requests if r["intent"] in SOP_INTENTS]
        if not sop_requests and s.pending:
            sop_requests = s.pending  # e.g. this turn only gave loan ID + DOB

        return {"understanding": raw, "requests": requests, "sop_requests": sop_requests,
                "angry": bool(raw.get("very_angry_or_abusive")), "dob": dob}

    def escalate(self, state: TurnState) -> dict:
        """At most ONE handoff per message: the most serious reason is the main one,
        the others are listed in the summary, so the customer gets one case and one id."""
        reasons = [HANDOFF_REASON[r["intent"]] for r in state["requests"] if r["intent"] in HANDOFF_INTENTS]
        if state.get("angry"):
            reasons.append(HANDOFF_REASON["angry"])
        if state.get("verification") == "failed_twice":
            reasons.append(HANDOFF_REASON["verification"])
        reasons = sorted(set(reasons), key=HANDOFF_PRIORITY.index)
        if not reasons:
            return {"handoffs": []}
        requests = state["requests"] + [r for r in state.get("blocked_requests", [])
                                        if r not in state["requests"]]
        return {"handoffs": [self._handoff(reasons, state["message"], requests)]}

    def verify(self, state: TurnState) -> dict:
        s = self.session
        if not state["sop_requests"]:
            return {"verification": "not_needed"}
        if s.loan_id and s.loan_id in s.system.verified:
            return {"verification": "ok"}
        if s.loan_id and state.get("dob"):
            if s.system.verify_customer(s.loan_id, state["dob"]):
                return {"verification": "ok"}
            s.failed_verifications += 1
            if s.failed_verifications >= 2:
                s.pending = []  # escalate will hand this off
                return {"verification": "failed_twice", "sop_requests": [],
                        "blocked_requests": state["sop_requests"]}
            s.pending = state["sop_requests"]
            return {"verification": "failed_once"}
        s.pending = state["sop_requests"]
        return {"verification": "missing"}

    def act(self, state: TurnState) -> dict:
        loan_id = self.session.loan_id
        results, retrieval = [], []
        for r in state["sop_requests"]:
            hits = self.index.search(r["text"])
            retrieval.append({"intent": r["intent"], "query": r["text"], "top_sop": hits[0].sop_id,
                              "scores": {h.sop_id: round(h.score, 2) for h in hits}})
            result = RUNNERS[r["intent"]](self.session.system, loan_id)
            results.append({"intent": r["intent"], "sop_id": r["intent"], "request": r["text"],
                            "result": result})
        self.session.pending = []
        return {"results": results, "retrieval": retrieval}

    def reply(self, state: TurnState) -> dict:
        results = state.get("results", [])
        handoffs = state.get("handoffs", [])
        v = state.get("verification")
        ask = v in ("missing", "failed_once")

        if not results and not handoffs:
            if v == "missing":
                return {"reply": "I can help with that. To protect your account, please share your "
                                 "loan ID and date of birth first."}
            if v == "failed_once":
                return {"reply": "Sorry, those details did not match our records. Please check "
                                 "your loan ID and date of birth and try again."}
            return {"reply": "Hello! I can help with duplicate EMI debits, foreclosure (early "
                             "closure) amounts and property document release. How can I help?"}

        facts = {
            # Handoffs first: a fraud report must be the first thing the customer reads.
            "handoffs": [{"about": " and ".join(HANDOFF_ABOUT[r] for r in h["reasons"]),
                          "handoff_id": h["handoff_id"],
                          "urgent": "fraud_or_unauthorised_transaction" in h["reasons"]}
                         for h in handoffs],
            "results": for_customer(results),
            "ask_for_identity": ask,
            "identity_check": v,
        }
        sop_ids = sorted({r["sop_id"] for r in results})
        sops = "\n\n".join(self.index.get(i).text for i in sop_ids) or "(none)"
        try:
            text = self.llm.text(prompts.REPLY.format(
                message=state["message"], sops=sops, facts=json.dumps(facts, indent=1, ensure_ascii=False)))
        except Exception as e:
            self._errors.append(f"reply: {type(e).__name__}: {str(e)[:150]}")
            text = ""
        if not text:  # LLM failed: fall back to a plain, fact-only reply
            text = fallback_reply(facts)
        return {"reply": text}

    # ---------------------------------------------------------------- helpers
    def _handoff(self, reasons: list[str], message: str, requests: list[dict]) -> dict:
        s = self.session
        main, also = reasons[0], reasons[1:]
        if main in s.handoffs_by_reason:  # same issue again later: reuse the open case
            return {"reason": main, "reasons": reasons, "handoff_id": s.handoffs_by_reason[main],
                    "reused": True}
        verified = bool(s.loan_id and s.loan_id in s.system.verified)
        handled = [r["intent"] for r in requests if r["intent"] not in HANDOFF_INTENTS] or ["none"]
        summary = (f"Reason: {main}" + (f" (also: {', '.join(also)})" if also else "")
                   + f". Customer said: \"{message[:200]}\".\n"
                   f"Loan ID: {s.loan_id or 'not given'} (identity {'verified' if verified else 'not verified'}). "
                   f"Other requests: {', '.join(handled)}.")
        hid = s.system.create_handoff(s.loan_id, main, summary)
        s.handoffs_by_reason[main] = hid
        return {"reason": main, "reasons": reasons, "handoff_id": hid, "summary": summary}


# ------------------------------------------------------------- formatting
AMOUNT_KEYS = {"loan_amount", "outstanding_principal", "emi_amount", "amount", "refund_amount",
               "foreclosure_charge", "total_foreclosure_amount"}


def inr(n: int | float) -> str:
    """Indian-style rupees: 3100000 -> '₹31,00,000' (groups of 2 after the last 3 digits)."""
    n = int(round(n))
    sign, digits = ("-" if n < 0 else ""), str(abs(n))
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        groups.insert(0, head)
        digits = ",".join(groups) + "," + tail
    return f"{sign}₹{digits}"


def for_customer(value):
    """Copy of tool output with money amounts pre-formatted, so the reply LLM
    copies '₹31,00,000' instead of doing number formatting itself."""
    if isinstance(value, dict):
        return {k: (inr(v) if k in AMOUNT_KEYS and isinstance(v, (int, float)) and not isinstance(v, bool)
                    else for_customer(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [for_customer(v) for v in value]
    return value


# ---------------------------------------------------------------- SOP runners
def run_duplicate_emi_debit(system: LoanSystem, loan_id: str) -> dict:
    payments = system.get_payments(loan_id)
    if isinstance(payments, dict):  # error
        return payments
    groups = find_duplicate_emi_debits(payments)
    if not groups:
        emi = [p for p in payments if p["type"] == "EMI"][-3:]
        return {"duplicate_found": False, "recent_emi_debits": emi}
    group = groups[0]
    first = next(p for p in payments if p["txn_id"] == group[0])
    extra = group[1:]
    ticket = system.raise_refund_ticket(loan_id, extra, f"Duplicate EMI debit on {first['date']}")
    return {"duplicate_found": True, "date": first["date"], "emi_amount": first["amount"],
            "duplicate_txn_ids": group, "refund_txn_ids": extra,
            "refund_amount": first["amount"] * len(extra), "ticket_id": ticket,
            "refund_timeline": REFUND_TIMELINE}


def run_foreclosure(system: LoanSystem, loan_id: str) -> dict:
    return system.get_foreclosure_amount(loan_id)


def run_property_document_release(system: LoanSystem, loan_id: str) -> dict:
    return system.get_document_release_status(loan_id)


RUNNERS = {
    "duplicate_emi_debit": run_duplicate_emi_debit,
    "foreclosure": run_foreclosure,
    "property_document_release": run_property_document_release,
}


def fallback_reply(facts: dict) -> str:
    """Used only if the reply LLM call fails. Plain and fact-only."""
    lines = []
    for r in facts["results"]:
        lines.append(f"{r['intent']}: {json.dumps(r['result'], ensure_ascii=False)}")
    for h in facts["handoffs"]:
        lines.append(f"A specialist will contact you (reference {h['handoff_id']}).")
    if facts["ask_for_identity"]:
        lines.append("Please share your loan ID and date of birth to continue.")
    return " ".join(lines)
