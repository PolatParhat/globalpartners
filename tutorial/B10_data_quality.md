# Stage B10: data-quality checks and the ops tables

**Goal:** a final job that proves the load is correct, writes the results, and fails the run if not. Prerequisites: A3 (data quality), B6 to B9.

## Principles

- Checks **reconcile** layers; they do not just count nulls.
- Each check returns a record: `name, observed, expected, passed, details, severity`.
- All results go to `lake.ops.dq_results` with the batch id (an audit trail).
- If any `FAIL` check fails, the job exits non-zero → Airflow marks the run failed → the dashboard keeps the last good data.

## The 25 checks (build them in groups; name = the first column)

1. **Reconciliation:** source lines reach bronze; bronze = silver + quarantine per table; source options reach silver.
2. **Uniqueness:** keys unique in silver and in every fact and dimension.
3. **Referential integrity:** every fact row finds its customer, location, item, app and date.
4. **Revenue ties:** Σ line revenue = Σ order revenue = Σ `sales_daily` = Σ `sales_daily_category`.
5. **Quarantine rate:** under 1 %.
6. **Snapshot checks:** one row per customer per day; no gaps; CLV on the last day = Σ revenue; tiers and segments complete.
7. **Location summary ties** to `fact_order`.

Real-world finding: `location_summary_ties_to_fact_order` failed on an empty run (None vs 0), because the check correctly refuses empty loads. When you write checks, decide what *empty* means.

## Steps

1. `quality/checks.py`: `result(...)`, `run_checks(spark, lake, db, batch_id, rules)`, `metric_checks(...)`.
2. `jobs/dq_checks.py`: run the checks, write `ops.dq_results`, print a table, `sys.exit(1)` if any FAIL.
3. Tests for the check logic with tiny DataFrames (one passing and one failing case per group).

## Check

- Normal run: **25/25 PASS**.
- **Break it on purpose:** delete one row from silver (on a scratch copy of the lake) and rerun: the reconciliation check fails and the job exits with an error; restore and see it pass.

## Compare with the real project

`quality/checks.py`, `jobs/dq_checks.py`, `common/run_log.py`.

## Done when

25/25 pass, you can make one fail on purpose, and you can say why a failing check is better than a wrong dashboard.
