# Chapter A10: Apache Airflow (and MWAA)

**Time:** 2 sessions. **Goal:** explain how Airflow schedules, retries and backfills; read and modify `dags/globalpartners_daily.py`; answer interview questions.

## 1. What and why

Airflow is a workflow scheduler: you write workflows in Python as **DAGs** (directed acyclic graphs of tasks); Airflow runs them on a schedule, in order, retries failures, records history, and shows it in a UI. It orchestrates; it does **not** process big data itself (Glue/Spark does). **MWAA** is Amazon's managed Airflow (here Airflow 3.3.1, mw1.micro).

## 2. Components

| Part | Job |
|---|---|
| **Scheduler** | decides what to run and when |
| **Executor / workers** | run the tasks |
| **Web server (UI/API)** | where you watch and trigger |
| **Metadata database** | state of every DAG run and task |
| **DAG processor** | parses the DAG files |

## 3. Core vocabulary

- **DAG:** the workflow definition. **Task:** one step. **Operator:** a template for a task (`BashOperator`, `GlueJobOperator`, Python `@task`). **Dependency:** `a >> b`.
- **DAG run:** one execution of the DAG for one **logical date** (`ds`, the day being processed). **Task instance:** one task in one run.
- **Schedule:** cron-like (`"0 6 * * *"` = daily 06:00).
- **catchup:** if True, Airflow creates runs for every missed interval since `start_date`; this project sets `catchup=False` (past days are loaded on purpose).
- **max_active_runs=1:** one run at a time, in order.
- **retries / retry_delay:** this DAG: 2 retries, 2 minutes apart.
- **States:** queued, running, success, failed, up_for_retry, skipped, upstream_failed.
- **Trigger:** run now manually. "Trigger DAG w/ config" opens a form for **params**.

## 4. Read the DAG

Open `dags/globalpartners_daily.py` and match:

1. `@dag(…)` defines schedule, start date, catchup, retries and `params`.
2. Six tasks: `replay_day`, `extract_to_bronze`, `bronze_to_silver`, `silver_to_gold`, `gold_metrics`, `dq_checks`, chained with `upstream >> downstream`.
3. Local mode (`PIPELINE_ENV=local`): each step runs `docker exec` in the Spark container. AWS mode: each step is a `GlueJobOperator` that starts the Glue job of the same name and waits.
4. **Templating (Jinja):** `"{{ ds }}"`, `"{{ run_id }}"`, `"{{ params.replay_until or ds }}"` are filled in per run. `run_id` is passed as `--batch-id`, so every row is traceable to the run.
5. The `replay_until` **Param** (type `null|string`, pattern `YYYY-MM-DD`) lets one run replay a range of days.

## 5. How a failed day is re-read (the failure reload)

`extract_to_bronze` stores a watermark and reads from `watermark − 3 days`; the watermark moves **only after a successful run**; writes are MERGE. So a failed run changes nothing, and the next run re-reads the missed data without duplicates. Airflow's retries handle transient errors; alerts (SNS) tell humans about the rest.

## 6. Time zones and triggers

The trigger form uses **your browser time zone**; `ds` is the date in UTC of the logical run. Pick 06:00 so the date is what you expect; to retrigger an existing date, use a different time (e.g. 06:30) so the run id is new.

## 7. Backfill vs catchup

- `catchup=True` = automatic runs for all past intervals.
- **Backfill** = deliberate runs for a date range (CLI/UI). In this project we load history with `replay_until` in a single run, chunked (Jan 4–31, Feb–May, Jun–Dec), because one-day-per-run for 365 days is slow and a whole-year single replay hung the small database.

## 8. Good DAG design

- Tasks **idempotent** and **atomic** (one clear job each).
- No heavy work in the DAG file (it is parsed constantly); no top-level API calls.
- Pass data by reference (S3 paths, table names), not in XCom (small values only).
- Parameterize dates with templates, never `datetime.now()` inside tasks.
- Alert on failure; keep retries bounded; use pools/concurrency for shared resources.
- Sensors wait for conditions (file arrival); prefer event-driven triggers when possible.

## 9. Operating it

| Need | Do |
|---|---|
| See why a task failed | UI → run → task → Logs (Glue log lines are copied in with `verbose=True`) |
| Re-run a failed task | clear the task instance |
| Mark a stuck run as failed | set state to failed (done once in this project) |
| Stop a run cleanly | `stop_job_run_on_kill=True` also stops the Glue job |
| MWAA needs | log levels on all modules; execution role permissions to Glue |

## 10. Exercises

1. Open the Airflow UI (local: http://localhost:8080). Trigger a run, watch the graph.
2. Make a task fail (e.g. a wrong job name in a scratch copy) and watch retries and `upstream_failed`.
3. Add a seventh task `notify` after `dq_checks` that prints the run id (scratch branch). Verify the DAG parses: `python -m py_compile dags/*.py`.
4. Add a second param `dry_run` (bool) and print it in a task.
5. Explain, with the watermark, what happens if `silver_to_gold` fails on Tuesday and succeeds on Wednesday.
6. Explain the difference between `logical date`, `run_id`, and "today".

## Interview questions

1. What is a DAG; why acyclic? 2. Operator vs task vs task instance? 3. What is catchup/backfill? 4. How do you make tasks idempotent? 5. XCom: what and limits? 6. Sensors? 7. How do you handle failures (retries, alerts, SLAs)? 8. Scheduler vs executor? (Celery, Kubernetes, Local) 9. How do you pass dates into tasks (Jinja templating)? 10. Airflow vs Step Functions vs cron? 11. How do you test a DAG? (parse test, unit-test task functions, run in a dev environment) 12. Why not process data inside Airflow workers?

## Done when

Exercises 1 to 6 done; you describe a full day's run, task by task, including what each writes.
