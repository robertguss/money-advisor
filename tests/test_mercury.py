from __future__ import annotations

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


def test_pull_uses_independent_opening_and_excludes_pending() -> None:
    client, _ = _client()
    stmt = client.statement(
        "00000000-0000-0000-0000-000000000001",
        Money.parse("3000.00"),
    )
    result = reconcile(stmt)
    assert result.ok
    assert stmt.opening == Money.parse("3000.00")
    assert stmt.closing == Money.parse("2875.50")
    pending = [row for row in stmt.postings if row.status is PostingStatus.PENDING]
    assert len(pending) == 1
    assert pending[0].amount == Money.parse("-40.00")


def test_token_repr_is_redacted() -> None:
    token = BearerToken("secret-token:fake")
    assert "fake" not in repr(token)
    assert "fake" not in str(token)


def test_missing_token_raises() -> None:
    with pytest.raises(MissingTokenError):
        BearerToken.from_env({})
