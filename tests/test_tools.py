from loan_agent.tools import (
    LoanSystem,
    find_duplicate_emi_debits,
    normalize_dob,
)


def verified(loan_id: str, dob: str) -> LoanSystem:
    s = LoanSystem()
    assert s.verify_customer(loan_id, dob) is True
    return s


def test_verify_ok_and_wrong_dob():
    s = LoanSystem()
    assert s.verify_customer("VL1001", "1988-04-12") is True
    assert s.verify_customer("VL1003", "1999-01-01") is False
    assert s.verify_customer("VL9999", "1988-04-12") is False
    assert s.verified == {"VL1001"}


def test_verify_accepts_other_date_formats():
    assert normalize_dob("12/04/1988") == "1988-04-12"
    assert normalize_dob("12-04-1988") == "1988-04-12"
    assert normalize_dob("not a date") is None
    assert LoanSystem().verify_customer("vl1001", "12/04/1988") is True


def test_no_loan_data_before_verification():
    s = LoanSystem()
    for call in (s.get_loan, s.get_payments, s.get_foreclosure_amount, s.get_document_release_status):
        assert call("VL1001")["error"] == "not_verified"
    assert s.raise_refund_ticket("VL1001", ["X"], "dup")["error"] == "not_verified"
    # Verifying a different loan does not unlock this one.
    s.verify_customer("VL1005", "1982-12-03")
    assert s.get_loan("VL1001")["error"] == "not_verified"


def test_customer_a_duplicate_debit_detected():
    s = verified("VL1001", "1988-04-12")
    dups = find_duplicate_emi_debits(s.get_payments("VL1001"))
    assert dups == [["TXN-1001-1105A", "TXN-1001-1105B"]]


def test_no_false_duplicates_for_other_customers():
    for loan_id, dob in [("VL1003", "1985-01-22"), ("VL1005", "1982-12-03")]:
        s = verified(loan_id, dob)
        assert find_duplicate_emi_debits(s.get_payments(loan_id)) == []


def test_refund_ticket_ids_are_deterministic():
    s = verified("VL1001", "1988-04-12")
    assert s.raise_refund_ticket("VL1001", ["TXN-1001-1105B"], "duplicate") == "RF-VL1001-001"
    assert s.raise_refund_ticket("VL1001", ["TXN-1001-1105B"], "duplicate") == "RF-VL1001-002"
    # A fresh conversation starts again from 001.
    s2 = verified("VL1001", "1988-04-12")
    assert s2.raise_refund_ticket("VL1001", ["TXN-1001-1105B"], "duplicate") == "RF-VL1001-001"


def test_customer_c_foreclosure_amount():
    s = verified("VL1003", "1985-01-22")
    out = s.get_foreclosure_amount("VL1003")
    assert out["outstanding_principal"] == 1200000
    assert out["foreclosure_charge"] == 24000  # 2% for fixed rate
    assert out["total_foreclosure_amount"] == 1224000


def test_floating_rate_foreclosure_has_no_charge():
    s = verified("VL1005", "1982-12-03")
    out = s.get_foreclosure_amount("VL1005")
    assert out["foreclosure_charge"] == 0
    assert out["total_foreclosure_amount"] == 3100000


def test_closed_loan_has_no_foreclosure():
    s = verified("VL1002", "1979-09-30")
    assert s.get_foreclosure_amount("VL1002")["error"] == "loan_not_active"


def test_documents_b_ready_d_held():
    b = verified("VL1002", "1979-09-30").get_document_release_status("VL1002")
    assert b["loan_status"] == "closed" and b["status"] == "ready_for_collection"
    d = verified("VL1004", "1990-07-08").get_document_release_status("VL1004")
    assert d["loan_status"] == "active" and d["status"] == "held"
    assert d["outstanding_principal"] == 800000


def test_handoff_works_without_verification():
    s = LoanSystem()
    assert s.create_handoff(None, "fraud", "Caller reports unknown debit.") == "HO-UNKNOWN-001"


def test_every_call_is_logged():
    s = LoanSystem()
    s.verify_customer("VL1003", "1985-01-22")
    s.get_foreclosure_amount("VL1003")
    s.create_handoff("VL1003", "human_requested", "Wants a human.")
    assert [e["tool"] for e in s.log] == ["verify_customer", "get_foreclosure_amount", "create_handoff"]
    assert s.log[1]["inputs"] == {"loan_id": "VL1003"}
    assert s.log[1]["output"]["total_foreclosure_amount"] == 1224000
