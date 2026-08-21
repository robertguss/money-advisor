from __future__ import annotations

import json
import urllib.error
from collections.abc import Mapping
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest

from finances.ledger import Money, PostingStatus
from finances.mercury import (
    CREATED_LOOKBACK_DAYS,
    BearerToken,
    HttpResponse,
    MercuryClient,
    MercuryError,
    MissingTokenError,
    UrllibHttp,
)
from finances.reconcile import reconcile
from tests.conftest import FakeHttp

FIXTURES = Path(__file__).parent / "fixtures"
ACCOUNT_ID = "00000000-0000-0000-0000-000000000001"
ACCOUNTS = (FIXTURES / "mercury-accounts.json").read_text(encoding="utf-8")
SINCE = date(2026, 8, 1)
API_START = (SINCE - timedelta(days=CREATED_LOOKBACK_DAYS)).isoformat()


class OffsetHttp:
    def __init__(self, accounts: str, pages: Mapping[int, str]) -> None:
        self.accounts = accounts
        self.pages = dict(pages)
        self.urls: list[str] = []

    def get(self, url: str, headers: Mapping[str, str]) -> HttpResponse:
        self.urls.append(url)
        if "/transactions" in url:
            offset = int(parse_qs(urlparse(url).query).get("offset", ["0"])[0])
            body = self.pages.get(offset)
            if body is None:
                return HttpResponse(404, "{}")
            return HttpResponse(200, body)
        return HttpResponse(200, self.accounts)


def _page(*txns: dict[str, object], total: int) -> str:
    return json.dumps({"total": total, "transactions": list(txns)})


def _client() -> tuple[MercuryClient, FakeHttp]:
    http = FakeHttp(
        {
            "/accounts": ACCOUNTS,
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
    stmt = client.statement(ACCOUNT_ID, "Example Checking", SINCE)
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
    assert any(f"start={API_START}" in url for url in http.urls)
    assert all("end=" not in url for url in http.urls if "/transactions" in url)


def test_pull_sends_optional_end() -> None:
    client, http = _client()
    stmt = client.statement(ACCOUNT_ID, "Example Checking", SINCE, date(2026, 8, 3))
    assert any(f"start={API_START}" in url and "end=2026-08-03" in url for url in http.urls)
    assert {row.description for row in stmt.postings if row.status is PostingStatus.POSTED} == {
        "Example Rent",
        "Corner Market",
    }
    assert all(row.date <= date(2026, 8, 3) for row in stmt.postings)


def test_truncated_page_raises() -> None:
    http = OffsetHttp(
        ACCOUNTS,
        {
            0: _page(
                {
                    "amount": "-100.00",
                    "status": "sent",
                    "createdAt": "2026-08-01T12:00:00Z",
                    "postedAt": "2026-08-01T12:00:00Z",
                    "counterpartyName": "Example Rent",
                },
                total=2,
            ),
            1: _page(total=2),
        },
    )
    client = MercuryClient(http=http, token=BearerToken("secret-token:fake"))
    with pytest.raises(MercuryError, match="truncated"):
        client.statement(ACCOUNT_ID, "Example Checking", SINCE)


def test_pages_until_total() -> None:
    http = OffsetHttp(
        ACCOUNTS,
        {
            0: _page(
                {
                    "amount": "-100.00",
                    "status": "sent",
                    "createdAt": "2026-08-01T12:00:00Z",
                    "postedAt": "2026-08-01T12:00:00Z",
                    "counterpartyName": "Example Rent",
                },
                total=2,
            ),
            1: _page(
                {
                    "amount": "-24.50",
                    "status": "sent",
                    "createdAt": "2026-08-03T12:00:00Z",
                    "postedAt": "2026-08-03T18:00:00Z",
                    "counterpartyName": "Corner Market",
                },
                total=2,
            ),
        },
    )
    client = MercuryClient(http=http, token=BearerToken("secret-token:fake"))
    stmt = client.statement(ACCOUNT_ID, "Example Checking", SINCE)
    posted = [row for row in stmt.postings if row.status is PostingStatus.POSTED]
    assert {row.description for row in posted} == {"Example Rent", "Corner Market"}
    assert stmt.opening == Money.parse("3000.00")
    assert any("offset=0" in url for url in http.urls)
    assert any("offset=1" in url for url in http.urls)


def test_includes_created_before_since_posted_in_window() -> None:
    http = FakeHttp(
        {
            "/accounts": ACCOUNTS,
            "/transactions": _page(
                {
                    "amount": "-15.00",
                    "status": "sent",
                    "createdAt": "2026-07-25T12:00:00Z",
                    "postedAt": "2026-08-02T09:00:00Z",
                    "counterpartyName": "Slow ACH",
                },
                total=1,
            ),
        }
    )
    client = MercuryClient(http=http, token=BearerToken("secret-token:fake"))
    stmt = client.statement(ACCOUNT_ID, "Example Checking", SINCE)
    posted = [row for row in stmt.postings if row.status is PostingStatus.POSTED]
    assert len(posted) == 1
    assert posted[0].description == "Slow ACH"
    assert posted[0].date == date(2026, 8, 2)
    assert stmt.opening == Money.parse("2890.50")
    assert any(f"start={API_START}" in url for url in http.urls)
    assert API_START < "2026-07-25"


def test_token_repr_is_redacted() -> None:
    token = BearerToken("secret-token:fake")
    assert "fake" not in repr(token)
    assert "fake" not in str(token)


def test_missing_token_raises() -> None:
    with pytest.raises(MissingTokenError):
        BearerToken.from_env({})


def test_pull_rejects_truncated_page() -> None:
    http = FakeHttp(
        {
            "/accounts": (FIXTURES / "mercury-accounts.json").read_text(encoding="utf-8"),
            "/transactions": '{"total":"2","transactions":[]}',
        }
    )
    client = MercuryClient(http=http, token=BearerToken("secret-token:fake"))
    with pytest.raises(MercuryError, match="truncated"):
        client.statement(
            "00000000-0000-0000-0000-000000000001",
            "Example Checking",
            date(2026, 8, 1),
        )


def test_urllib_http_wraps_urlerror() -> None:
    http = UrllibHttp()
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("timed out")):
        with pytest.raises(MercuryError, match="timed out"):
            http.get("https://api.mercury.com/api/v1/accounts", {})
