from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from finances.ledger import Bill, BillId, PostingStatus, Statement


@dataclass(frozen=True, slots=True)
class Paid:
    bill: Bill
    description: str


@dataclass(frozen=True, slots=True)
class Unpaid:
    bill: Bill


BillStatus = Paid | Unpaid


@dataclass(frozen=True, slots=True)
class Checklist:
    statuses: tuple[BillStatus, ...]

    @property
    def all_paid(self) -> bool:
        return all(isinstance(status, Paid) for status in self.statuses)


def check_bills(registry: Mapping[BillId, Bill], statements: Mapping[str, Statement]) -> Checklist:
    statuses: list[BillStatus] = []
    for bill in registry.values():
        match = _find_payment(bill, statements)
        if match is None:
            statuses.append(Unpaid(bill))
        else:
            statuses.append(Paid(bill, match))
    return Checklist(tuple(statuses))


def _find_payment(bill: Bill, statements: Mapping[str, Statement]) -> str | None:
    stmt = statements.get(bill.account_id)
    if stmt is None:
        return None
    needle = str(bill.id).lower()
    for posting in stmt.postings:
        if posting.status is not PostingStatus.POSTED:
            continue
        if posting.category.lower() == needle:
            return posting.description
    return None
