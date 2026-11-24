"""Agent A flow tests with a scripted fake LLM (no API calls)."""

import json
import re

from loan_agent.graph import Agent
from loan_agent.llm import FakeLLM


def understanding(*intents, angry=False, loan_id=None, dob=None):
    return {"requests": [{"intent": i, "text": i.replace("_", " ")} for i in intents],
            "loan_id": loan_id, "date_of_birth": dob, "very_angry_or_abusive": angry}


def agent_with(script: dict[str, dict]) -> Agent:
    """script maps a phrase in the latest message -> the fake 'understand' output."""
    def json_fn(prompt):
        latest = prompt.rsplit("Latest customer message:", 1)[1]
        for phrase, out in script.items():
            if phrase in latest:
                return out
        return understanding()

    def text_fn(prompt):  # echo the facts so tests can inspect what the reply saw
        return "REPLY " + prompt.split("Facts (JSON):", 1)[1]

    return Agent(FakeLLM(json_fn, text_fn))


def tools(trace):
    return [c["tool"] for c in trace["tool_calls"]]


def test_asks_for_identity_before_any_data():
    a = agent_with({"twice": understanding("duplicate_emi_debit")})
    t = a.run_turn("My EMI was debited twice")
    assert t["verification"] == "missing"
    assert tools(t) == []
    assert "loan ID and date of birth" in t["reply"]
    assert t["llm_calls"] == 1  # template reply, no second LLM call


def test_duplicate_debit_full_flow_across_two_turns():
    a = agent_with({"twice": understanding("duplicate_emi_debit")})
    a.run_turn("My EMI was debited twice")
    t = a.run_turn("HF1001, 12/04/1988")  # second turn: only credentials
    assert tools(t) == ["verify_customer", "get_payments", "raise_refund_ticket"]
    refund = t["tool_calls"][2]
    assert refund["inputs"]["transaction_ids"] == ["TXN-1001-1105B"]
    assert refund["output"] == "RF-HF1001-001"
    assert "RF-HF1001-001" in t["reply"] and "5-7 working days" in t["reply"]
    assert t["sops_used"] == ["duplicate_emi_debit"]
    assert t["retrieval"][0]["intent"] == "duplicate_emi_debit"


def test_multi_intent_in_one_message():
    a = agent_with({"foreclosure": understanding("foreclosure", "property_document_release")})
    t = a.run_turn("HF1003 dob 1985-01-22. What's my foreclosure amount and can I get my documents?")
    assert tools(t) == ["verify_customer", "get_foreclosure_amount", "get_document_release_status"]
    assert t["sops_used"] == ["foreclosure", "property_document_release"]
    assert "1224000" in t["reply"]
    assert t["llm_calls"] == 2


def test_documents_refused_when_loan_not_closed():
    a = agent_with({"documents": understanding("property_document_release")})
    t = a.run_turn("HF1004 08-07-1990 please release my property documents")
    out = t["tool_calls"][-1]["output"]
    assert out["loan_status"] == "active" and out["status"] == "held"
    assert t["handoffs"] == []


def test_fraud_handoff_but_safe_request_still_done():
    a = agent_with({"fraud": understanding("fraud_report", "foreclosure")})
    t = a.run_turn("HF1005 1982-12-03. There is a fraud debit I never made. Also foreclosure amount?")
    assert [h["reason"] for h in t["handoffs"]] == ["fraud_or_unauthorised_transaction"]
    assert "create_handoff" in tools(t) and "get_foreclosure_amount" in tools(t)
    summary = t["tool_calls"][0]["inputs"]["summary"]
    assert 2 <= len(summary.splitlines()) <= 3


def test_keyword_rule_catches_fraud_the_llm_missed():
    a = agent_with({"unauthorised": understanding()})  # LLM returns nothing
    t = a.run_turn("I see an unauthorised transaction on my account")
    assert "fraud_report" in t["intents"]
    assert t["handoffs"][0]["reason"] == "fraud_or_unauthorised_transaction"
    assert "get_loan" not in tools(t) and "get_payments" not in tools(t)


def test_human_request_and_anger():
    a = agent_with({"useless": understanding(angry=True)})
    t = a.run_turn("This is useless, you idiots. Let me speak to a manager!")
    reasons = {h["reason"] for h in t["handoffs"]}
    assert reasons == {"very_angry_or_abusive", "customer_asked_for_human"}


def test_out_of_scope_goes_to_human():
    a = agent_with({"car loan": understanding("out_of_scope")})
    t = a.run_turn("Can I get a car loan?")
    assert t["handoffs"][0]["reason"] == "no_matching_sop"


def test_verification_fails_twice_then_handoff_and_no_data():
    a = agent_with({"foreclosure": understanding("foreclosure")})
    t1 = a.run_turn("HF1003 1999-01-01 foreclosure amount please")
    assert t1["verification"] == "failed_once" and t1["handoffs"] == []
    t2 = a.run_turn("HF1003 1999-02-02")
    assert t2["verification"] == "failed_twice"
    assert t2["handoffs"][0]["reason"] == "verification_failed_twice"
    assert "get_foreclosure_amount" not in tools(t1) + tools(t2)


def test_repeat_escalation_reuses_handoff():
    a = agent_with({"human": understanding("human_request")})
    h1 = a.run_turn("I want a human")["handoffs"][0]["handoff_id"]
    t2 = a.run_turn("I said I want a human")
    assert t2["handoffs"][0]["handoff_id"] == h1
    assert tools(t2) == []  # no second create_handoff


def test_bad_llm_json_falls_back_to_handoff():
    def broken(_):
        raise ValueError("not json")
    a = Agent(FakeLLM(broken))
    t = a.run_turn("asdkjh qwe")
    assert t["handoffs"][0]["reason"] == "no_matching_sop"
