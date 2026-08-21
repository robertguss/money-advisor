# Ledger schema

Two layers. You own `accounts.yaml`. The CLI owns per-account CSVs under `transactions/`.

## accounts.yaml

Hand-edited. Required keys per account:

- `id`. Stable slug. Example: `example-checking`.
- `name`. Display name. Example: `Example Checking`.
- `type`. `checking`, `credit`, `savings`, or `cash`.
- `csv`. Path to that account's reconcile CSV, relative to the workspace root.

Optional keys:

- `apr`. Annual percentage rate as a decimal. Example: `0.2499` for a card.

## Bills

Top-level key `bills`. Not nested under an account. `load_ledger` reads this list from the root of `accounts.yaml`. Nested bills are ignored and the checklist is empty.

Bill object:

- `id`. Stable id. Never reuse. Example: `example-rent`.
- `name`. Display name. Example: `Example Rent`.
- `amount`. Due amount as a decimal string with two places.
- `due_day`. Day of month, 1-28, if the bill is monthly. Omit if irregular.
- `account_id`. The account `id` that pays it.

`finances verify` raises if an account has no CSV, if a CSV header `account` does not match `name`, or if a bill `account_id` is unknown.

## Reconcile CSV

UTF-8. Header comments, then a header row, then data rows.

```
# account: Example Checking
# opening_balance: 3000.00
# closing_balance: 2875.50
date,description,amount,category
2026-08-01,Example Rent,-100.00,example-rent
2026-08-03,Corner Market,-24.50,groceries
2026-08-04,PENDING Sample Cafe,-40.00,pending
```

Rules:

- `opening_balance` and `closing_balance` come from the export or from an independently known posted balance. Do not compute opening as closing minus the sum of rows.
- `amount` is the signed change. Money out is negative. Money in is positive. Credit-card spend is negative on the card CSV.
- A row whose `category` is `pending` is visible and excluded from the posted sum. A `PENDING` prefix on the description is also treated as pending.
- Closing is the posted balance. Pending does not change it.
- Reconcile identity: `opening_balance + sum(posted amounts) == closing_balance` within one cent.

`finances import-csv` and `finances pull` both write this format. `finances reconcile` only reads this format.
