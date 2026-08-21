from __future__ import annotations

import io
import shutil
from datetime import date
from pathlib import Path

import pytest

from finances.cli import Balances, ImportCsv, Pull, Reconcile, Verify, main, parse_argv, run
from finances.ledger import Money
from tests.conftest import FakeHttp

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_reconcile() -> None:
    cmd = parse_argv(["reconcile", "transactions/"])
    assert isinstance(cmd, Reconcile)


def test_reconcile_sample_data_exits_zero() -> None:
    buf = io.StringIO()
    code = run(Reconcile(ROOT / "transactions"), env={}, http=object(), out=buf)
    assert code == 0
    assert "PASS" in buf.getvalue()
    assert "reconcile ok" in buf.getvalue()


def test_reconcile_unbalanced_exits_one(tmp_path: Path) -> None:
    dest = tmp_path / "broken.csv"
    dest.write_text((FIXTURES / "unbalanced.csv").read_text(encoding="utf-8"), encoding="utf-8")
    buf = io.StringIO()
    code = run(Reconcile(tmp_path), env={}, http=object(), out=buf)
    assert code == 1
    assert "FAIL" in buf.getvalue()


def test_import_csv_command(tmp_path: Path) -> None:
    out = tmp_path / "out.csv"
    buf = io.StringIO()
    code = run(
        ImportCsv(
            source=FIXTURES / "bank-export.csv",
            out=out,
            account="Example Checking",
            opening=Money.parse("3000.00"),
            closing=Money.parse("2875.50"),
        ),
        env={},
        http=object(),
        out=buf,
    )
    assert code == 0
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "# opening_balance: 3000.00" in text
    assert "pending" in text


def test_balances_missing_token() -> None:
    buf = io.StringIO()
    code = run(Balances(), env={}, http=object(), out=buf)
    assert code == 2


def test_pull_mocked(tmp_path: Path) -> None:
    http = FakeHttp(
        {
            "/accounts": (FIXTURES / "mercury-accounts.json").read_text(encoding="utf-8"),
            "/transactions": (FIXTURES / "mercury-transactions.json").read_text(encoding="utf-8"),
        }
    )
    out = tmp_path / "pulled.csv"
    buf = io.StringIO()
    code = run(
        Pull(
            account_id="00000000-0000-0000-0000-000000000001",
            account="Example Checking",
            since=date(2026, 8, 1),
            out=out,
        ),
        env={"MERCURY_API_TOKEN": "secret-token:fake"},
        http=http,
        out=buf,
    )
    assert code == 0
    text = out.read_text(encoding="utf-8")
    assert "secret-token" not in text
    assert "# account: Example Checking" in text
    assert "# opening_balance: 3000.00" in text
    assert "xx0000" not in text
    assert "2875.50" in text
    assert any("start=2026-07-02" in url for url in http.urls)
    rec = io.StringIO()
    assert run(Reconcile(tmp_path), env={}, http=object(), out=rec) == 0


def test_parse_pull_requires_account() -> None:
    with pytest.raises(SystemExit):
        parse_argv(
            [
                "pull",
                "--account-id",
                "00000000-0000-0000-0000-000000000001",
                "--since",
                "2026-08-01",
                "--out",
                "transactions/sample-checking.csv",
            ]
        )


def test_parse_pull_requires_since() -> None:
    with pytest.raises(SystemExit):
        parse_argv(
            [
                "pull",
                "--account",
                "Example Checking",
                "--account-id",
                "00000000-0000-0000-0000-000000000001",
                "--out",
                "transactions/sample-checking.csv",
            ]
        )


def test_parse_pull_keeps_display_name() -> None:
    cmd = parse_argv(
        [
            "pull",
            "--account",
            "Example Checking",
            "--account-id",
            "00000000-0000-0000-0000-000000000001",
            "--since",
            "2026-08-01",
            "--out",
            "transactions/sample-checking.csv",
        ]
    )
    assert isinstance(cmd, Pull)
    assert cmd.account == "Example Checking"
    assert cmd.since == date(2026, 8, 1)
    assert cmd.end is None


def test_parse_pull_optional_end() -> None:
    cmd = parse_argv(
        [
            "pull",
            "--account",
            "Example Checking",
            "--account-id",
            "00000000-0000-0000-0000-000000000001",
            "--since",
            "2026-08-01",
            "--end",
            "2026-08-31",
            "--out",
            "transactions/sample-checking.csv",
        ]
    )
    assert isinstance(cmd, Pull)
    assert cmd.end == date(2026, 8, 31)


def test_main_invalid_opening_exits_two() -> None:
    code = main(
        [
            "import-csv",
            str(FIXTURES / "bank-export.csv"),
            "--out",
            "out.csv",
            "--account",
            "Example Checking",
            "--opening",
            "12.345",
            "--closing",
            "2875.50",
        ]
    )
    assert code == 2


def test_verify_sample_tree(tmp_path: Path) -> None:
    shutil.copy(ROOT / "accounts.sample.yaml", tmp_path / "accounts.yaml")
    shutil.copytree(ROOT / "transactions", tmp_path / "transactions")
    shutil.copytree(ROOT / ".agents", tmp_path / ".agents")
    shutil.copytree(ROOT / ".claude", tmp_path / ".claude")
    shutil.copy(ROOT / "AGENTS.md", tmp_path / "AGENTS.md")
    buf = io.StringIO()
    code = run(Verify(tmp_path), env={}, http=object(), out=buf)
    assert code == 0, buf.getvalue()


def test_verify_bad_opening_records_ledger_fail(tmp_path: Path) -> None:
    shutil.copy(ROOT / "accounts.sample.yaml", tmp_path / "accounts.yaml")
    shutil.copytree(ROOT / "transactions", tmp_path / "transactions")
    shutil.copytree(ROOT / ".agents", tmp_path / ".agents")
    shutil.copytree(ROOT / ".claude", tmp_path / ".claude")
    shutil.copy(ROOT / "AGENTS.md", tmp_path / "AGENTS.md")
    (tmp_path / "transactions" / "sample-checking.csv").write_text(
        """# account: Example Checking
# opening_balance: 12.345
# closing_balance: 2875.50
date,description,amount,category
""",
        encoding="utf-8",
    )
    buf = io.StringIO()
    code = run(Verify(tmp_path), env={}, http=object(), out=buf)
    assert code == 1
    assert "FAIL  ledger" in buf.getvalue()


def test_verify_fails_without_accounts_yaml(tmp_path: Path) -> None:
    shutil.copytree(ROOT / ".agents", tmp_path / ".agents")
    shutil.copytree(ROOT / ".claude", tmp_path / ".claude")
    shutil.copy(ROOT / "AGENTS.md", tmp_path / "AGENTS.md")
    buf = io.StringIO()
    code = run(Verify(tmp_path), env={}, http=object(), out=buf)
    assert code == 1
    assert "FAIL  ledger" in buf.getvalue()


def test_import_missing_file_exits_one(tmp_path: Path) -> None:
    buf = io.StringIO()
    code = run(
        ImportCsv(
            source=tmp_path / "missing.csv",
            out=tmp_path / "out.csv",
            account="Example Checking",
            opening=Money.parse("1.00"),
            closing=Money.parse("1.00"),
        ),
        env={},
        http=object(),
        out=buf,
    )
    assert code == 1
