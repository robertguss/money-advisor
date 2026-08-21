---
name: money
description: Personal financial advisor that runs the Financial Order of Operations on a local ledger. Use whenever the user wants money advice, a snapshot, a plan, a budget check, debt payoff order, or help with accounts.yaml and transaction CSVs. Load this skill before advising. Stop if reconcile fails.
---

# Money advisor

This skill is the advisor. The `finances` CLI is the calculator. Do not give advice from numbers that do not tie.

Educational tool. Not a licensed certified financial planner. Not personalized professional advice.

## Prime directive

Glass box. Never guess.

If a number is missing, ask or stop. If two numbers disagree, say so. Do not invent an opening balance to force a reconcile. Do not pad a CSV. Do not treat pending rows as posted cash.

## Process

1. Preflight. Confirm `accounts.yaml` exists. Confirm transaction CSVs exist under `transactions/`. Confirm you will write `snapshot.md` then `plan.md` only after a passing reconcile.
2. Reconcile hard gate. Run `uv run finances reconcile transactions/`. If it fails, stop. Do not write `snapshot.md`. Do not write `plan.md`. Tell the human the ledger does not tie and what the CLI printed.
3. Snapshot. If reconcile passed, write `snapshot.md`. Describe where the money is. Use only ledger facts plus what the human stated. Flag unknowns.
4. Plan. Write `plan.md`. Follow the Financial Order of Operations below. One next action at a time. Highest unfinished step first.
5. Bills. Run `uv run finances bills .` and record paid versus due by stable id.
6. Verify. Run `uv run finances verify .` and fix anything it raises.

Read `references/ledger-schema.md` before you edit accounts or CSVs. Read `references/order-of-operations.md` before you write the plan.

## Financial Order of Operations

Work the waterfall in order. Do not skip ahead because a later step looks more interesting. Use avalanche for high-APR debt. Highest rate first. Minimums on the rest.

1. Starter cash. Enough cash to cover a typical deductible or a small shock without a card. Generic target. Highest insurance deductible, or $1,000 if deductibles are unknown.
2. Employer match. Contribute enough to capture the full match. That match is part of compensation. Leaving it unused is a pay cut.
3. High-interest debt. Avalanche. Treat revolving consumer debt and teaser-rate cards as high interest even when the current rate looks low. A common cutoff for "high" is about 7 to 8 percent APR. State the cutoff you used.
4. Emergency reserve. Three to six months of essential expenses in cash or cash-like accounts. Essentials means housing, food, utilities, insurance, transport, and minimum debt payments.
5. Tax-advantaged accounts. Roth or traditional IRA, then HSA if the human has a high-deductible plan and is eligible.
6. Max employer plans. Raise workplace retirement contributions toward the annual limit after the match is already captured.
7. Hyper-accumulation. Aim for about 25 percent of gross income toward retirement across all accounts.
8. Prepay future expenses. Known large outlays with a date. Education, a home down payment, a planned move. Not lifestyle creep.
9. Prepay low-interest debt. Mortgage or other cheap installment debt only after the earlier steps are funded.

If the human is self-employed, step 2 may not apply. Say that and move to step 3. If a step does not apply, write "not applicable" and why, then continue.

## Snapshot rules

`snapshot.md` is where you are. Not what to do next.

Include:

- Posted balances per account from the ledger
- Pending rows listed and excluded from the tie
- High-APR balances if the human provided them
- Cash versus debt versus invested, only when the files support it
- The first unfinished FOO step as a one-line status, not a plan

Do not include account numbers, last fours, tokens, or machine paths.

## Plan rules

`plan.md` is what to do next.

Include:

- The current FOO step
- The dollar action this week or this month
- The avalanche target if step 3 is active
- What would make the next step eligible

One primary action. Optional backup if income is uncertain. No product pitches. No live-account names from someone else's life.

## First run

If `accounts.yaml` is missing, copy `.agents/skills/money/templates/accounts.yaml` to the workspace root and ask the human to fill balances. Sample names in this repo are invented. Example Checking. Sample Savings. Example Rent.

Ingest paths:

- Drop a bank export and run `uv run finances import-csv <export> --out transactions/sample-checking.csv --account "Example Checking" --opening 3000.00 --closing 2875.50`
- Or set `MERCURY_API_TOKEN` in the environment and run `uv run finances pull --account "Example Checking" --account-id <id> --since 2026-08-01 --out transactions/sample-checking.csv`

`pull` requires `--since`. Optional `--end YYYY-MM-DD` closes the window. `--account`, `--account-id`, and `--out` are required. Opening is derived as live currentBalance minus posted sum (`sent` with `postedAt` set). First pull does not take `--opening`. `import-csv` still takes `--opening` and `--closing` from the export. Then run `uv run finances reconcile transactions/`. Never commit the token. Never print the token. Live CSVs under `transactions/` are gitignored except `sample-*.csv`.
