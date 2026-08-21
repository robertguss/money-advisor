from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_both_skill_directories_exist() -> None:
    agents = ROOT / ".agents" / "skills" / "money" / "SKILL.md"
    claude = ROOT / ".claude" / "skills" / "money" / "SKILL.md"
    assert agents.is_file()
    assert claude.is_file()


def test_skill_copies_are_byte_identical() -> None:
    agents = ROOT / ".agents" / "skills" / "money"
    claude = ROOT / ".claude" / "skills" / "money"
    left = {p.relative_to(agents): p.read_bytes() for p in agents.rglob("*") if p.is_file()}
    right = {p.relative_to(claude): p.read_bytes() for p in claude.rglob("*") if p.is_file()}
    assert left.keys() == right.keys()
    for rel in left:
        assert left[rel] == right[rel], rel


def test_agents_md_names_skill_and_hard_gate() -> None:
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert ".agents/skills/money/SKILL.md" in text
    assert "reconcile" in text.lower()
    assert "stop" in text.lower()
    assert "snapshot.md" in text
    assert "plan.md" in text


def test_skill_documents_ingest_flags() -> None:
    text = (ROOT / ".agents" / "skills" / "money" / "SKILL.md").read_text(encoding="utf-8")
    assert "--account" in text
    assert "--opening" in text
    assert "--closing" in text
    assert "--account-id" in text
    assert "--since" in text
    assert "--end" in text
    assert "--out" in text
    assert "transactions/sample-checking.csv" in text
    schema = (
        ROOT / ".agents" / "skills" / "money" / "references" / "ledger-schema.md"
    ).read_text(encoding="utf-8")
    assert "Top-level key `bills`" in schema
    assert "Not nested under an account" in schema
