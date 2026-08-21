from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import TextIO, assert_never

from finances.bills import check_bills
from finances.csv_import import CsvImportError, import_bank_csv
from finances.ledger import (
    LedgerError,
    Money,
    MoneyError,
    StatementError,
    load_ledger,
    load_statements,
    write_statement,
)
from finances.mercury import (
    BearerToken,
    HttpGet,
    MercuryClient,
    MercuryError,
    MissingTokenError,
    UrllibHttp,
)
from finances.reconcile import reconcile_all
from finances.render import balances_text, checklist_text, reconcile_text


@dataclass(frozen=True, slots=True)
class ImportCsv:
    source: Path
    out: Path
    account: str
    opening: Money
    closing: Money


@dataclass(frozen=True, slots=True)
class Pull:
    account_id: str
    account: str
    since: date
    out: Path
    end: date | None = None


@dataclass(frozen=True, slots=True)
class Reconcile:
    directory: Path


@dataclass(frozen=True, slots=True)
class Bills:
    root: Path


@dataclass(frozen=True, slots=True)
class Verify:
    root: Path


@dataclass(frozen=True, slots=True)
class Balances:
    pass


Command = ImportCsv | Pull | Reconcile | Bills | Verify | Balances


@dataclass(frozen=True, slots=True)
class Check:
    name: str
    ok: bool
    detail: str


def parse_argv(argv: Sequence[str]) -> Command:
    parser = argparse.ArgumentParser(prog="finances", description="Math and gates. No advice.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    import_p = sub.add_parser("import-csv", help="convert a bank export into a reconcile CSV")
    import_p.add_argument("source", type=Path)
    import_p.add_argument("--out", type=Path, required=True)
    import_p.add_argument("--account", required=True)
    import_p.add_argument("--opening", required=True)
    import_p.add_argument("--closing", required=True)

    pull_p = sub.add_parser("pull", help="GET Mercury transactions into a reconcile CSV")
    pull_p.add_argument("--account-id", required=True)
    pull_p.add_argument("--account", required=True)
    pull_p.add_argument("--since", required=True, type=date.fromisoformat)
    pull_p.add_argument("--end", type=date.fromisoformat)
    pull_p.add_argument("--out", type=Path, required=True)

    rec_p = sub.add_parser("reconcile", help="opening plus posted must equal closing")
    rec_p.add_argument("directory", type=Path)

    bills_p = sub.add_parser("bills", help="checklist and paid-state harvest")
    bills_p.add_argument("root", type=Path)

    verify_p = sub.add_parser("verify", help="complete-or-raise plus skill copies")
    verify_p.add_argument("root", type=Path)

    sub.add_parser("balances", help="print posted vs available from Mercury")

    args = parser.parse_args(list(argv))
    cmd = args.cmd
    if cmd == "import-csv":
        return ImportCsv(
            source=args.source,
            out=args.out,
            account=args.account,
            opening=Money.parse(args.opening),
            closing=Money.parse(args.closing),
        )
    if cmd == "pull":
        if args.end is not None and args.end < args.since:
            parser.error("--end must be on or after --since")
        return Pull(
            account_id=args.account_id,
            account=args.account,
            since=args.since,
            out=args.out,
            end=args.end,
        )
    if cmd == "reconcile":
        return Reconcile(directory=args.directory)
    if cmd == "bills":
        return Bills(root=args.root)
    if cmd == "verify":
        return Verify(root=args.root)
    if cmd == "balances":
        return Balances()
    raise AssertionError(cmd)


def verify_repo(root: Path) -> tuple[Check, ...]:
    checks: list[Check] = []
    agents = root / ".agents" / "skills" / "money"
    claude = root / ".claude" / "skills" / "money"
    agents_skill = agents / "SKILL.md"
    claude_skill = claude / "SKILL.md"
    checks.append(Check("agents-skill", agents_skill.is_file(), str(agents_skill)))
    checks.append(Check("claude-skill", claude_skill.is_file(), str(claude_skill)))
    if agents.is_dir() and claude.is_dir():
        drift = _skill_drift(agents, claude)
        checks.append(Check("skill-copies", drift is None, drift or "byte identical"))
    else:
        checks.append(Check("skill-copies", False, "missing skill directory"))
    agents_md = root / "AGENTS.md"
    if agents_md.is_file():
        text = agents_md.read_text(encoding="utf-8")
        names_skill = ".agents/skills/money/SKILL.md" in text
        names_gate = "reconcile" in text.lower() and "stop" in text.lower()
        checks.append(Check("agents-md", names_skill and names_gate, "names skill and hard gate"))
    else:
        checks.append(Check("agents-md", False, "missing AGENTS.md"))
    try:
        ledger = load_ledger(root)
        checks.append(Check("ledger", True, f"{len(ledger.accounts)} accounts"))
    except LedgerError as exc:
        checks.append(Check("ledger", False, str(exc)))
        return tuple(checks)
    statements = tuple(account.statement for account in ledger.accounts if account.statement is not None)
    try:
        report = reconcile_all(statements)
        checks.append(Check("reconcile", report.ok, "transactions/"))
    except StatementError as exc:
        checks.append(Check("reconcile", False, str(exc)))
    return tuple(checks)


def _skill_drift(left: Path, right: Path) -> str | None:
    left_files = {p.relative_to(left): p for p in left.rglob("*") if p.is_file()}
    right_files = {p.relative_to(right): p for p in right.rglob("*") if p.is_file()}
    if left_files.keys() != right_files.keys():
        return "skill file lists differ"
    for rel, left_path in left_files.items():
        if left_path.read_bytes() != right_files[rel].read_bytes():
            return f"skill copy drifted at {rel}"
    return None


def run(
    cmd: Command,
    *,
    env: Mapping[str, str],
    http: HttpGet,
    out: TextIO,
) -> int:
    try:
        return _run(cmd, env=env, http=http, out=out)
    except (MoneyError, MissingTokenError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except (StatementError, CsvImportError, LedgerError, MercuryError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


def _run(cmd: Command, *, env: Mapping[str, str], http: HttpGet, out: TextIO) -> int:
    match cmd:
        case ImportCsv():
            text = cmd.source.read_text(encoding="utf-8")
            stmt = import_bank_csv(text, cmd.account, cmd.opening, cmd.closing)
            write_statement(cmd.out, stmt)
            print(f"wrote {cmd.out}", file=out)
            return 0
        case Pull():
            token = BearerToken.from_env(env)
            client = MercuryClient(http=http, token=token)
            stmt = client.statement(cmd.account_id, cmd.account, cmd.since, cmd.end)
            write_statement(cmd.out, stmt)
            print(f"wrote {cmd.out}", file=out)
            return 0
        case Reconcile():
            report = reconcile_all(load_statements(cmd.directory))
            print(reconcile_text(report), end="", file=out)
            return 0 if report.ok else 1
        case Bills():
            ledger = load_ledger(cmd.root)
            statements = {
                account.id: account.statement
                for account in ledger.accounts
                if account.statement is not None
            }
            print(checklist_text(check_bills(ledger.bills, statements)), end="", file=out)
            return 0
        case Verify():
            checks = verify_repo(cmd.root)
            failed = False
            for check in checks:
                mark = "PASS" if check.ok else "FAIL"
                print(f"{mark}  {check.name}  {check.detail}", file=out)
                if not check.ok:
                    failed = True
            return 1 if failed else 0
        case Balances():
            token = BearerToken.from_env(env)
            client = MercuryClient(http=http, token=token)
            print(balances_text(client.accounts()), end="", file=out)
            return 0
        case _ as unreachable:
            assert_never(unreachable)


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        command = parse_argv(args)
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        if isinstance(code, int):
            return code
        return 2
    except MoneyError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return run(command, env=os.environ, http=UrllibHttp(), out=sys.stdout)


if __name__ == "__main__":
    raise SystemExit(main())
