from __future__ import annotations

from pathlib import Path

import pytest

from finances.ledger import LedgerError, Money, StatementError, load_ledger, parse_statement

ROOT = Path(__file__).resolve().parents[1]


def test_missing_accounts_yaml_raises(tmp_path: Path) -> None:
    with pytest.raises(LedgerError, match="missing"):
        load_ledger(tmp_path)


def test_sample_ledger_loads() -> None:
    ledger = load_ledger(ROOT, ROOT / "accounts.sample.yaml")
    assert [account.name for account in ledger.accounts] == ["Example Checking", "Sample Savings"]
    savings = next(account for account in ledger.accounts if account.id == "sample-savings")
    assert savings.kind == "savings"
    assert savings.apr is None
    assert "example-rent" in {str(bill_id) for bill_id in ledger.bills}


def test_missing_csv_raises(tmp_path: Path) -> None:
    yaml_text = """
accounts:
  - id: ghost
    name: Ghost Account
    type: checking
    csv: transactions/missing.csv
"""
    (tmp_path / "accounts.yaml").write_text(yaml_text, encoding="utf-8")
    (tmp_path / "transactions").mkdir()
    with pytest.raises(LedgerError, match="missing CSV"):
        load_ledger(tmp_path)


def test_unclaimed_csv_raises(tmp_path: Path) -> None:
    yaml_text = """
accounts:
  - id: example-checking
    name: Example Checking
    type: checking
    csv: transactions/sample-checking.csv
"""
    tx = tmp_path / "transactions"
    tx.mkdir()
    csv = """# account: Example Checking
# opening_balance: 10.00
# closing_balance: 10.00
date,description,amount,category
"""
    (tx / "sample-checking.csv").write_text(csv, encoding="utf-8")
    (tx / "orphan.csv").write_text(csv.replace("Example Checking", "Orphan"), encoding="utf-8")
    (tmp_path / "accounts.yaml").write_text(yaml_text, encoding="utf-8")
    with pytest.raises(LedgerError, match="unclaimed CSV"):
        load_ledger(tmp_path)


def test_csv_name_mismatch_raises(tmp_path: Path) -> None:
    yaml_text = """
accounts:
  - id: example-checking
    name: Example Checking
    type: checking
    csv: transactions/sample-checking.csv
"""
    tx = tmp_path / "transactions"
    tx.mkdir()
    (tx / "sample-checking.csv").write_text(
        """# account: Not The Name
# opening_balance: 10.00
# closing_balance: 10.00
date,description,amount,category
""",
        encoding="utf-8",
    )
    (tmp_path / "accounts.yaml").write_text(yaml_text, encoding="utf-8")
    with pytest.raises(LedgerError, match="does not match"):
        load_ledger(tmp_path)


def test_unknown_bill_account_raises(tmp_path: Path) -> None:
    yaml_text = """
accounts:
  - id: example-checking
    name: Example Checking
    type: checking
    csv: transactions/sample-checking.csv
bills:
  - id: example-rent
    name: Example Rent
    amount: "100.00"
    account_id: not-a-real-account
"""
    tx = tmp_path / "transactions"
    tx.mkdir()
    (tx / "sample-checking.csv").write_text(
        """# account: Example Checking
# opening_balance: 10.00
# closing_balance: 10.00
date,description,amount,category
""",
        encoding="utf-8",
    )
    (tmp_path / "accounts.yaml").write_text(yaml_text, encoding="utf-8")
    with pytest.raises(LedgerError, match="unknown account"):
        load_ledger(tmp_path)


def test_bad_opening_header_is_statement_error() -> None:
    text = """# account: Example Checking
# opening_balance: 12.345
# closing_balance: 10.00
date,description,amount,category
"""
    with pytest.raises(StatementError, match="whole cents"):
        parse_statement(text)


def test_bad_opening_header_is_ledger_error(tmp_path: Path) -> None:
    yaml_text = """
accounts:
  - id: example-checking
    name: Example Checking
    type: checking
    csv: transactions/sample-checking.csv
"""
    tx = tmp_path / "transactions"
    tx.mkdir()
    (tx / "sample-checking.csv").write_text(
        """# account: Example Checking
# opening_balance: 12.345
# closing_balance: 10.00
date,description,amount,category
""",
        encoding="utf-8",
    )
    (tmp_path / "accounts.yaml").write_text(yaml_text, encoding="utf-8")
    with pytest.raises(LedgerError, match="whole cents"):
        load_ledger(tmp_path)


def test_money_rejects_sub_penny() -> None:
    with pytest.raises(Exception):
        Money.parse("1.234")
