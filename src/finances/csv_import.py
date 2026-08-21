from __future__ import annotations

import csv
import io
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, date

from finances.ledger import Money, MoneyError, Posting, PostingStatus, Statement


class CsvImportError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ColumnMap:
    date: str
    description: str
    amount: str | None
    debit: str | None
    credit: str | None
    status: str | None
    category: str | None


_DATE_ALIASES = ("date", "posted date", "transaction date", "posted")
_DESC_ALIASES = ("description", "payee", "memo", "name", "details")
_AMOUNT_ALIASES = ("amount", "amt")
_DEBIT_ALIASES = ("debit", "withdrawal", "out")
_CREDIT_ALIASES = ("credit", "deposit", "in")
_STATUS_ALIASES = ("status", "type", "state")
_CATEGORY_ALIASES = ("category", "categories")


def sniff_columns(header: Sequence[str]) -> ColumnMap:
    lookup = {name.strip().lower(): name for name in header}

    def pick(aliases: Sequence[str]) -> str | None:
        for alias in aliases:
            if alias in lookup:
                return lookup[alias]
        return None

    date_col = pick(_DATE_ALIASES)
    desc_col = pick(_DESC_ALIASES)
    if date_col is None or desc_col is None:
        raise CsvImportError("export needs a date column and a description column")
    return ColumnMap(
        date=date_col,
        description=desc_col,
        amount=pick(_AMOUNT_ALIASES),
        debit=pick(_DEBIT_ALIASES),
        credit=pick(_CREDIT_ALIASES),
        status=pick(_STATUS_ALIASES),
        category=pick(_CATEGORY_ALIASES),
    )


def import_bank_csv(text: str, account: str, opening: Money, closing: Money) -> Statement:
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise CsvImportError("export has no header row")
    columns = sniff_columns(reader.fieldnames)
    if columns.amount is None and (columns.debit is None or columns.credit is None):
        raise CsvImportError("export needs an amount column or debit and credit columns")
    postings: list[Posting] = []
    for row in reader:
        if not any((value or "").strip() for value in row.values()):
            continue
        try:
            occurred = _parse_date(row[columns.date])
        except (KeyError, ValueError) as exc:
            raise CsvImportError("bad date in export") from exc
        description = (row.get(columns.description) or "").strip() or "imported"
        try:
            amount = _row_amount(row, columns)
        except (KeyError, MoneyError, CsvImportError) as exc:
            raise CsvImportError("bad amount in export") from exc
        status_raw = (row.get(columns.status) or "").strip() if columns.status else ""
        category_raw = (row.get(columns.category) or "").strip() if columns.category else ""
        pending = _pending_marker(description, status_raw, category_raw)
        category = "pending" if pending else (category_raw or "")
        status = PostingStatus.PENDING if pending else PostingStatus.POSTED
        postings.append(Posting(occurred, description, amount, category, status))
    return Statement(account, opening, closing, tuple(postings))


def _pending_marker(description: str, status: str, category: str) -> bool:
    if category.lower() == "pending":
        return True
    if status.lower() == "pending":
        return True
    return description.upper().startswith("PENDING")


def _row_amount(row: dict[str, str | None], columns: ColumnMap) -> Money:
    if columns.amount is not None:
        raw = (row.get(columns.amount) or "").strip()
        if raw == "":
            raise CsvImportError("empty amount")
        return Money.parse(_normalize_amount(raw))
    debit = (row.get(columns.debit or "") or "").strip()
    credit = (row.get(columns.credit or "") or "").strip()
    if debit and credit:
        raise CsvImportError("row has both debit and credit")
    if debit:
        return -Money.parse(_normalize_amount(debit))
    if credit:
        return Money.parse(_normalize_amount(credit))
    raise CsvImportError("row has no amount")


def _normalize_amount(raw: str) -> str:
    cleaned = raw.replace("$", "").replace(",", "").strip()
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = "-" + cleaned[1:-1]
    return cleaned


def _parse_date(raw: str) -> date:
    text = raw.strip()
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        pass
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(text)
