# Stage B7: silver (clean, type, flag) and quarantine

**Goal:** turn bronze text into typed, deduplicated, flagged silver tables with MERGE; route broken rows to a quarantine table with reasons. Prerequisites: A7, A8, B6.

## Rules to implement (from the data model)

- Parse `creation_time_utc` as ISO 8601 (with or without fraction); `date_key` as `dd-MM-yyyy`. **Never let Spark guess a format.**
- Money columns as `DECIMAL(18,2)`; quantities as integers.
- Trim text, normalize empty strings to NULL.
- Flags: `is_guest` (no user), `is_test_app`, `is_loyalty`. Keep the loyalty card number in silver only.
- **Valid** row: has keys, a parseable timestamp, non-negative price. Anything else is **quarantined** with *all* its reasons, not dropped, and the run continues.

## Steps

1. **`transformations/cleaning.py`:** small pure helpers: `parse_ts`, `to_decimal`, `clean_string`, `reasons(df)` (an array of failure reasons per row).
2. **`transformations/silver_order_items.py`, `silver_order_item_options.py`, `silver_date_dim.py`:** each takes a bronze DataFrame, returns `(valid, bad)`.
3. **`quality/quarantine.py`:** `ensure_table` and `record(bad, table)` which MERGEs: a new broken row is inserted; one seen again increments `times_seen` and updates `last_seen_batch_id`.
4. **`common/tables.py` `merge_into(spark, target, source_df, keys)`:** generates `MERGE INTO … WHEN MATCHED THEN UPDATE SET * WHEN NOT MATCHED THEN INSERT *`. Source must be unique per key: dedupe first with a window (`row_number` over the key, newest `_loaded_at` first).
5. **`jobs/bronze_to_silver.py`:** read the batch's bronze rows, transform, MERGE valid rows into `lake.silver.*`, record bad rows, log the run.
6. **Tests first:** for each rule, one test with a tiny DataFrame (bad date, negative price, missing key, duplicate).

## Check

- `bronze = silver + quarantine` (row counts reconcile for the batch).
- Run `bronze_to_silver` twice: silver count does **not** change (idempotent).
- Your negative-price test row lands in `silver.quarantine` with reason text.

```sql
SELECT count(*) FROM lake.silver.order_items;
SELECT reasons, count(*) FROM lake.silver.quarantine GROUP BY reasons;
```

On the real 2023 data no row is quarantined; the table protects future loads.

## Compare with the real project

`transformations/cleaning.py`, `silver_*.py`, `quality/quarantine.py`, `jobs/bronze_to_silver.py`, `tests/test_cleaning.py`, `test_silver_*.py`.

## Done when

Reruns do not duplicate, bad rows are quarantined with reasons, and you wrote a test for each rule before the code.
