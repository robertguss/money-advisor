from __future__ import annotations

from pathlib import Path

from finances.bills import Paid, check_bills
from finances.ledger import load_ledger, load_statement

ROOT = Path(__file__).resolve().parents[1]


def test_example_rent_is_paid_on_sample_checking() -> None:
    ledger = load_ledger(ROOT, ROOT / "accounts.sample.yaml")
    statements = tuple(load_statement(account.statement_path) for account in ledger.accounts)
    checklist = check_bills(ledger.bills, statements)
    assert len(checklist.statuses) == 1
    status = checklist.statuses[0]
    assert isinstance(status, Paid)
    assert str(status.bill.id) == "example-rent"
