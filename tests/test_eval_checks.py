"""Tests for the eval scorer itself (a buggy scorer would make the results lie)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evals"))

from run_evals import numbers_in, ungrounded  # noqa: E402


def test_number_normalising():
    assert numbers_in("Rs. 1,224,000 and Rs. 12,24,000") == {"1224000"}
    assert numbers_in("on 05 Nov, 2.0%") == {"5", "2"}


def test_grounded_reply_passes():
    src = ['{"total_foreclosure_amount": 1224000, "foreclosure_charge": 24000}', "2% charge"]
    assert ungrounded("Total is Rs. 1,224,000 including a 2% charge of Rs. 24,000.", src) == []


def test_invented_number_and_ticket_are_caught():
    src = ['"RF-VL1001-001"', '{"amount": 28500}']
    bad = ungrounded("Ticket RF-VL1001-009 for Rs. 28,500, done in 3 days.", src)
    assert bad == ["3", "RF-VL1001-009"]


def test_date_parts_allowed():
    assert ungrounded("Debited on 5 November 2026.", ['{"date": "2026-11-05"}']) == []


def test_internal_code_check():
    from run_evals import CODE_RE
    assert CODE_RE.findall("about the very_angry_or_abusive matter, ticket RF-VL1001-001") == ["very_angry_or_abusive"]


def test_indian_format_is_grounded():
    assert numbers_in("₹31,00,000 and ₹12,24,000") == {"3100000", "1224000"}
    assert ungrounded("Total ₹31,00,000.", ['{"total_foreclosure_amount": 3100000}']) == []


def _trace(reply, reasons):
    return {"reply": reply, "intents": ["fraud_report", "foreclosure"], "sops_used": ["foreclosure"],
            "tool_calls": [], "llm_calls": 2, "retrieval": [],
            "handoffs": [{"handoff_id": "HO-VL1005-001", "reason": reasons[0], "reasons": reasons}]}


def test_fraud_first_check():
    from run_evals import score_case
    case = {"id": "X", "category": "t", "turns": ["m"], "expect": {
        "intents": ["fraud_report", "foreclosure"], "sops": ["foreclosure"], "tools_required": [],
        "tools_forbidden": [], "handoff": True, "reply_must_contain": ["HO-VL1005-001", "3100000"]}}
    fraud = ["fraud_or_unauthorised_transaction"]
    good = score_case(case, [_trace("We flagged your fraud report: HO-VL1005-001. Total ₹31,00,000.", fraud)])
    bad = score_case(case, [_trace("Total ₹31,00,000. Your fraud report: HO-VL1005-001.", fraud)])
    assert good["facts"] and not bad["facts"]
    assert "not mentioned first" in bad["notes"]
