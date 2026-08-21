from __future__ import annotations

from pathlib import Path

from finances.csv_import import import_bank_csv
from finances.ledger import Money, PostingStatus, parse_statement, statement_bytes, write_statement
from finances.reconcile import reconcile

FIXTURES = Path(__file__).parent / "fixtures"


def test_import_bank_export_writes_canonical_csv(tmp_path: Path) -> None:
    source = (FIXTURES / "bank-export.csv").read_text(encoding="utf-8")
    stmt = import_bank_csv(
        source,
        account="Example Checking",
        opening=Money.parse("3000.00"),
        closing=Money.parse("2875.50"),
    )
    dest = tmp_path / "example-checking.csv"
    write_statement(dest, stmt)
    loaded = parse_statement(dest.read_text(encoding="utf-8"))
    result = reconcile(loaded)
    assert result.ok
    pending = [row for row in loaded.postings if row.status is PostingStatus.PENDING]
    assert len(pending) == 1
    assert loaded.posted_total() == Money.parse("-124.50")


def test_import_does_not_invent_opening() -> None:
    source = (FIXTURES / "bank-export.csv").read_text(encoding="utf-8")
    stmt = import_bank_csv(
        source,
        account="Example Checking",
        opening=Money.parse("3000.00"),
        closing=Money.parse("2875.50"),
    )
    assert stmt.opening == Money.parse("3000.00")
    assert stmt.closing == Money.parse("2875.50")
    assert stmt.opening + stmt.posted_total() == stmt.closing


def test_quoted_comma_round_trip() -> None:
    text = """# account: Quoted
# opening_balance: 1.00
# closing_balance: 0.00
date,description,amount,category
2026-08-01,"Foo, Bar",-1.00,misc
"""
    stmt = parse_statement(text)
    assert stmt.postings[0].description == "Foo, Bar"
    again = parse_statement(statement_bytes(stmt).decode("utf-8"))
    assert again == stmt


def test_statement_bytes_round_trip() -> None:
    source = (FIXTURES / "pending-excluded.csv").read_text(encoding="utf-8")
    stmt = parse_statement(source)
    again = parse_statement(statement_bytes(stmt).decode("utf-8"))
    assert again == stmt


def test_import_debit_credit_columns() -> None:
    text = """Date,Payee,Debit,Credit
2026-08-01,Example Rent,100.00,
2026-08-05,Example Payroll,,500.00
"""
    stmt = import_bank_csv(
        text,
        account="Example Checking",
        opening=Money.parse("100.00"),
        closing=Money.parse("500.00"),
    )
    assert stmt.postings[0].amount == Money.parse("-100.00")
    assert stmt.postings[1].amount == Money.parse("500.00")
    assert reconcile(stmt).ok
