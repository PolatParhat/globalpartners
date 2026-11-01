# Status: GlobalPartners Business Insights Pipeline
Updated: 2026-11-01 by Claude (Step 6 built; everything is ready up to the AWS deployment)

## Where we are
Steps 1–5 are merged to main (PR #4 Step 5, PR #5 setup_source warning). The local Airflow run of 2026-11-01 is all green.
**Step 6 (dashboard) is built and committed on branch `worktree-step-6-dashboard`**, worktree
`.claude/worktrees/step-6-dashboard`. **The branch is not pushed and there is no PR yet** (the user merges via PR; say "open the PR").
Step 4.9 + the dashboard's AWS part (Fargate + ALB) are written and tested as templates, **never deployed**.
Remaining before the video: user reviews the dashboard → merge → single AWS deployment (Step 7).

## Step 6 in one paragraph
`dashboard/` (Streamlit 1.66.1): 6 pages (segmentation/RFM, churn risk with a threshold alert list, sales trends + holidays +
category, loyalty impact, location performance, pricing/discounts). `queries.py` = plain SQL returning sums, `logic.py` = pandas
calculations (tested), `views/` = pages, `data.py` = `query(sql)` → Spark SQL locally / Athena on AWS (by `PIPELINE_ENV`).
New gold table `location_summary` (orders, revenue, customers, repeat customers per restaurant; DQ check → **25 checks**).
Sidebar "as of" date drives the customer pages (the snapshot has one row per customer per day). The discount page states the
SME-confirmed limitation (no discounts in the data). Details and reasons: `docs/decisions.md` (2026-11-01 rows).

## Verified (2026-11-01)
- 99 unit tests pass (44 before + 55 new), 19 infra tests pass (11 + 8 new), `cdk synth` ok, pyflakes clean.
- All 6 pages run headless (Streamlit AppTest) against a **full-year demo lake** (`scripts/build_demo_lake.py` → `lake_demo/`,
  built from the raw CSVs, matches 2,283,740 snapshot rows) through the real Spark engine; numbers match the references:
  10,512 customers, CLV $673,614, VIP 755, Churn Risk 7,693, churn 2,409 / 1,553 / 6,550, revenue $746,224, 52,015 orders, 20 restaurants.
- `gold_metrics` + the metric DQ checks ran on a **copy** of the user's lake: SUCCESS, all PASS (the user's lake was not touched).
- AWS dashboard image builds for ARM64 and runs (health 200, non-root); `up.sh` syntax ok; 8 queries parse as Athena SQL.
- **NOT verified:** the Athena path against real Athena (only a stand-in for boto3), the Fargate/ALB deployment, the S3 path
  `lake/gold.db/*` the task role may read (assumed from Iceberg's default location; if the dashboard gets AccessDenied on
  the first deploy, check the table locations in the Glue console), and how the pages look in a browser (Claude cannot see them).

## Next actions
1. User: look at the dashboard. A preview container may be running on http://localhost:8501 (full-year demo data;
   stop it with `docker rm -f gp-dashboard-preview`). Tell Claude what to change (layout, wording, charts).
2. Open the PR for `worktree-step-6-dashboard` (Claude pushes the branch and runs `gh pr create` when the user says so), wait for CI green, user merges.
3. After the merge, in the main folder: `docker compose build spark` (adds Streamlit), `docker compose up -d dashboard`,
   then trigger a Airflow run (pick 06:00) so `gold_metrics` writes `gold.location_summary` and `dq_checks` shows 25/25.
   Optional full-year data: `docker compose exec spark spark-submit scripts/build_demo_lake.py`, then
   `DASHBOARD_WAREHOUSE=/home/hadoop/workspace/lake_demo docker compose up -d dashboard`.
4. Step 7: the single AWS deployment. The user runs `infra/up.sh` (needs Docker running; ~45 min; costs ≈ $0.42/hour), then:
   run the DAG 2–3× (replay days), open the DashboardUrl printed at the end, verify, Claude writes the video speaker notes
   after a dry run, record, `infra/down.sh`. The 4.9 code and the Fargate/ALB/Athena parts have never run on AWS: expect first-deploy fixes.
5. After the build: the full tutorial (see "Planned at the end of the build").

## Planned at the end of the build
- **Full tutorial + rebuild-by-hand (requested 2026-11-01):** after the deployment, Claude writes a very detailed tutorial in the repo
  (chapter folder + `TUTORIAL.md` index with a progress checklist, one chapter per session, each chapter tested before it is given).
  Part A: data-engineering concepts and every tool/library with practice exercises (Python and its libraries, SQL Server, Spark/PySpark,
  Iceberg, Airflow, Docker, pytest, GitHub Actions, AWS services, CDK, Streamlit, Bash). Part B: rebuild this project by hand in the order a
  developer grows code: one `main.py`, then functions, modules, the repo's layout, tests, DAG, infra, dashboard. The user types everything.
  Freeze the code after Step 7 (bug fixes only) so chapters do not go stale. The 4.9 walkthrough files 13–14 (`cleanup.py`/`down.sh`,
  infra tests + CI) fold into that tutorial.
- Bash / command-line course (requested 2026-10-31) is part of Part A.

## Open items
- Old worktrees/branches that can be deleted (merged or declined): worktree-log-data-model-decisions, worktree-step-4.8-tests-ci,
  worktree-step-4.9-cdk, worktree-session-memory, worktree-step-5-metrics (branch `handoff-2026-11-01`, locked), practice/negative-price-test (local),
  worktree-sqlserver-restart-policy (declined by the user).
- The design document (`Step3_Solution_Design.md`, SME-approved) still says the dashboard is HTTPS; the build uses HTTP limited to one IP
  (no domain, so no certificate). Recorded in `docs/decisions.md`; mention it in the video; the user decides whether to amend the document.
- The scheduled Airflow runs of 30 and 31 Oct are `failed` in the local Airflow database; cause not investigated.
- SME assumptions still unconfirmed: Q3, Q8, Q10, Q11a, Q16 (see CLAUDE.md).

## Environment gotchas
- **Never run `setup_source` on a stack that holds data**: script 02 DROPs `dbo.*` and `seed.*` and recreates them empty.
  Restore: `docker compose exec spark spark-submit src/globalpartners/jobs/load_seed.py`, then
  `docker compose exec spark spark-submit src/globalpartners/jobs/replay_day.py --date 2023-01-01 --to-date 2023-01-03`.
- **SQL Server container crashes** under Rosetta (seen 3×, `RETAIL ASSERT … timeout or deadlock`), often
  overnight. Symptom: "TCP/IP connection to the host sqlserver … failed" or Airflow "409 Conflict".
  Fix: `docker compose up -d sqlserver` (data is safe in the volume). No restart policy (user's choice).
- The `spark` container mounts the **main** folder. To test worktree code use a one-off container with the worktree
  mounted: `docker run --rm -v <worktree>:/home/hadoop/workspace -w /home/hadoop/workspace -e PYTHONPATH=/home/hadoop/workspace/src:/home/hadoop/workspace
  -e PIPELINE_ENV=local globalpartners-spark:step6-test -c "python3 -m pytest -q"` (image `globalpartners-spark:step6-test` = Glue 5.1 +
  PyYAML + Streamlit, built from the worktree's `docker/spark/Dockerfile`; after `docker compose build spark` use `globalpartners-spark:5.1.0`).
  Mount a copy of `lake/` for job tests.
- **In the Glue image, Spark's default catalog is Hive/Glue-backed**: `USE lake`, `spark.catalog.setCurrentCatalog` and unqualified names fail
  with "Unable to load credentials". Pipeline jobs avoid it by always using full `lake.<layer>.<table>` names; the dashboard builds its
  session with `extra_conf={"spark.sql.catalogImplementation": "in-memory"}`.
- Claude's worktree sandbox refuses long shell heredocs and `git` mixed into compound commands: use the Edit/Write tools and plain commands.
- Local MWAA needs all 18 `MWAA__LOGGING__*` variables (in docker-compose.yml); `docker exec … airflow`
  CLI does not work (skips the MWAA entrypoint): use the UI or REST API.
- Airflow UI trigger uses the browser time zone: pick 06:00 so `ds` stays the chosen date.
- SQL Server does not allow `GROUP BY 1` (Spark SQL and Athena do).
- Lake SQL prompt: `docker compose exec spark spark-sql --conf spark.sql.catalogImplementation=in-memory
  --conf spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions
  --conf spark.sql.catalog.lake=org.apache.iceberg.spark.SparkCatalog --conf spark.sql.catalog.lake.type=hadoop
  --conf spark.sql.catalog.lake.warehouse=/home/hadoop/workspace/lake --conf spark.sql.session.timeZone=UTC`
- Debug jobs in the VS Code window attached to `globalpartners-spark-1` (bottom-left shows "Container …"),
  not the Mac window.

## Key facts to keep straight
- 2023 only; America/New_York business day; revenue rule and reference numbers: CLAUDE.md "Key facts".
- RFM segments at 31 Dec 2023: Churn Risk 7,693 · VIP 755 · Regular 1,661 · New 403.
- Loyalty at 31 Dec 2023: 4,985 members (47 %), avg CLV $93.12 vs 2.5× lower for non-members, repeat rate 67 % vs 37 % (association, not proof).
- Local user stack holds 3 replayed days (1–3 Jan 2023) in SQL Server and the lake.
- User preferences: concept first, explain imports and every library call, full commands in code blocks, infra files at
  concept level with interview points, user runs AWS commands, Claude writes code on branches, user merges via PR.
  The user gets frustrated by vague answers: say plainly where things are (branch, folder) in the first line.
