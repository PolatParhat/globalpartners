# Status: GlobalPartners Business Insights Pipeline
Updated: 2026-11-01 by Claude (after the DQ failure fix)

## Where we are
Step 4 (local pipeline 4.1–4.8, AWS CDK code 4.9) and **Step 5 (metrics, PR #4)** are merged to main; 4.9 is **not deployed**.
The user's local stack runs the Step 5 code: metric tables exist in the lake, `dq_checks` is 24/24 PASS (run by Claude on 2026-11-01).
Step 6 (Streamlit dashboard) is next. The 4.9 beginner walkthrough stands at **files 1–12 of 14**; files 13 (`cleanup.py` + `down.sh`)
and 14 (infra tests + CI) are not explained yet.

## Incident 2026-11-01 (fixed)
`dq_checks` failed `source_lines_reach_bronze` (463 vs 0) and `source_options_reach_silver` (429 vs 0) on the 06:00 scheduled run
and a manual run. Cause: Claude re-ran `setup_source` on 2026-10-31 as a demo; `sql/02_create_tables.sql` DROPs and recreates
`dbo.*` and `seed.*`, so SQL Server was emptied while the lake kept 3 days. Fix: `load_seed` (203,519 / 193,017 / 365), then
`replay_day --date 2023-01-01 --to-date 2023-01-03` (289 orders / 463 lines / 429 options), then `dq_checks` 24/24 PASS.
The docstring and 02's header now carry a warning (branch `worktree-fix-setup-source-docs`).

## Done in the Step 5 session (2026-10-31)
- Step 5 code (commits `01fcab5`, `8e80abf`, `f848bbb`): `metrics/sales.py` (sales_daily, sales_daily_category),
  `metrics/customer_snapshot.py` (dense calendar, totals/CLV, loyalty, 90/30-day windows, cume_dist tiers, RFM, churn),
  job `jobs/gold_metrics.py` (full rebuild, snapshot partitioned by month), 5 new DQ checks (`metric_checks`, 24 total),
  DAG step `gold_metrics` between `silver_to_gold` and `dq_checks`, Glue job registered in `infra/.../names.py` (8 jobs).
- Verified: 44 unit tests + 11 infra tests pass; DAG parses in the MWAA 3.3.1 image (local and prod); **full-year run
  from the raw CSVs in memory matches every reference number** (52,015 orders, $746,223.86, 2,283,740 snapshot rows,
  10,512 customers, CLV $673,614.04, tiers 2,103/6,604/1,805, churn 2,409/1,553/6,550, example customer 642d6946… row for row).
  Job + DQ checks also ran on a **copy** of the local lake (3 days): SUCCESS, 5/5 PASS. The user's lake was not changed.
- Decisions logged in docs/decisions.md: inclusive "last N days" windows, job order, new DQ checks.
- User chose Step 5 before deploying; the AWS demo and the video wait until Steps 5 and 6 exist.

## Next actions
1. In the Airflow UI, clear the failed `dq_checks` task of today's two runs (06:00 scheduled and the manual one) so they turn green;
   or trigger a new run (pick 06:00) and watch `gold_metrics` and `dq_checks` pass. Merge the docs-fix PR (setup_source warning).
2. Step 6: Streamlit dashboard (local Docker first, then ECS Fargate + ALB in PipelineStack; CDK tests/cost doc update).
3. Finish the 4.9 walkthrough (files 13–14), concept level: what `down.sh`/`cleanup.py` remove and how the leftover check works.
4. Single AWS deployment (user runs `infra/up.sh`), verify, run the DAG 2–3×, record the video with speaker notes
   (Claude writes them after a dry run), `infra/down.sh`. The 4.9 code has never run on AWS, so expect first-deploy fixes.
5. After the build: end-to-end learning session, tool deep dives (pytest, GitHub Actions), and the bash course below.

## Open items
- Old worktrees/branches that can be deleted (merged or declined): worktree-log-data-model-decisions,
  worktree-step-4.8-tests-ci, worktree-step-4.9-cdk, worktree-session-memory, practice/negative-price-test (local),
  worktree-sqlserver-restart-policy (declined by the user; keep only if they change their mind).
- **Planned at the end of the build (requested 2026-10-31): a Bash / command-line course with lots of practice**
  (flags, pipes, `&&`/`||`, `$(...)`, `export`, `set -euo pipefail`, tests like `[ -f ]`, loops), using this
  project's real scripts (`infra/up.sh`, `down.sh`, docker, aws, git) as exercises. Claude builds it for the user.
- Planned learning: deep-dive sessions on tools the user picks (must-haves: pytest, GitHub Actions).
- The scheduled Airflow runs of 30 and 31 Oct are `failed` in the local Airflow database; cause not investigated (they happened
  before the 2026-11-01 incident, so it is not that one; possibly the known SQL Server crash).
- SME assumptions still unconfirmed: Q3, Q8, Q10, Q11a, Q16 (see CLAUDE.md).

## Environment gotchas
- **Never run `setup_source` on a stack that holds data**: script 02 DROPs `dbo.*` and `seed.*` and recreates them empty.
  Restore: `docker compose exec spark spark-submit src/globalpartners/jobs/load_seed.py`, then
  `docker compose exec spark spark-submit src/globalpartners/jobs/replay_day.py --date 2023-01-01 --to-date 2023-01-03`.
- **SQL Server container crashes** under Rosetta (seen 3×, `RETAIL ASSERT … timeout or deadlock`), often
  overnight. Symptom: "TCP/IP connection to the host sqlserver … failed" or Airflow "409 Conflict".
  Fix: `docker compose up -d sqlserver` (data is safe in the volume). No restart policy (user's choice).
- The `spark` container mounts the **main** folder. To test worktree code use a one-off container with the worktree
  mounted: `docker run --rm -v <worktree>:/home/hadoop/workspace -w /home/hadoop/workspace -e PYTHONPATH=/home/hadoop/workspace/src
  -e PIPELINE_ENV=local globalpartners-spark:5.1.0 -c "python3 -m pytest -q"` (mount a copy of `lake/` for job tests).
- Local MWAA needs all 18 `MWAA__LOGGING__*` variables (in docker-compose.yml); `docker exec … airflow`
  CLI does not work (skips the MWAA entrypoint): use the UI or REST API.
- Airflow UI trigger uses the browser time zone: pick 06:00 so `ds` stays the chosen date.
- SQL Server does not allow `GROUP BY 1` (Spark SQL does).
- Lake SQL prompt: `docker compose exec spark spark-sql --conf spark.sql.catalogImplementation=in-memory
  --conf spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions
  --conf spark.sql.catalog.lake=org.apache.iceberg.spark.SparkCatalog --conf spark.sql.catalog.lake.type=hadoop
  --conf spark.sql.catalog.lake.warehouse=/home/hadoop/workspace/lake --conf spark.sql.session.timeZone=UTC`
- Debug jobs in the VS Code window attached to `globalpartners-spark-1` (bottom-left shows "Container …"),
  not the Mac window.

## Key facts to keep straight
- 2023 only; America/New_York business day; revenue rule and reference numbers: CLAUDE.md "Key facts".
- RFM segments at 31 Dec 2023 (new): Churn Risk 7,693 · VIP 755 · Regular 1,661 · New 403.
- Local user stack holds 3 replayed days (1–3 Jan 2023) in SQL Server and the lake; the metrics tables do not exist there yet.
- User preferences: concept first, explain imports and every library call, full commands in code blocks, infra files at
  concept level with interview points, user runs AWS commands, Claude writes code on branches, user merges via PR.
  The user gets frustrated by vague answers: say plainly where things are (branch, folder) in the first line.
