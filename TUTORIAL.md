# GlobalPartners tutorial: understand it, then rebuild it by hand

You built a real pipeline by following along. This tutorial is how you make it **yours**: you learn every concept and tool (with interview questions), then you type the whole project again, piece by piece, until you could explain and rebuild any file in an interview.

**All chapters are written.** One markdown file per chapter, in `tutorial/`. Tick a chapter only when its **Done when** is true.

**Rules**
- You type everything in Parts B and C. Try first; use the real repo as the answer key afterwards.
- The project code is frozen (bug fixes only), so chapters do not go stale.
- Every chapter ends with exercises, interview questions (Part A) or a check with known numbers (Parts B and C).
- Claude helps when you are stuck, reviews your work, and explains AWS commands; **you** run commands that create or delete cloud resources.

**Suggested order:** A1 → A2 → A3 → A4 → A5 → A6 → **A7 (Spark)** → A8 → A9 → A10 → A11 → A12 → A13 → A14 → A15 → A16 → B1 … B15 → C1 … C10.
If an interview is close, do **A7, A3, A5, A8, A10, A11** first.

**What has been tested:** the Bash chapter's exercise answers (on a Mac), the Spark chapter's code and outputs (in the project's Glue 5.1 Spark image), and the B1 to B3 code and numbers (against the real data: 52,015 orders, $746,223.86, 10,512 customers, 6 passing tests). The other chapters are written from the project's real files, numbers and incidents; commands in them that were not run are marked as exercises for you to run. If a command fails, tell Claude and the chapter gets fixed.

---

## Part A: concepts, tools and practice (with interview questions)

| ✔ | Chapter | What you learn |
|---|---|---|
| ☐ | [A1 Bash and the command line](tutorial/A01_bash/README.md) (+ [exercises](tutorial/A01_bash/exercises.md), [solutions](tutorial/A01_bash/solutions.md)) | pipes, grep/awk/sort, variables and quotes, exit codes, `&&`/`||`, loops, `set -euo pipefail`, reading `up.sh`/`down.sh` |
| ☐ | [A2 Git and GitHub workflow](tutorial/A02_git.md) | commits, branches, worktrees, PRs, merge vs rebase, undo safely, `reflog` |
| ☐ | [A3 Data engineering concepts](tutorial/A03_data_engineering_concepts.md) | ETL/ELT, medallion, incremental loads, watermark, idempotency, CDC, star schema, grain, SCD, data quality |
| ☐ | [A4 Python for this project](tutorial/A04_python.md) | venv/pip, imports, stdlib, YAML, pandas, boto3, a tested CLI |
| ☐ | [A5 SQL and T-SQL](tutorial/A05_sql_tsql.md) | joins, windows, CTEs, MERGE, indexes, transactions, locks, stored procedures |
| ☐ | [A6 Docker and Compose](tutorial/A06_docker.md) | images, containers, volumes, networks, Dockerfile, Compose, debugging |
| ☐ | [**A7 Spark and PySpark**](tutorial/A07_spark.md) | architecture, lazy evaluation, shuffles, Catalyst/AQE, joins and strategies, skew, partitions, caching, windows, UDFs, memory, Spark UI, streaming, tuning, 30 interview questions |
| ☐ | [A8 Iceberg and the lakehouse](tutorial/A08_iceberg_lakehouse.md) | table formats, snapshots, time travel, MERGE, compaction |
| ☐ | [A9 Testing with pytest](tutorial/A09_pytest.md) | fixtures, parametrize, testing PySpark, mocking, TDD |
| ☐ | [A10 Airflow and MWAA](tutorial/A10_airflow.md) | DAGs, scheduling, retries, templating, params, backfill |
| ☐ | [A11 AWS foundations](tutorial/A11_aws_foundations.md) | IAM, VPC, S3, KMS, RDS, Glue, Athena, MWAA, ECS, ALB, cost |
| ☐ | [A12 AWS CDK and CloudFormation](tutorial/A12_cdk_cloudformation.md) | stacks, constructs, synth/deploy/destroy, testing infrastructure, the real failures |
| ☐ | [A13 GitHub Actions](tutorial/A13_github_actions.md) | workflows, jobs, caching, OIDC, CI vs CD |
| ☐ | [A14 Streamlit and the dashboard](tutorial/A14_streamlit_dashboard.md) | the rerun model, caching, layers, AppTest |
| ☐ | [A15 How real teams handle environments](tutorial/A15_environments.md) | dev/staging/prod, trunk-based, ephemeral environments, why local never matches the cloud |
| ☐ | [A16 What makes a project production-grade](tutorial/A16_production_grade.md) | gap analysis and scoring; becomes Part C |

## Part B: rebuild the project by hand

| ✔ | Stage | What you build | Check |
|---|---|---|---|
| ☐ | [B1 One script](tutorial/B01_one_script.md) | pandas `main.py` over the raw CSVs | 52,015 orders · $746,223.86 · 10,512 customers |
| ☐ | [B2 Functions](tutorial/B02_functions.md) | pure functions | same numbers |
| ☐ | [B3 Tests](tutorial/B03_tests.md) | pytest suite, test-first | 6 passed |
| ☐ | [B4 Config and modules](tutorial/B04_config_and_modules.md) | YAML rules, package layout | numbers unchanged |
| ☐ | [B5 SQL Server source](tutorial/B05_sql_server_source.md) | Docker SQL Server, tables, replay procedure | days 1 to 3: 63 / 96 / 130 orders |
| ☐ | [B6 PySpark bronze](tutorial/B06_pyspark_bronze.md) | incremental extract, watermark, lookback | bronze 463 lines · 429 options |
| ☐ | [B7 Silver and quarantine](tutorial/B07_silver_and_quarantine.md) | clean, type, MERGE, quarantine | bronze = silver + quarantine; reruns safe |
| ☐ | [B8 Gold star schema](tutorial/B08_gold_star_schema.md) | facts and dimensions | order and line revenue agree |
| ☐ | [B9 Metrics](tutorial/B09_metrics.md) | CLV snapshot, RFM, churn, sales, locations | 2,283,740 rows · CLV $673,614.04 |
| ☐ | [B10 Data quality](tutorial/B10_data_quality.md) | 25 checks, ops tables | 25/25 pass; break one on purpose |
| ☐ | [B11 Airflow DAG](tutorial/B11_airflow_dag.md) | six tasks, retries, `replay_until` | green runs |
| ☐ | [B12 Dashboard](tutorial/B12_dashboard.md) | six pages, Athena/Spark data layer | all pages show the numbers |
| ☐ | [B13 CI](tutorial/B13_ci.md) | GitHub Actions tests | green PR |
| ☐ | [B14 Infrastructure](tutorial/B14_infrastructure.md) | two tested CDK stacks, scripts | `cdk synth` + tests pass |
| ☐ | [B15 Deploy and teardown](tutorial/B15_deploy_and_teardown.md) | your build on AWS, verified, deleted | reference numbers on your dashboard |

## Part C: production hardening (one branch and PR each)

| ✔ | Chapter | What you build |
|---|---|---|
| ☐ | [C1 Repository safety](tutorial/C01_repository_safety.md) | branch protection, CODEOWNERS, PR template, tags |
| ☐ | [C2 Code quality in CI](tutorial/C02_code_quality_ci.md) | ruff, types, pre-commit, Dependabot, secret scanning, audit |
| ☐ | [C3 End-to-end test](tutorial/C03_end_to_end_test.md) | tiny dataset with known answers in CI |
| ☐ | [C4 Observability](tutorial/C04_observability.md) | freshness/volume/quality alarms, schema drift |
| ☐ | [C5 Runbook](tutorial/C05_runbook.md) | failure playbook from real incidents |
| ☐ | [C6 Table maintenance](tutorial/C06_table_maintenance.md) | compaction, snapshot expiry, orphan files |
| ☐ | [C7 Continuous delivery](tutorial/C07_continuous_delivery.md) | GitHub OIDC deploys, environments |
| ☐ | [C8 Security](tutorial/C08_security.md) | HTTPS + sign-in, per-job roles, VPC endpoints, RDS certificates, audit logs |
| ☐ | [C9 Reliability](tutorial/C09_reliability.md) | multi-AZ, backups, restore drill, RPO/RTO |
| ☐ | [C10 Governance and scale](tutorial/C10_governance_and_scale.md) | dictionary, Lake Formation, retention, deletion, sizing |

After Part C, we write your resume bullets together: what was built and deployed (a demo deployment built to production standard), described accurately.

---

## How to use a chapter

1. Read the lessons and type every example.
2. Do the exercises; compare with the stated answers or numbers.
3. Tick the chapter here and commit the progress on a branch.
4. Ask Claude for a review of your work, or for help on anything that does not match.

## Where things are

| What | Where |
|---|---|
| Chapters | `tutorial/` (`A01_bash/` is a folder; every other chapter is one `.md` file) |
| The finished project (answer key) | the repository itself |
| Every decision with its reason | `docs/decisions.md` |
