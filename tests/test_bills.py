from __future__ import annotations

from pathlib import Path

from finances.bills import Paid, Unpaid, check_bills
from finances.ledger import Bill, BillId, Money, load_ledger

ROOT = Path(__file__).resolve().parents[1]


def _statements(ledger) -> dict:
    return {
        account.id: account.statement
        for account in ledger.accounts
        if account.statement is not None
    }


def test_example_rent_is_paid_on_sample_checking() -> None:
    ledger = load_ledger(ROOT, ROOT / "accounts.sample.yaml")
    checklist = check_bills(ledger.bills, _statements(ledger))
    assert len(checklist.statuses) == 1
    status = checklist.statuses[0]
    assert isinstance(status, Paid)
    assert str(status.bill.id) == "example-rent"


def test_bill_does_not_match_another_account() -> None:
    ledger = load_ledger(ROOT, ROOT / "accounts.sample.yaml")
    stray = Bill(BillId("example-rent"), "Example Rent", Money.parse("100.00"), "sample-savings")
    checklist = check_bills({stray.id: stray}, _statements(ledger))
    assert isinstance(checklist.statuses[0], Unpaid)
