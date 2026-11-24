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
    src = ['"RF-HF1001-001"', '{"amount": 28500}']
    bad = ungrounded("Ticket RF-HF1001-009 for Rs. 28,500, done in 3 days.", src)
    assert bad == ["3", "RF-HF1001-009"]


def test_date_parts_allowed():
    assert ungrounded("Debited on 5 November 2026.", ['{"date": "2026-11-05"}']) == []
