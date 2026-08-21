from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Protocol
from urllib.parse import urlencode

from finances.ledger import Money, MoneyError, Posting, PostingStatus, Statement, total


class HttpResponse:
    def __init__(self, status: int, body: str) -> None:
        self.status = status
        self.body = body


class HttpGet(Protocol):
    def get(self, url: str, headers: Mapping[str, str]) -> HttpResponse: ...


class UrllibHttp:
    def get(self, url: str, headers: Mapping[str, str]) -> HttpResponse:
        request = urllib.request.Request(url, headers=dict(headers), method="GET")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return HttpResponse(response.status, response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8") if exc.fp else ""
            return HttpResponse(exc.code, body)


class MissingTokenError(Exception):
    pass


class MercuryError(Exception):
    pass


@dataclass(frozen=True)
class BearerToken:
    value: str

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> BearerToken:
        raw = env.get("MERCURY_API_TOKEN", "").strip()
        if raw == "":
            raise MissingTokenError("MERCURY_API_TOKEN is missing")
        return cls(raw)

    def header_value(self) -> str:
        return f"Bearer {self.value}"

    def __repr__(self) -> str:
        return "BearerToken(<redacted>)"

    __str__ = __repr__


@dataclass(frozen=True, slots=True)
class MercuryAccount:
    id: str
    name: str
    kind: str
    posted: Money
    available: Money


@dataclass(frozen=True, slots=True)
class MercuryClient:
    http: HttpGet
    token: BearerToken
    base_url: str = "https://api.mercury.com/api/v1"

    def accounts(self) -> tuple[MercuryAccount, ...]:
        payload = self._get("/accounts")
        return _parse_accounts(payload)

    def statement(
        self,
        account_id: str,
        account_name: str,
        since: date,
        end: date | None = None,
    ) -> Statement:
        accounts = {account.id: account for account in self.accounts()}
        account = accounts.get(account_id)
        if account is None:
            raise MercuryError("account not found")
        params: dict[str, str] = {"start": since.isoformat()}
        if end is not None:
            params["end"] = end.isoformat()
        payload = self._get(f"/account/{account_id}/transactions", params)
        postings = _parse_transactions(payload, since=since, end=end)
        posted_sum = total(p.amount for p in postings if p.status is PostingStatus.POSTED)
        opening = account.posted - posted_sum
        return Statement(account_name, opening, account.posted, postings)

    def _get(self, path: str, params: Mapping[str, str] | None = None) -> object:
        url = self.base_url.rstrip("/") + path
        if params:
            url = f"{url}?{urlencode(params)}"
        response = self.http.get(url, {"Authorization": self.token.header_value(), "Accept": "application/json"})
        if response.status < 200 or response.status >= 300:
            raise MercuryError(f"GET {path} failed with HTTP {response.status}")
        try:
            return json.loads(response.body, parse_float=str, parse_int=str)
        except json.JSONDecodeError as exc:
            raise MercuryError("response was not JSON") from exc


def _parse_accounts(payload: object) -> tuple[MercuryAccount, ...]:
    if not isinstance(payload, dict):
        raise MercuryError("accounts payload must be an object")
    rows = payload.get("accounts")
    if not isinstance(rows, list):
        raise MercuryError("accounts list missing")
    accounts: list[MercuryAccount] = []
    for row in rows:
        if not isinstance(row, dict):
            raise MercuryError("account row must be an object")
        try:
            accounts.append(
                MercuryAccount(
                    id=str(row["id"]),
                    name=str(row["name"]),
                    kind=str(row.get("kind", "")),
                    posted=Money.parse(str(row["currentBalance"])),
                    available=Money.parse(str(row["availableBalance"])),
                )
            )
        except (KeyError, MoneyError) as exc:
            raise MercuryError("account row missing posted or available balance") from exc
    return tuple(accounts)


def _parse_transactions(payload: object, *, since: date, end: date | None) -> tuple[Posting, ...]:
    if not isinstance(payload, dict):
        raise MercuryError("transactions payload must be an object")
    rows = payload.get("transactions")
    if not isinstance(rows, list):
        raise MercuryError("transactions list missing")
    postings: list[Posting] = []
    for row in rows:
        if not isinstance(row, dict):
            raise MercuryError("transaction row must be an object")
        occurred = _row_date(row)
        if not _in_window(occurred, since, end):
            continue
        status = PostingStatus.POSTED if _is_posted(row) else PostingStatus.PENDING
        description = str(
            row.get("counterpartyName")
            or row.get("bankDescription")
            or row.get("externalMemo")
            or "Mercury transfer"
        )
        try:
            amount = Money.parse(str(row["amount"]))
        except (KeyError, MoneyError) as exc:
            raise MercuryError("transaction missing amount") from exc
        category = "pending" if status is PostingStatus.PENDING else str(row.get("mercuryCategory") or "")
        postings.append(Posting(occurred, description, amount, category, status))
    return tuple(postings)


def _is_posted(row: Mapping[str, object]) -> bool:
    status = str(row.get("status") or "").lower()
    return status == "sent" and _posted_at_set(row)


def _posted_at_set(row: Mapping[str, object]) -> bool:
    value = row.get("postedAt")
    if value is None:
        return False
    return str(value).strip() != ""


def _row_date(row: Mapping[str, object]) -> date:
    raw = row.get("postedAt") or row.get("createdAt") or row.get("amountDate") or ""
    return _parse_iso_date(str(raw))


def _in_window(occurred: date, since: date, end: date | None) -> bool:
    if occurred < since:
        return False
    if end is not None and occurred > end:
        return False
    return True


def _parse_iso_date(raw: str) -> date:
    if raw == "":
        raise MercuryError("transaction missing date")
    try:
        return date.fromisoformat(raw[:10])
    except ValueError as exc:
        raise MercuryError(f"bad transaction date {raw!r}") from exc
