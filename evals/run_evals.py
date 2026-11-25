"""Run the 20 eval conversations against the real agent and score them.

    uv run python evals/run_evals.py                 # provider from .env (LLM_PROVIDER)
    uv run python evals/run_evals.py --provider groq
    uv run python evals/run_evals.py --only C01,C12  # a subset

All checks are deterministic (no LLM judge). They read the tool-call log and replies:
- intent:      detected intents match the expected set
- sop/tools:   right SOPs used, required tools called with key inputs, forbidden tools never called
- escalation:  handed off exactly when expected
- grounded:    every number / ticket id / handoff id in the replies appears in a tool
               output, the SOP text, or the customer's own messages (hallucination check)
- facts:       key facts appear in the final reply (and a fraud handoff comes first)
- clean:       no internal codes (words_with_underscores, e.g. a handoff reason) in any reply
A case passes only if all six pass.

    uv run python evals/run_evals.py --rescore evals/results_run1.json
re-scores saved traces with the current scorer (no LLM calls).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from loan_agent.graph import Agent  # noqa: E402
from loan_agent.llm import make_llm  # noqa: E402
from loan_agent.retrieval import default_index  # noqa: E402

ID_RE = re.compile(r"\b(?:RF|HO|TXN)-[A-Z0-9-]*[A-Z0-9]\b", re.I)
NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
CODE_RE = re.compile(r"\b[a-z]+(?:_[a-z]+)+\b")


# --------------------------------------------------------------- checkers
def numbers_in(text: str) -> set[str]:
    """All numbers in a text, normalised: commas removed, leading zeros and
    trailing '.0' dropped. '1,224,000' -> '1224000', '05' -> '5', '2.0' -> '2'."""
    text = ID_RE.sub(" ", text)  # ids are checked separately
    out = set()
    for raw in NUM_RE.findall(text):
        n = raw.replace(",", "").rstrip(".")
        if "." in n:
            n = n.rstrip("0").rstrip(".")
        n = n.lstrip("0") or "0"
        out.add(n)
    return out


def ids_in(text: str) -> set[str]:
    return {m.upper() for m in ID_RE.findall(text)}


def ungrounded(reply: str, sources: list[str]) -> list[str]:
    """Numbers / ids in the reply that do not appear in any source text."""
    allowed_nums, allowed_ids = set(), set()
    for s in sources:
        allowed_nums |= numbers_in(s)
        # date parts, so '5 November 2026' is fine when the tool said 2026-11-05
        for y, m, d in re.findall(r"(\d{4})-(\d{2})-(\d{2})", s):
            allowed_nums |= {y, m.lstrip("0"), d.lstrip("0")}
        allowed_ids |= ids_in(s)
    bad = sorted(n for n in numbers_in(reply) if n not in allowed_nums)
    bad += sorted(i for i in ids_in(reply) if i not in allowed_ids)
    return bad


def norm(text: str) -> str:
    return re.sub(r"[\s,]", "", text).lower()


def inputs_match(actual: dict, expected: dict) -> bool:
    return all(actual.get(k) == v for k, v in expected.items())


def score_case(case: dict, traces: list[dict]) -> dict:
    exp = case["expect"]
    calls = [c for t in traces for c in t["tool_calls"]]
    got_intents = {i for t in traces for i in t["intents"]}
    want = set(exp["intents"])
    allowed = want | set(exp.get("intents_optional", []))
    intent_ok = want <= got_intents <= allowed

    sops_got = {s for t in traces for s in t["sops_used"]}
    missing = [r["tool"] for r in exp["tools_required"]
               if not any(c["tool"] == r["tool"] and inputs_match(c["inputs"], r["inputs"]) for c in calls)]
    forbidden = sorted({c["tool"] for c in calls if c["tool"] in exp["tools_forbidden"]})
    tools_ok = sops_got == set(exp["sops"]) and not missing and not forbidden

    handed_off = any(t["handoffs"] for t in traces)
    escalation_ok = handed_off == exp["handoff"]

    sources = [json.dumps(c["output"]) + json.dumps(c["inputs"]) for c in calls]
    sources += [s.text for s in default_index().sops] + case["turns"]
    bad = sorted({b for t in traces for b in ungrounded(t["reply"], sources)})
    grounded_ok = not bad

    final = norm(traces[-1]["reply"])
    facts_missing = [f for f in exp["reply_must_contain"] if norm(f) not in final]
    facts_bad = [f for f in exp.get("reply_must_not_contain", []) if norm(f) in final]
    # A fraud report must be the first thing the customer reads (before other facts).
    fraud_ids = [norm(h["handoff_id"]) for t in traces for h in t["handoffs"]
                 if "fraud_or_unauthorised_transaction" in h.get("reasons", [h["reason"]])]
    fraud_late = False
    if fraud_ids and fraud_ids[0] in final:
        pos = final.index(fraud_ids[0])
        others = [norm(f) for f in exp["reply_must_contain"] if norm(f) != fraud_ids[0]]
        fraud_late = any(o in final and final.index(o) < pos for o in others)
    facts_ok = not facts_missing and not facts_bad and not fraud_late

    codes = sorted({c for t in traces for c in CODE_RE.findall(t["reply"])})
    clean_ok = not codes

    retr = [r for t in traces for r in t.get("retrieval", [])]
    notes = []
    errors = [e for t in traces for e in t.get("llm_errors", [])]
    if errors:
        notes.append(f"LLM/API ERROR in {len(errors)} call(s), agent used its safe fallback: {errors[0][:80]}")
    if not intent_ok:
        notes.append(f"intents got {sorted(got_intents)}")
    if sops_got != set(exp["sops"]):
        notes.append(f"sops got {sorted(sops_got)}")
    if missing:
        notes.append(f"missing tools {missing}")
    if forbidden:
        notes.append(f"forbidden tools {forbidden}")
    if not escalation_ok:
        notes.append("handoff " + ("not expected" if handed_off else "missing"))
    if bad:
        notes.append(f"ungrounded {bad}")
    if facts_missing:
        notes.append(f"reply missing {facts_missing}")
    if facts_bad:
        notes.append(f"reply should not have {facts_bad}")
    if fraud_late:
        notes.append("fraud handoff not mentioned first")
    if codes:
        notes.append(f"internal codes in reply {codes}")
    return {
        "id": case["id"], "category": case["category"],
        "intent": intent_ok, "tools": tools_ok, "escalation": escalation_ok,
        "grounded": grounded_ok, "facts": facts_ok, "clean": clean_ok,
        "passed": all([intent_ok, tools_ok, escalation_ok, grounded_ok, facts_ok, clean_ok]),
        "retrieval_hits": sum(r["top_sop"] == r["intent"] for r in retr),
        "retrieval_total": len(retr),
        "llm_calls": sum(t["llm_calls"] for t in traces),
        "llm_errors": len(errors),
        "notes": "; ".join(notes),
    }


# ----------------------------------------------------------------- runner
def run(cases: list[dict], llm, sleep: float) -> list[dict]:
    rows, raw = [], []
    for case in cases:
        agent = Agent(llm)  # fresh conversation + fresh mock system per case
        traces = []
        for msg in case["turns"]:
            try:
                traces.append(agent.run_turn(msg))
            except Exception as e:  # keep failures visible instead of crashing the run
                traces.append({"reply": f"[ERROR] {e}", "intents": [], "sops_used": [],
                               "tool_calls": [], "handoffs": [], "llm_calls": 0, "retrieval": [],
                               "llm_errors": [f"run_turn: {e}"]})
            time.sleep(sleep)
        row = score_case(case, traces)
        rows.append(row)
        raw.append({"case": case["id"], "turns": case["turns"], "traces": traces})
        print(f"{row['id']} {'PASS' if row['passed'] else 'FAIL'} {row['notes']}", flush=True)
    return rows, raw


def pct(rows, key):
    return f"{sum(r[key] for r in rows)}/{len(rows)} ({100 * sum(r[key] for r in rows) / len(rows):.0f}%)"


def to_markdown(rows: list[dict], model: str, title: str = "Eval results", when: str | None = None) -> str:
    mark = lambda b: "✅" if b else "❌"  # noqa: E731
    hits = sum(r["retrieval_hits"] for r in rows)
    total = sum(r["retrieval_total"] for r in rows)
    lines = [
        f"# {title}",
        "",
        f"- Agent: A (rules-first)  ",
        f"- Model: `{model}`  ",
        f"- Run at: {when or datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}  ",
        f"- Cases: {len(rows)}, LLM calls: {sum(r['llm_calls'] for r in rows)} (retries after rate limits included)",
        "",
        "| Metric | Score |",
        "|---|---|",
        f"| Intent accuracy | {pct(rows, 'intent')} |",
        f"| SOP / tool correctness | {pct(rows, 'tools')} |",
        f"| Escalation correctness | {pct(rows, 'escalation')} |",
        f"| No hallucinated numbers/ids | {pct(rows, 'grounded')} |",
        f"| Key facts in reply | {pct(rows, 'facts')} |",
        f"| No internal codes in reply | {pct(rows, 'clean')} |",
        f"| **Cases fully passed** | **{pct(rows, 'passed')}** |",
        f"| BM25 top-1 SOP = intent (info only) | {hits}/{total} |",
        f"| Cases hit by LLM/API errors (info) | {sum(1 for r in rows if r.get('llm_errors'))} |",
        "",
        "| Case | Category | Intent | SOP/tools | Escalation | Grounded | Facts | Clean | Pass | Notes |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(f"| {r['id']} | {r['category']} | {mark(r['intent'])} | {mark(r['tools'])} | "
                     f"{mark(r['escalation'])} | {mark(r['grounded'])} | {mark(r['facts'])} | {mark(r['clean'])} | "
                     f"{mark(r['passed'])} | {r['notes'] or ''} |")
    return "\n".join(lines) + "\n"


def main():
    try:  # Windows consoles can choke on the ✅/❌ marks
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default=None, help="gemini or groq (default: LLM_PROVIDER)")
    ap.add_argument("--only", default=None, help="comma-separated case ids")
    ap.add_argument("--sleep", type=float, default=4.0, help="seconds between turns (free-tier limits)")
    ap.add_argument("--out", default=str(ROOT / "evals" / "results.md"))
    ap.add_argument("--rescore", default=None, help="re-score a saved results .json (no LLM calls)")
    ap.add_argument("--model", default="(see original run)", help="model label for --rescore")
    args = ap.parse_args()

    cases = json.loads((ROOT / "evals" / "cases.json").read_text(encoding="utf-8"))["cases"]
    if args.rescore:
        saved = {r["case"]: r["traces"] for r in json.loads(Path(args.rescore).read_text(encoding="utf-8"))}
        rows = [score_case(c, saved[c["id"]]) for c in cases if c["id"] in saved]
        md = to_markdown(rows, args.model, title=f"Re-score of {Path(args.rescore).name} with current scorer",
                         when="(saved run)")
        print(md)
        return
    if args.only:
        keep = set(args.only.split(","))
        cases = [c for c in cases if c["id"] in keep]
    llm = make_llm(args.provider)
    rows, raw = run(cases, llm, args.sleep)
    md = to_markdown(rows, llm.name)
    Path(args.out).write_text(md, encoding="utf-8")
    Path(args.out).with_suffix(".json").write_text(json.dumps(raw, indent=1), encoding="utf-8")
    print("\n" + md)


if __name__ == "__main__":
    main()
