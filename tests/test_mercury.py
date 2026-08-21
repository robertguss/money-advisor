from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from finances.ledger import Money, PostingStatus
from finances.mercury import BearerToken, MercuryClient, MissingTokenError
from finances.reconcile import reconcile
from tests.conftest import FakeHttp

FIXTURES = Path(__file__).parent / "fixtures"


def _client() -> tuple[MercuryClient, FakeHttp]:
    http = FakeHttp(
        {
            "/accounts": (FIXTURES / "mercury-accounts.json").read_text(encoding="utf-8"),
            "/transactions": (FIXTURES / "mercury-transactions.json").read_text(encoding="utf-8"),
        }
    )
    client = MercuryClient(http=http, token=BearerToken("secret-token:fake"))
    return client, http


def test_balances_posted_vs_available() -> None:
    client, _ = _client()
    accounts = client.accounts()
    assert len(accounts) == 1
    assert accounts[0].posted == Money.parse("2875.50")
    assert accounts[0].available == Money.parse("2835.50")


def test_pull_derives_opening_and_excludes_unposted() -> None:
    client, http = _client()
    stmt = client.statement(
        "00000000-0000-0000-0000-000000000001",
        "Example Checking",
        date(2026, 8, 1),
    )
    result = reconcile(stmt)
    assert result.ok
    assert stmt.account == "Example Checking"
    assert "xx0000" not in stmt.account
    assert stmt.opening == Money.parse("3000.00")
    assert stmt.closing == Money.parse("2875.50")
    posted = [row for row in stmt.postings if row.status is PostingStatus.POSTED]
    pending = [row for row in stmt.postings if row.status is PostingStatus.PENDING]
    assert {row.description for row in posted} == {"Example Rent", "Corner Market"}
    assert {row.description for row in pending} == {
        "Sample Cafe",
        "Cancelled Wire",
        "Failed ACH",
        "Reversed Check",
        "Blocked Transfer",
        "Unposted Sent",
    }
    assert any("start=2026-08-01" in url for url in http.urls)
    assert all("end=" not in url for url in http.urls if "/transactions" in url)


def test_pull_sends_optional_end() -> None:
    client, http = _client()
    stmt = client.statement(
        "00000000-0000-0000-0000-000000000001",
        "Example Checking",
        date(2026, 8, 1),
        date(2026, 8, 3),
    )
    assert any("start=2026-08-01" in url and "end=2026-08-03" in url for url in http.urls)
    assert {row.description for row in stmt.postings if row.status is PostingStatus.POSTED} == {
        "Example Rent",
        "Corner Market",
    }
    assert all(row.date <= date(2026, 8, 3) for row in stmt.postings)


def test_token_repr_is_redacted() -> None:
    token = BearerToken("secret-token:fake")
    assert "fake" not in repr(token)
    assert "fake" not in str(token)


def test_missing_token_raises() -> None:
    with pytest.raises(MissingTokenError):
        BearerToken.from_env({})
