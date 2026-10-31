# Status: GlobalPartners Business Insights Pipeline
Updated: 2026-10-31 by Claude (first STATUS.md; session-memory setup)

## Where we are
Step 4 (build): local pipeline complete (4.1–4.8: SQL Server source, extract, silver, gold, 19 DQ checks,
Airflow, 24 unit tests, CI). Step 4.9 AWS CDK code merged to main (PR #2, commit 0e127ae), **not deployed**.
Currently doing a beginner walkthrough of the 4.9 files, one file per message: **files 1–5 of 14 done**
(names.py, job_args.py, environments.yaml + config.py, credentials.py, sqlserver.py).

## Done recently
- 2026-10-30: 4.9 CDK app (GlobalPartnersData 16 resources + GlobalPartnersPipeline 57, none retained),
  infra/up.sh, infra/down.sh, cleanup.py, run_glue_job.py; Glue-ready job code; DAG GlueJobOperator path;
  CI job `infra` (synth + 11 template tests). Verified: 31 unit tests, local pipeline from empty SQL Server
  identical numbers, DAG parsed in MWAA 3.3.1 image, `cleanup.py --dry-run` on the real account: nothing exists.
- 2026-10-25 to 29: end-to-end learning session Parts 1–9 on the user's stack (rebuilt from empty);
  user's own test + PR #1 merged.
- 2026-10-31: session-memory system: global ~/.claude (CLAUDE.md, hooks, skills /handoff /new-project
  /explain); this STATUS.md; CLAUDE.md slimmed (64 KB → 6 KB), history moved to docs/decisions.md.

## Next actions
1. Continue the walkthrough: **File 6 of 14 = `src/globalpartners/jobs/setup_source.py` + `replay_day.py`**
   (then 7 DAG GlueJobOperator part, 8 infra/app.py + cdk.json, 9 data_stack.py, 10 artifacts.py,
   11 pipeline_stack.py in 6 sections, 12 run_glue_job.py + up.sh, 13 cleanup.py + down.sh, 14 infra tests + CI).
   Use the /explain format: story → concepts → lines → where it fits → tested "try it".
2. Step 5 metrics: `customer_daily_snapshot` (CLV per day, tiers via cume_dist, RFM fixed bands, churn
   45/90), `sales_daily`, `sales_daily_category`; DQ tie-outs; tests. Targets in CLAUDE.md "Key facts".
3. Step 6 Streamlit dashboard (local Docker, then ECS Fargate + ALB in PipelineStack).
4. Later: single AWS deployment (user runs `infra/up.sh`), verify, run DAG 2–3×, record video with
   speaker notes (Claude writes them after the dry run), `infra/down.sh`.

## Open items
- Old worktrees/branches that can be deleted (all merged or declined): worktree-log-data-model-decisions,
  worktree-step-4.8-tests-ci, worktree-step-4.9-cdk, practice/negative-price-test (local),
  worktree-sqlserver-restart-policy (restart policy declined by the user; keep only if they change their mind).
- Planned learning: deep-dive sessions after the build on tools the user picks (must-haves: pytest, GitHub Actions).
- SME assumptions still unconfirmed: Q3, Q8, Q10, Q11a, Q16 (see CLAUDE.md).

## Environment gotchas
- **SQL Server container crashes** under Rosetta (seen 3×, `RETAIL ASSERT … timeout or deadlock`), often
  overnight. Symptom: "TCP/IP connection to the host sqlserver … failed" or Airflow "409 Conflict".
  Fix: `docker compose up -d sqlserver` (data is safe in the volume). No restart policy (user's choice).
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
- Local user stack currently holds 3 replayed days (1–3 Jan 2023) in SQL Server and the lake.
- User preferences: one file/step per message, beginner explanations with tested examples, restate full
  commands, user runs AWS commands, Claude writes code on branches and the user merges via PR.
