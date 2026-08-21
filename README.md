# money-advisor

A personal financial advisor you run with the agent you already use. The skill is the advisor. The CLI is the calculator.

Sample data in this repo is invented. Example Checking. Sample Savings. Example Rent. No real money. No live accounts.

## Install

```
git clone https://github.com/robertguss/money-advisor
cd money-advisor
uv sync
```

## First numbers

Copy the sample accounts file and keep the sample CSVs, or replace them with your own.

```
cp accounts.sample.yaml accounts.yaml
```

Two ways to ingest:

1. Drop a bank CSV export, then run `uv run finances import-csv path/to/export.csv --out transactions/checking.csv --account "Example Checking" --opening 3000.00 --closing 2875.50`
2. Set `MERCURY_API_TOKEN` in your environment. Never commit it. Then `uv run finances pull --account "Example Checking" --account-id <id> --since 2026-08-01 --out transactions/checking.csv`

`pull` requires `--since`. Optional `--end` closes the window. `--account`, `--account-id`, and `--out` are required. Opening is derived from live currentBalance minus posted rows, so the first pull does not take `--opening`. `import-csv` still takes `--opening` and `--closing` from the export.

## Reconcile

```
uv run finances reconcile transactions/
```

Posted rows must tie. `opening + posted == closing` within one cent. Pending rows print and stay out of the sum. If this command fails, stop. Do not ask an agent for a plan on numbers that do not tie.

## Point your agent here

Open `AGENTS.md`. The agent loads `.agents/skills/money/SKILL.md` (Claude Code also has `.claude/skills/money/SKILL.md`). That skill writes `snapshot.md` then `plan.md` only after reconcile passes. Then it runs `finances bills` and `finances verify`.

This README is not the skill. The skill is the advisor.

## Privacy

Keep tokens in the environment. Gitignores `transactions/*` except `sample-*.csv`, plus `snapshot.md` and `plan.md`. Write live pulls to a non-sample name such as `transactions/checking.csv`. Do not overwrite the tracked `sample-*.csv` files. The tracked sample CSVs are invented.
