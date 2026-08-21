from __future__ import annotations

from pathlib import Path

from finances.ledger import Money, PostingStatus, load_statement, parse_statement
from finances.reconcile import reconcile, reconcile_all

FIXTURES = Path(__file__).parent / "fixtures"
ROOT = Path(__file__).resolve().parents[1]


def test_sample_checking_ties_and_excludes_pending() -> None:
    stmt = load_statement(ROOT / "transactions" / "sample-checking.csv")
    result = reconcile(stmt)
    assert result.ok
    assert result.opening == Money.parse("3000.00")
    assert result.closing == Money.parse("2875.50")
    assert result.posted == Money.parse("-124.50")
    assert result.pending_count == 1
    pending = [row for row in stmt.postings if row.status is PostingStatus.PENDING]
    assert len(pending) == 1
    assert pending[0].amount == Money.parse("-40.00")


def test_sample_card_ties() -> None:
    stmt = load_statement(ROOT / "transactions" / "sample-card.csv")
    assert reconcile(stmt).ok


def test_pending_fixture_excluded_from_sum() -> None:
    stmt = load_statement(FIXTURES / "pending-excluded.csv")
    result = reconcile(stmt)
    assert result.ok
    assert result.posted == Money.parse("-10.00")
    assert result.pending_count == 1


def test_unbalanced_fixture_fails() -> None:
    stmt = load_statement(FIXTURES / "unbalanced.csv")
    result = reconcile(stmt)
    assert not result.ok
    assert result.delta == Money.parse("40.00")


def test_directory_fails_when_any_file_breaks() -> None:
    report = reconcile_all(
        [
            parse_statement((ROOT / "transactions" / "sample-card.csv").read_text(encoding="utf-8")),
            load_statement(FIXTURES / "unbalanced.csv"),
        ]
    )
    assert not report.ok


def test_penny_tolerance_allows_one_cent() -> None:
    text = """# account: Penny
# opening_balance: 10.00
# closing_balance: 9.01
date,description,amount,category
2026-08-01,Example Drift,-1.00,misc
"""
    result = reconcile(parse_statement(text))
    assert result.ok
    text_off = text.replace("9.01", "8.98")
    assert not reconcile(parse_statement(text_off)).ok
