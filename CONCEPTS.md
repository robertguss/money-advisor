# Concepts

Reference. Terms this repo uses with one meaning each.

**Advisor.** The money skill. It reads a tying ledger and writes `snapshot.md` then `plan.md`.

**Avalanche.** Extra payments go to the debt with the highest annual percentage rate. Other debts get minimums only.

**Bill id.** Stable identifier in `accounts.yaml`. Paid-state harvest keys off this id. Do not rename it to mark a bill paid.

**CLI.** The `finances` program. Reconcile, import, pull, balances, bills, verify. No advice.

**Closing balance.** Posted balance at the end of the CSV window. Independent of the row sum. Pending does not change it.

**Financial Order of Operations.** Nine-step waterfall for the next dollar. Spine lives in `.agents/skills/money/references/order-of-operations.md`.

**Glass box.** Every number in a snapshot or plan points at a ledger line, a bill id, or a sentence the human wrote. No guesses.

**Ledger.** Hand-owned `accounts.yaml` plus per-account CSVs under `transactions/`.

**Opening balance.** Posted balance at the start of the CSV window. On `import-csv`, taken from `--opening` on the export. On `pull`, derived as live currentBalance minus the posted sum so the written file ties.

**Pending.** A row that is visible and excluded from the posted sum. Marked by a `PENDING` description prefix or `category` equal to `pending`. On `pull`, every Mercury row that is not posted (`sent` with `postedAt` set) is pending, including cancelled, failed, reversed, blocked, and `sent` without `postedAt`.

**Posted.** A settled row. These rows must satisfy `opening + posted == closing` within one cent. On `pull`, posted means Mercury status `sent` and `postedAt` is set.

**Pull.** GET-only adapter. Reads `MERCURY_API_TOKEN` from the environment. Dated window: `--since` required, `--end` optional. Writes a reconcile CSV. Closing is live currentBalance. Opening is currentBalance minus posted sum. Display name comes from `--account`, never Mercury's live `account.name`. `balances` prints account id, not the live name.

**Reconcile.** The gate. `opening_balance + posted amounts == closing_balance` within one cent. Failure stops the advisor.

**Reconcile CSV.** Canonical file format. Header comments for account, opening, and closing. Then `date,description,amount,category`.

**Snapshot.** `snapshot.md`. Where you are. Written only after a passing reconcile.

**Plan.** `plan.md`. What to do next. Written only after a passing reconcile and after the snapshot.

**Verify.** Completeness check. Missing CSVs, mismatched account names, and unknown bill accounts raise.
