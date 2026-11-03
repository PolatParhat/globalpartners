# Status: GlobalPartners Business Insights Pipeline
Updated: 2026-11-03 by Claude (project closed: deployed, verified, video recorded, AWS deleted; tutorial started)

## Where we are
**The project is built, deployed once to AWS, verified and deleted.** All steps 1–7 are merged to main. On 2026-11-02 the full year 2023
ran on AWS through the real Airflow DAG (6 runs, `replay_until` run setting): `dq_checks` 25/25, and Athena matches the local reference
to the cent (52,015 orders, $746,223.86, 10,512 customers, CLV $673,614.04, snapshot 2,283,740 rows, 20 locations). The SME video was
recorded (script: `docs/04_video/Video_Speaker_Notes.md`). `infra/down.sh` ran on 2026-11-03: no stacks, database, NAT gateway, load balancer
or Airflow environment remain (checked); the KMS key is pending deletion (7 days, free). Estimated cost ≈ $9–10; confirm in Cost Explorer.
Details and the three bugs found in the real deployment: `docs/decisions.md` (2026-11-02 and 2026-11-03).
**Current phase: the tutorial** (`TUTORIAL.md`; chapter A1 Bash is ready in `tutorial/A01_bash/`). Code is frozen: bug fixes only.

## Step 6 in one paragraph
`dashboard/` (Streamlit 1.66.1): 6 pages (segmentation/RFM, churn risk with a threshold alert list, sales trends + holidays +
category, loyalty impact, location performance, pricing/discounts). `queries.py` = plain SQL returning sums, `logic.py` = pandas
calculations (tested), `views/` = pages, `data.py` = `query(sql)` → Spark SQL locally / Athena on AWS (by `PIPELINE_ENV`).
New gold table `location_summary` (orders, revenue, customers, repeat customers per restaurant; DQ check → **25 checks**).
Sidebar "as of" date drives the customer pages (the snapshot has one row per customer per day). The discount page states the
SME-confirmed limitation (no discounts in the data). Details and reasons: `docs/decisions.md` (2026-11-01 rows).

## Verified on AWS (2026-11-02)
- Full year 2023 through the real Airflow DAG; final `dq_checks` 25/25; Athena numbers identical to the local reference (see above).
- All six dashboard pages worked on Fargate behind the ALB (HTTP, limited to one IP). 99 unit tests and 21 infra tests pass in CI.
- Bugs found only by deploying (all fixed, with tests): MWAA log level required even for disabled modules (PR #8); dashboard
  `PYTHONPATH=/app` (PR #9); `cleanup.py` order for the CDK bootstrap stack (PR #16, not yet run end to end).
- Year-size replay in one run hung on the db.t3.micro; loaded in three chunks instead (root cause not investigated further).

## Next actions
1. User: Cost Explorer check (the bill lags many hours); merge this PR; edit the SME design document if they want it to say HTTP (it still says HTTPS).
2. Tutorial, one chapter per session: start with A1 (`bash tutorial/A01_bash/make_sandbox.sh`, then `tutorial/A01_bash/README.md` and `exercises.md`).
   Order and checklist: `TUTORIAL.md` (Part A concepts and tools, Part B rebuild by hand, Part C the ten production-hardening items).
3. Resume bullets after Part C: what was built and deployed (a demo deployment built to production standard), described accurately.

## Open items
- Old worktrees/branches that can be deleted (merged or declined): worktree-log-data-model-decisions, worktree-step-4.8-tests-ci,
  worktree-step-4.9-cdk, worktree-session-memory, worktree-step-5-metrics (branch `handoff-2026-11-01`, locked), practice/negative-price-test (local),
  worktree-sqlserver-restart-policy (declined by the user), worktree-step-6-dashboard, fix-mwaa-log-level, fix-dashboard-pythonpath,
  docs-video-speaker-notes, dag-replay-range, docs-video-notes-final, tutorial-skeleton, fix-cleanup-bootstrap-order.
- The design document (`Step3_Solution_Design.md`, SME-approved) still says the dashboard is HTTPS; the build used HTTP limited to one IP
  (no domain, so no certificate). Recorded in `docs/decisions.md`; the user decides whether to amend the document.
- The DAG's `replay_until` accepts impossible dates such as 2023-04-31 (the job then fails fast); stricter validation offered, not built.
- The scheduled local Airflow runs of 30 and 31 Oct are `failed` in the local Airflow database; cause not investigated.
- SME assumptions still unconfirmed: Q3, Q8, Q10, Q11a, Q16 (see CLAUDE.md).
- The AWS stack is deleted. To deploy again: `infra/up.sh` (about 45 minutes, about $0.42 per hour) and then `infra/down.sh`.

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
