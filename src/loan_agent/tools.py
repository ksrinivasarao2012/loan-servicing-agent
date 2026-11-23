"""Mock HomeFirst Loans back-end tools.

Everything here is deterministic (no randomness): the same calls in the same
order always give the same outputs, so tests and evals are repeatable.

Each conversation gets its own `LoanSystem`. It keeps:
- the fake customer data (loaded from data/customers.json),
- which loan ids have passed identity verification in this conversation,
- a log of every tool call (name, inputs, output) for the UI and the evals.
"""

from __future__ import annotations

import copy
import json
from datetime import datetime
from pathlib import Path
from typing import Any

DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "customers.json"

# Foreclosure charge, as written in sops/foreclosure.md:
# fixed-rate: 2% of the amount prepaid (lender policy); floating-rate: 0% (RBI rule).
FORECLOSURE_CHARGE_RATE = {"fixed": 0.02, "floating": 0.0}

REFUND_TIMELINE = "5-7 working days"  # from sops/duplicate_emi_debit.md

_DOB_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d")


def normalize_dob(value: str | None) -> str | None:
    """Turn a date of birth in a few common formats into YYYY-MM-DD."""
    if not value:
        return None
    value = value.strip()
    for fmt in _DOB_FORMATS:
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def load_customers(path: Path = DATA_PATH) -> dict[str, dict]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {c["loan_id"]: c for c in data["customers"]}


NOT_VERIFIED = {"error": "not_verified", "message": "Identity not verified for this loan."}


class LoanSystem:
    """One conversation's view of the mock loan system."""

    def __init__(self, customers: dict[str, dict] | None = None):
        self._customers = copy.deepcopy(customers) if customers else load_customers()
        self.verified: set[str] = set()
        self.log: list[dict[str, Any]] = []
        self._ticket_counter = 0
        self._handoff_counter = 0

    # ---- logging -------------------------------------------------------
    def _record(self, name: str, inputs: dict, output: Any) -> Any:
        self.log.append({"tool": name, "inputs": inputs, "output": copy.deepcopy(output)})
        return output

    def _guard(self, loan_id: str) -> bool:
        """Safety net: loan data is only returned after verification."""
        return loan_id in self.verified

    # ---- tools ---------------------------------------------------------
    def verify_customer(self, loan_id: str, date_of_birth: str) -> bool:
        loan_id = (loan_id or "").strip().upper()
        dob = normalize_dob(date_of_birth)
        cust = self._customers.get(loan_id)
        ok = bool(cust and dob and cust["date_of_birth"] == dob)
        if ok:
            self.verified.add(loan_id)
        return self._record("verify_customer", {"loan_id": loan_id, "date_of_birth": date_of_birth}, ok)

    def get_loan(self, loan_id: str) -> dict:
        inputs = {"loan_id": loan_id}
        if not self._guard(loan_id):
            return self._record("get_loan", inputs, NOT_VERIFIED)
        c = self._customers[loan_id]
        out = {
            k: c[k]
            for k in (
                "name", "loan_id", "loan_amount", "outstanding_principal",
                "emi_amount", "interest_rate", "rate_type", "status",
            )
        }
        if "closure_date" in c:
            out["closure_date"] = c["closure_date"]
        return self._record("get_loan", inputs, out)

    def get_payments(self, loan_id: str) -> list[dict] | dict:
        inputs = {"loan_id": loan_id}
        if not self._guard(loan_id):
            return self._record("get_payments", inputs, NOT_VERIFIED)
        return self._record("get_payments", inputs, self._customers[loan_id]["payment_history"])

    def raise_refund_ticket(self, loan_id: str, transaction_ids: list[str], reason: str) -> str | dict:
        inputs = {"loan_id": loan_id, "transaction_ids": list(transaction_ids), "reason": reason}
        if not self._guard(loan_id):
            return self._record("raise_refund_ticket", inputs, NOT_VERIFIED)
        self._ticket_counter += 1
        ticket = f"RF-{loan_id}-{self._ticket_counter:03d}"
        return self._record("raise_refund_ticket", inputs, ticket)

    def get_foreclosure_amount(self, loan_id: str) -> dict:
        inputs = {"loan_id": loan_id}
        if not self._guard(loan_id):
            return self._record("get_foreclosure_amount", inputs, NOT_VERIFIED)
        c = self._customers[loan_id]
        if c["status"] != "active":
            out = {"error": "loan_not_active", "status": c["status"]}
            return self._record("get_foreclosure_amount", inputs, out)
        rate = FORECLOSURE_CHARGE_RATE[c["rate_type"]]
        principal = c["outstanding_principal"]
        charge = round(principal * rate)
        out = {
            "outstanding_principal": principal,
            "rate_type": c["rate_type"],
            "foreclosure_charge_percent": rate * 100,
            "foreclosure_charge": charge,
            "total_foreclosure_amount": principal + charge,
        }
        return self._record("get_foreclosure_amount", inputs, out)

    def get_document_release_status(self, loan_id: str) -> dict:
        inputs = {"loan_id": loan_id}
        if not self._guard(loan_id):
            return self._record("get_document_release_status", inputs, NOT_VERIFIED)
        c = self._customers[loan_id]
        out = {"loan_status": c["status"], **c["documents"]}
        if c["status"] != "closed":
            out["outstanding_principal"] = c["outstanding_principal"]
        return self._record("get_document_release_status", inputs, out)

    def create_handoff(self, loan_id: str | None, reason: str, summary: str) -> str:
        """Hand off to a human. Allowed without verification (a fraud report
        from an unverified caller still has to reach a human)."""
        self._handoff_counter += 1
        handoff = f"HO-{(loan_id or 'UNKNOWN')}-{self._handoff_counter:03d}"
        return self._record(
            "create_handoff", {"loan_id": loan_id, "reason": reason, "summary": summary}, handoff
        )


def find_duplicate_emi_debits(payments: list[dict]) -> list[list[str]]:
    """Return groups of txn_ids where the same EMI amount was debited more
    than once on the same date (SOP: duplicate_emi_debit.md, step 2)."""
    groups: dict[tuple[str, int], list[str]] = {}
    for p in payments:
        if p.get("type") != "EMI":
            continue
        groups.setdefault((p["date"], p["amount"]), []).append(p["txn_id"])
    return [ids for ids in groups.values() if len(ids) > 1]
