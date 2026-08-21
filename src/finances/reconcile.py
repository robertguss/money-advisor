from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from finances.ledger import PENNY, Money, PostingStatus, Statement


@dataclass(frozen=True, slots=True)
class AccountResult:
    account: str
    opening: Money
    posted: Money
    closing: Money
    delta: Money
    pending_count: int

    @property
    def ok(self) -> bool:
        return abs(self.delta.cents) <= PENNY.cents


@dataclass(frozen=True, slots=True)
class ReconcileReport:
    results: tuple[AccountResult, ...]

    @property
    def ok(self) -> bool:
        return all(result.ok for result in self.results)


def reconcile(stmt: Statement) -> AccountResult:
    posted = stmt.posted_total()
    delta = stmt.opening + posted - stmt.closing
    pending_count = sum(1 for posting in stmt.postings if posting.status is PostingStatus.PENDING)
    return AccountResult(
        account=stmt.account,
        opening=stmt.opening,
        posted=posted,
        closing=stmt.closing,
        delta=delta,
        pending_count=pending_count,
    )


def reconcile_all(stmts: Sequence[Statement]) -> ReconcileReport:
    return ReconcileReport(tuple(reconcile(stmt) for stmt in stmts))
