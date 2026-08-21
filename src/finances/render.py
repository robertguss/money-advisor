from __future__ import annotations

from collections.abc import Sequence

from finances.bills import Checklist, Paid
from finances.mercury import MercuryAccount
from finances.reconcile import ReconcileReport


def reconcile_text(report: ReconcileReport) -> str:
    lines: list[str] = []
    for result in report.results:
        mark = "PASS" if result.ok else "FAIL"
        lines.append(
            f"{mark}  {result.account}  opening {result.opening}  "
            f"posted {result.posted}  closing {result.closing}  "
            f"delta {result.delta}  pending {result.pending_count}"
        )
    if report.ok:
        lines.append("reconcile ok")
    else:
        lines.append("reconcile failed")
    return "\n".join(lines) + "\n"


def checklist_text(checklist: Checklist) -> str:
    lines: list[str] = []
    for status in checklist.statuses:
        if isinstance(status, Paid):
            lines.append(f"PAID  {status.bill.id}  {status.bill.name}  {status.description}")
        else:
            lines.append(f"DUE   {status.bill.id}  {status.bill.name}  {status.bill.amount}")
    return "\n".join(lines) + "\n"


def balances_text(accounts: Sequence[MercuryAccount]) -> str:
    lines = ["account  posted  available"]
    for account in accounts:
        lines.append(f"{account.id}  {account.posted}  {account.available}")
    return "\n".join(lines) + "\n"
