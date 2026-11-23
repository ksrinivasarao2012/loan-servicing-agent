import pytest

from loan_agent.retrieval import default_index

CASES = [
    ("my EMI was debited twice this month", "duplicate_emi_debit"),
    ("I was double charged for the instalment", "duplicate_emi_debit"),
    ("how much do I need to pay to close my loan early", "foreclosure"),
    ("what is my foreclosure amount", "foreclosure"),
    ("please release my property documents", "property_document_release"),
    ("I want my original sale deed back", "property_document_release"),
]


@pytest.mark.parametrize("query,expected", CASES)
def test_top_hit(query, expected):
    hits = default_index().search(query)
    assert hits[0].sop_id == expected, [(h.sop_id, round(h.score, 2)) for h in hits]


def test_all_three_sops_loaded():
    ids = {s.sop_id for s in default_index().sops}
    assert ids == {"duplicate_emi_debit", "foreclosure", "property_document_release"}
