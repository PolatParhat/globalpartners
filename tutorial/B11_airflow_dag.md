# Stage B11: the Airflow DAG

**Goal:** orchestrate the six steps with retries, local first. Prerequisites: A10, B5 to B10.

## Steps

1. **Run Airflow locally** with the MWAA image (`amazon/mwaa-local`-style setup used in `docker-compose.yml`): the web UI at http://localhost:8080. Note the required `MWAA__LOGGING__*` variables.
2. **`dags/globalpartners_daily.py`:**
   - `@dag(schedule="0 6 * * *", start_date=datetime(2023,1,1), catchup=False, max_active_runs=1, default_args={"retries": 2, "retry_delay": timedelta(minutes=2)})`
   - tasks in order: `replay_day` → `extract_to_bronze` → `bronze_to_silver` → `silver_to_gold` → `gold_metrics` → `dq_checks`
   - `run_id` passed as `--batch-id`
   - local mode: run each step in the `spark` container (`docker exec`); AWS mode (later): `GlueJobOperator`
3. **Add the `replay_until` Param** (string `YYYY-MM-DD`, optional) so one run can replay a range; the replay task uses `params.replay_until or ds`.
4. **Test:** `python -m py_compile dags/*.py`; load the DAG in the MWAA image to confirm it parses.

## Check

- Trigger a run from the UI at **06:00** (the form uses your browser's time zone; 06:00 keeps `ds` equal to the date you pick). The first run for 2023-01-01 must show **63 orders** in the `replay_day` log.
- Make a task fail and watch retries (2 × 2 minutes), then `upstream_failed` downstream.
- Fix and re-run: no duplicates (watermark + MERGE).
- Run 2023-01-02 and 2023-01-03; `dq_checks` stays green.

## Experiments

- Trigger with `replay_until` = `2023-01-31` and observe the long `replay_day`.
- Trigger the same date twice: what changes? (run ids must differ; use a different time.)

## Compare with the real project

`dags/globalpartners_daily.py` and chapter A10's reading guide.

## Done when

A full green run exists for three consecutive days and you can explain what happens on a failed day.
