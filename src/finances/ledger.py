from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import NewType

import yaml


class MoneyError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Money:
    cents: int

    @classmethod
    def parse(cls, text: str) -> Money:
        raw = text.strip()
        if raw == "":
            raise MoneyError("empty money text")
        negative = raw.startswith("-")
        if raw[0] in "+-":
            raw = raw[1:]
        if raw == "" or raw.startswith("-") or raw.startswith("+"):
            raise MoneyError(f"invalid money text: {text!r}")
        if "." in raw:
            whole, frac = raw.split(".", 1)
            if whole == "":
                whole = "0"
            if not whole.isdigit() or not frac.isdigit():
                raise MoneyError(f"invalid money text: {text!r}")
            if len(frac) == 1:
                frac = frac + "0"
            if len(frac) != 2:
                raise MoneyError(f"money must be whole cents: {text!r}")
            cents = int(whole) * 100 + int(frac)
        else:
            if not raw.isdigit():
                raise MoneyError(f"invalid money text: {text!r}")
            cents = int(raw) * 100
        if negative:
            cents = -cents
        return cls(cents)

    def __add__(self, other: Money) -> Money:
        return Money(self.cents + other.cents)

    def __sub__(self, other: Money) -> Money:
        return Money(self.cents - other.cents)

    def __neg__(self) -> Money:
        return Money(-self.cents)

    def __abs__(self) -> Money:
        return Money(abs(self.cents))

    def __lt__(self, other: Money) -> bool:
        return self.cents < other.cents

    def __str__(self) -> str:
        sign = "-" if self.cents < 0 else ""
        amount = abs(self.cents)
        return f"{sign}{amount // 100}.{amount % 100:02d}"


ZERO = Money(0)
PENNY = Money(1)


def total(amounts: Iterable[Money]) -> Money:
    cents = 0
    for amount in amounts:
        cents += amount.cents
    return Money(cents)


class PostingStatus(Enum):
    POSTED = "posted"
    PENDING = "pending"


@dataclass(frozen=True, slots=True)
class Posting:
    date: dt.date
    description: str
    amount: Money
    category: str
    status: PostingStatus


@dataclass(frozen=True, slots=True)
class Statement:
    account: str
    opening: Money
    closing: Money
    postings: tuple[Posting, ...]

    def posted_total(self) -> Money:
        return total(p.amount for p in self.postings if p.status is PostingStatus.POSTED)

    def pending_total(self) -> Money:
        return total(p.amount for p in self.postings if p.status is PostingStatus.PENDING)


class StatementError(ValueError):
    pass


def parse_statement(text: str, source: str = "<memory>") -> Statement:
    lines = text.splitlines()
    account: str | None = None
    opening: Money | None = None
    closing: Money | None = None
    header_index: int | None = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#"):
            body = stripped[1:].strip()
            if ":" not in body:
                continue
            key, value = body.split(":", 1)
            key = key.strip().lower()
            value = value.strip()
            if key == "account":
                account = value
            elif key == "opening_balance":
                opening = Money.parse(value)
            elif key == "closing_balance":
                closing = Money.parse(value)
            continue
        if stripped == "":
            continue
        if stripped.replace(" ", "") == "date,description,amount,category":
            header_index = i
            break
        raise StatementError(f"{source}: expected CSV header, found {stripped!r}")
    if account is None or opening is None or closing is None:
        raise StatementError(
            f"{source}: missing # account, # opening_balance, or # closing_balance"
        )
    if header_index is None:
        raise StatementError(f"{source}: missing date,description,amount,category header")
    postings: list[Posting] = []
    for line in lines[header_index + 1 :]:
        if line.strip() == "":
            continue
        postings.append(_parse_row(line, source))
    return Statement(account, opening, closing, tuple(postings))


def _parse_row(line: str, source: str) -> Posting:
    parts = _split_csv_line(line)
    if len(parts) != 4:
        raise StatementError(f"{source}: expected 4 columns, got {line!r}")
    date_text, description, amount_text, category = parts
    try:
        occurred = dt.date.fromisoformat(date_text)
    except ValueError as exc:
        raise StatementError(f"{source}: bad date {date_text!r}") from exc
    status = PostingStatus.PENDING if _is_pending(description, category) else PostingStatus.POSTED
    stored_category = category
    if status is PostingStatus.PENDING and category.lower() == "pending":
        stored_category = "pending"
    return Posting(occurred, description, Money.parse(amount_text), stored_category, status)


def _is_pending(description: str, category: str) -> bool:
    if category.strip().lower() == "pending":
        return True
    return description.upper().startswith("PENDING")


def _split_csv_line(line: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    in_quotes = False
    i = 0
    while i < len(line):
        ch = line[i]
        if in_quotes:
            if ch == '"':
                if i + 1 < len(line) and line[i + 1] == '"':
                    current.append('"')
                    i += 2
                    continue
                in_quotes = False
                i += 1
                continue
            current.append(ch)
            i += 1
            continue
        if ch == '"':
            in_quotes = True
            i += 1
            continue
        if ch == ",":
            parts.append("".join(current).strip())
            current = []
            i += 1
            continue
        current.append(ch)
        i += 1
    parts.append("".join(current).strip())
    return parts


def statement_bytes(stmt: Statement) -> bytes:
    lines = [
        f"# account: {stmt.account}",
        f"# opening_balance: {stmt.opening}",
        f"# closing_balance: {stmt.closing}",
        "date,description,amount,category",
    ]
    for posting in stmt.postings:
        category = "pending" if posting.status is PostingStatus.PENDING else posting.category
        lines.append(
            ",".join(
                [
                    posting.date.isoformat(),
                    _csv_field(posting.description),
                    str(posting.amount),
                    _csv_field(category),
                ]
            )
        )
    return ("\n".join(lines) + "\n").encode("utf-8")


def _csv_field(value: str) -> str:
    if any(ch in value for ch in ',\"\n'):
        return '"' + value.replace('"', '""') + '"'
    return value


def write_statement(path: Path, stmt: Statement) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = statement_bytes(stmt)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(payload)
    tmp.replace(path)


def load_statement(path: Path) -> Statement:
    return parse_statement(path.read_text(encoding="utf-8"), source=str(path))


def load_statements(directory: Path) -> tuple[Statement, ...]:
    paths = sorted(directory.glob("*.csv"))
    if not paths:
        raise StatementError(f"{directory}: no CSV files")
    return tuple(load_statement(path) for path in paths)


BillId = NewType("BillId", str)


@dataclass(frozen=True, slots=True)
class Bill:
    id: BillId
    name: str
    amount: Money
    account_id: str


@dataclass(frozen=True, slots=True)
class Account:
    id: str
    name: str
    kind: str
    statement_path: Path
    apr: str | None


@dataclass(frozen=True, slots=True)
class Ledger:
    root: Path
    accounts: tuple[Account, ...]
    bills: Mapping[BillId, Bill]


class LedgerError(ValueError):
    pass


def load_ledger(root: Path, accounts_path: Path | None = None) -> Ledger:
    root = root.resolve()
    path = accounts_path if accounts_path is not None else root / "accounts.yaml"
    if not path.exists():
        sample = root / "accounts.sample.yaml"
        if sample.exists():
            path = sample
        else:
            raise LedgerError(f"missing {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise LedgerError(f"{path}: expected a mapping")
    problems: list[str] = []
    accounts: list[Account] = []
    claimed: set[Path] = set()
    seen_ids: set[str] = set()
    for item in raw.get("accounts") or []:
        if not isinstance(item, dict):
            problems.append("account entry is not a mapping")
            continue
        missing = [key for key in ("id", "name", "type", "csv") if not item.get(key)]
        if missing:
            problems.append(f"account missing {', '.join(missing)}")
            continue
        account_id = str(item["id"])
        if account_id in seen_ids:
            problems.append(f"duplicate account id {account_id}")
            continue
        seen_ids.add(account_id)
        csv_path = (root / str(item["csv"])).resolve()
        accounts.append(
            Account(
                id=account_id,
                name=str(item["name"]),
                kind=str(item["type"]),
                statement_path=csv_path,
                apr=str(item["apr"]) if item.get("apr") is not None else None,
            )
        )
        claimed.add(csv_path)
        if not csv_path.exists():
            problems.append(f"missing CSV for {item['name']}: {item['csv']}")
        else:
            try:
                stmt = load_statement(csv_path)
            except StatementError as exc:
                problems.append(str(exc))
            else:
                if stmt.account != str(item["name"]):
                    problems.append(
                        f"CSV account {stmt.account!r} does not match {item['name']!r}"
                    )
    bills: dict[BillId, Bill] = {}
    for item in raw.get("bills") or []:
        if not isinstance(item, dict):
            problems.append("bill entry is not a mapping")
            continue
        missing = [key for key in ("id", "name", "amount", "account_id") if key not in item]
        if missing:
            problems.append(f"bill missing {', '.join(missing)}")
            continue
        bill_id = BillId(str(item["id"]))
        if bill_id in bills:
            problems.append(f"duplicate bill id {bill_id}")
            continue
        account_id = str(item["account_id"])
        if account_id not in seen_ids:
            problems.append(f"bill {bill_id} points at unknown account {account_id}")
        try:
            amount = Money.parse(str(item["amount"]))
        except MoneyError as exc:
            problems.append(f"bill {bill_id}: {exc}")
            continue
        bills[bill_id] = Bill(bill_id, str(item["name"]), amount, account_id)
    tx_dir = root / "transactions"
    if tx_dir.is_dir():
        for csv_path in sorted(tx_dir.glob("*.csv")):
            if csv_path.resolve() not in claimed:
                problems.append(f"unclaimed CSV {csv_path.relative_to(root)}")
    if problems:
        raise LedgerError("; ".join(problems))
    return Ledger(root, tuple(accounts), bills)


def require_complete(root: Path) -> Ledger:
    return load_ledger(root)
