# Status: GlobalPartners Business Insights Pipeline
Updated: 2026-11-01 by /handoff

## Where we are
Steps 1–5 done: local pipeline (4.1–4.8), AWS CDK code (4.9, **never deployed**), and Step 5 metrics (PR #4 merged, commit `757522f`).
The local stack runs the Step 5 code; metric tables exist in the lake and `dq_checks` is 24/24 PASS. Step 6 (Streamlit
dashboard) is next, then the single AWS deployment + video. The 4.9 beginner walkthrough is at files 1–12 of 14.

## Done this session
- Walkthrough files 6–12 explained (setup_source/replay_day, DAG Glue part, app.py + cdk.json, data_stack, artifacts,
  pipeline_stack at concept level, up.sh + run_glue_job.py). From file 11 on: concept + interview points, imports and every library call explained.
- Step 5 (commits `01fcab5`, `8e80abf`, `f848bbb`, merged as PR #4): `metrics/sales.py`, `metrics/customer_snapshot.py`, job
  `gold_metrics` (between `silver_to_gold` and `dq_checks`), 5 new DQ checks (24 total), 8th Glue job in `names.py`.
  Verified: 44 unit + 11 infra tests; full 2023 from the raw CSVs matches every reference (see Key facts).
- Incident 2026-11-01 (fixed): `dq_checks` failed because Claude re-ran `setup_source` on 2026-10-31; `sql/02_create_tables.sql`
  DROPs `dbo.*` and `seed.*`. Restored with `load_seed` + `replay_day` 1–3 Jan (289 orders / 463 lines / 429 options); 24/24 PASS.
- PR #5 (branch `worktree-fix-setup-source-docs`, commit `a96828b`, CI green): warnings in the `setup_source` docstring and 02's header.

## Next actions
1. User: merge PR #5. In Airflow (http://localhost:8080) clear the failed `dq_checks` task of today's two runs (06:00 scheduled,
   manual) or trigger a new run (pick 06:00); `gold_metrics` and `dq_checks` should be green.
2. Step 6: Streamlit dashboard (local Docker first, then ECS Fargate + ALB in PipelineStack; CDK tests and cost doc update).
3. Finish the walkthrough (file 13 `cleanup.py` + `down.sh`, file 14 infra tests + CI), concept level.
4. Single AWS deployment (user runs `infra/up.sh`), verify, run the DAG 2–3×, record the video (Claude writes speaker notes after
   a dry run), `infra/down.sh`. The 4.9 code has never run on AWS: expect first-deploy fixes.
5. After the build: end-to-end learning session, tool deep dives (pytest, GitHub Actions), and the bash course.

## Open items
- PR #5 open. Scheduled Airflow runs of 30 and 31 Oct failed; cause not investigated (before the incident, so a different cause).
- **Planned for the end of the build: a Bash / command-line course with lots of practice** (flags, pipes, `&&`/`||`, `$(...)`,
  `export`, `set -euo pipefail`, `[ -f ]`, loops) using this project's scripts as exercises (requested 2026-10-31).
- Old worktrees/branches that can be deleted: worktree-log-data-model-decisions, worktree-step-4.8-tests-ci,
  worktree-step-4.9-cdk, worktree-session-memory, worktree-step-5-metrics, practice/negative-price-test (local);
  worktree-sqlserver-restart-policy (declined by the user).
- SME assumptions still unconfirmed: Q3, Q8, Q10, Q11a, Q16 (see CLAUDE.md).

## Environment gotchas
- **Never run `setup_source` on a stack that holds data** (script 02 DROPs `dbo.*` and `seed.*`). Restore:
  `docker compose exec spark spark-submit src/globalpartners/jobs/load_seed.py`, then
  `docker compose exec spark spark-submit src/globalpartners/jobs/replay_day.py --date 2023-01-01 --to-date 2023-01-03`.
- **SQL Server container crashes** under Rosetta (`RETAIL ASSERT … timeout or deadlock`). Symptom: "TCP/IP connection to the
  host sqlserver … failed" or Airflow "409 Conflict". Fix: `docker compose up -d sqlserver` (data is safe). No restart policy.
- The `spark` container mounts the **main** folder. To test a worktree use a one-off container:
  `docker run --rm -v <worktree>:/home/hadoop/workspace -w /home/hadoop/workspace -e PYTHONPATH=/home/hadoop/workspace/src
  -e PIPELINE_ENV=local globalpartners-spark:5.1.0 -c "python3 -m pytest -q"` (mount a COPY of `lake/` for job tests).
- Local MWAA needs all 18 `MWAA__LOGGING__*` variables (docker-compose.yml); `docker exec … airflow` CLI does not work: use UI/REST API.
- Airflow UI trigger uses the browser time zone: pick 06:00 so `ds` stays the chosen date.
- SQL Server does not allow `GROUP BY 1` (Spark SQL does).
- Lake SQL prompt: `docker compose exec spark spark-sql --conf spark.sql.catalogImplementation=in-memory
  --conf spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions
  --conf spark.sql.catalog.lake=org.apache.iceberg.spark.SparkCatalog --conf spark.sql.catalog.lake.type=hadoop
  --conf spark.sql.catalog.lake.warehouse=/home/hadoop/workspace/lake --conf spark.sql.session.timeZone=UTC`
- Debug jobs in the VS Code window attached to `globalpartners-spark-1`, not the Mac window.

## Key facts to keep straight
- 2023 only; America/New_York business day; revenue rule and reference numbers: CLAUDE.md "Key facts".
- Step 5 full-year check (verified): 52,015 orders, $746,223.86 (sales_daily and sales_daily_category); snapshot 2,283,740 rows,
  10,512 customers, CLV $673,614.04; 31 Dec tiers High 2,103 / Medium 6,604 / Low 1,805; churn active 2,409 / at_risk 1,553 /
  lapsed 6,550; RFM segments Churn Risk 7,693 / Regular 1,661 / VIP 755 / New 403. "Last N days" windows include the snapshot day.
- Local stack holds 3 replayed days (1–3 Jan 2023; 63/96/130 orders, 289 total) in SQL Server and the lake.
- User preferences: concept first; explain imports and every library call; full commands in code blocks; infra files at concept
  level with interview points; say where things are (branch, folder) in the first line; user runs AWS commands; Claude writes
  code on branches and the user merges via PR. Never call something "safe to repeat" without reading the code it runs.
