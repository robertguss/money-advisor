from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from finances.ledger import Money, Posting, PostingStatus, Statement


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

    def statement(self, account_id: str, opening: Money, account_name: str | None = None) -> Statement:
        accounts = {account.id: account for account in self.accounts()}
        account = accounts.get(account_id)
        if account is None:
            raise MercuryError("account not found")
        payload = self._get(f"/account/{account_id}/transactions")
        postings = _parse_transactions(payload)
        name = account_name if account_name is not None else account.name
        return Statement(name, opening, account.posted, postings)

    def _get(self, path: str) -> object:
        url = self.base_url.rstrip("/") + path
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


def _parse_transactions(payload: object) -> tuple[Posting, ...]:
    if not isinstance(payload, dict):
        raise MercuryError("transactions payload must be an object")
    rows = payload.get("transactions")
    if not isinstance(rows, list):
        raise MercuryError("transactions list missing")
    postings: list[Posting] = []
    for row in rows:
        if not isinstance(row, dict):
            raise MercuryError("transaction row must be an object")
        status_raw = str(row.get("status", "")).lower()
        status = PostingStatus.PENDING if status_raw == "pending" else PostingStatus.POSTED
        description = str(
            row.get("counterpartyName")
            or row.get("bankDescription")
            or row.get("externalMemo")
            or "Mercury transfer"
        )
        date_raw = str(row.get("postedAt") or row.get("createdAt") or "")
        occurred = _parse_iso_date(date_raw)
        try:
            amount = Money.parse(str(row["amount"]))
        except (KeyError, MoneyError) as exc:
            raise MercuryError("transaction missing amount") from exc
        category = "pending" if status is PostingStatus.PENDING else str(row.get("mercuryCategory") or "")
        postings.append(Posting(occurred, description, amount, category, status))
    return tuple(postings)


def _parse_iso_date(raw: str) -> date:
    if raw == "":
        raise MercuryError("transaction missing date")
    try:
        return date.fromisoformat(raw[:10])
    except ValueError as exc:
        raise MercuryError(f"bad transaction date {raw!r}") from exc
