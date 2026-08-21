# Agent instructions

Load `.agents/skills/money/SKILL.md` before you advise on money. If you are Claude Code, `.claude/skills/money/SKILL.md` is the same skill. Do not improvise a process.

The `finances` CLI is math. The skill is the advisor. The CLI never writes a plan. You write `snapshot.md` and `plan.md` only after the ledger ties.

## Hard gate

Run this first:

```
uv run finances reconcile transactions/
```

If that command fails, stop. Do not write `snapshot.md`. Do not write `plan.md`. Show the CLI output to the human. Numbers that do not tie are not advice.

## After a passing reconcile

1. Follow the money skill. Run the Financial Order of Operations analysis.
2. Write `snapshot.md` (where you are).
3. Write `plan.md` (what to do next).
4. Run `uv run finances bills .`
5. Run `uv run finances verify .`

## Language

Write in plain language. If you use an abbreviation, expand it on first use. Financial Order of Operations is the waterfall for the next dollar. Annual percentage rate is the yearly interest on a debt. Posted means the bank has settled the row. Pending means it is visible and excluded from the reconcile sum.

Never print `MERCURY_API_TOKEN`. Never commit it. Never copy facts from someone else's real accounts.
