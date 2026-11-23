# Order Orchestrator Repair Task

Repair the production code in `order_engine/` so the project satisfies all requirements below.

## Required workflow

1. Inspect the project and run the test suite before editing.
2. Record the initial failing test names in `AGENT_REPORT.md`.
3. Modify production code only. Do not edit `TASK.md`, `tests/`, or `acceptance_check.py`.
4. Re-run the full test suite after each logical fix until all 12 tests pass.
5. Run `python3 acceptance_check.py` and require `ACCEPTANCE_PASS`.
6. Write `result.json` and finish `AGENT_REPORT.md` with root causes, changed files, and verification commands.

Use these commands from `/workspace/order-orchestrator`:

```bash
python3 -m unittest discover -s tests -v
python3 acceptance_check.py
```

## Business rules

- Monetary input must be converted through `Decimal(str(value))`.
- Every public monetary result is rounded to two decimals with `ROUND_HALF_UP`.
- Supported customer tiers are `standard` (0%), `vip` (10%), and `premium` (15%). Unknown tiers raise `ValueError`.
- Discount is calculated from the rounded subtotal. Tax is calculated from the subtotal after discount. Total is discounted subtotal plus tax.
- Every line quantity must be a positive integer.
- Duplicate SKUs are allowed, but inventory checks and decrements must use their aggregate quantity.
- Inventory reservation is atomic: no stock changes when any requested SKU is missing or insufficient.
- Processing the same successful `order_id` again is idempotent and returns the original result without decrementing stock again.
- Failed orders are not cached. A corrected retry with the same `order_id` must be processed normally.
- Batch processing continues after rejected orders and returns one result per input order.
- Reports sort orders by `order_id`, count accepted and rejected orders, and sum revenue from accepted orders only.
- Report money values are strings with exactly two decimal places.

## Required artifacts

`result.json` must contain at least:

```json
{
  "status": "pass",
  "tests_run": 12,
  "acceptance": "PASS"
}
```

The final line of `AGENT_REPORT.md` must be:

```text
COMPLEX_AGENT_TASK_OK tests=12 acceptance=PASS
```
