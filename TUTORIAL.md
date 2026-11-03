# GlobalPartners tutorial: understand it, then rebuild it by hand

You built a real pipeline by following along. This tutorial is how you make it **yours**: you learn every concept and tool, then you type the whole project again, piece by piece, until you could explain and rebuild any file in an interview.

**Rules of the tutorial**
- One chapter per session. Each chapter has lessons, exercises with checkable answers, and a *done when* test. Claude tests every chapter before you get it.
- You type everything. No copy-paste in Parts B and C.
- The project code is frozen (bug fixes only), so chapters do not go stale. Chapter folders live in `tutorial/`.
- Progress is the checklist below. Tick a chapter only when its *done when* is true. Ask Claude "next chapter".

Start here: **A1 (Bash)**, then follow the order. Parts A1 to A4 are the foundation; the rest of Part A can be taken in the order of your interest, but finish all of Part A before Part B.

---

## Part A: concepts, tools and practice

| ✔ | Chapter | What you learn | Practice | Done when |
|---|---|---|---|---|
| ☐ | **A1 Bash and the command line** (`tutorial/A01_bash/`, **ready**) | files, pipes, grep/awk/sort, variables and quotes, exit codes, `&&`/`||`, tests, loops, `set -euo pipefail`; reading `up.sh`/`down.sh` | sandbox with 12 exercises + 3 bonus, checkable answers | all exercise outputs match; you explain `down.sh` in your own words |
| ☐ | **A2 Git and GitHub workflow** | commits, branches, worktrees, pull requests, merge vs rebase, reading `git log`, undoing mistakes safely, why we never push to main | break and repair a practice repo; open a PR on a scratch repo | you can create a branch, commit, push, open and merge a PR, and recover a lost commit with `reflog` |
| ☐ | **A3 Data engineering concepts** | source vs warehouse vs lake, ETL vs ELT, batch vs streaming, full vs incremental load, watermark, idempotency, CDC, medallion layers, star schema, grain, facts/dimensions, slowly changing dimensions, data quality, quarantine | match each concept to the file in this project that shows it; draw the data flow from memory | you can explain the architecture diagram to a stranger in 3 minutes |
| ☐ | **A4 Python for this project** | virtualenvs and pip, `pathlib`, `argparse`, dataclasses and typing, `logging`, exceptions, `yaml`, `boto3`, `pandas` basics, how imports and packages work (`src/globalpartners/`) | small scripts for each library; read `common/config.py` and `common/job_args.py` | you write a CLI script that reads a YAML config and a CSV with `pandas`, with a test |
| ☐ | **A5 SQL and T-SQL (SQL Server)** | joins, aggregates, window functions, CTEs, MERGE, indexes, transactions and locks, stored procedures, `sqlcmd`; read `sql/01`–`03` | 30 queries on the order tables with known answers (52,015 orders, $746,223.86) | you rewrite the CLV and churn definitions as SQL on your own |
| ☐ | **A6 Docker and Compose** | images vs containers, volumes, networks, ports, `docker compose`, health checks, why images are built for a CPU architecture (ARM64) | build and run a tiny image; read `docker-compose.yml` and `dashboard/Dockerfile` | you add a service to a compose file and explain every key |
| ☐ | **A7 Spark and PySpark** | what Spark is (driver, executors, lazy evaluation, partitions, shuffles), DataFrames, `select/filter/join/groupBy/window`, reading the Spark UI, why jobs get slow | exercises on the project's real transformations in `src/globalpartners/transformations/` | you reproduce the order-line revenue calculation from scratch and explain its plan |
| ☐ | **A8 Iceberg and the lakehouse** | table formats vs files, snapshots and time travel, MERGE, schema evolution, partitioning, compaction, the Glue Data Catalog | run MERGE and time-travel queries on a local Iceberg table | you roll a table back to an earlier snapshot |
| ☐ | **A9 Testing with pytest** | test anatomy, fixtures, parametrize, testing pure functions vs I/O, Spark test sessions, coverage, what to test | read and extend `tests/`; write tests before code for one new function | you add a new rule with a failing test first, then make it pass |
| ☐ | **A10 Airflow** | DAGs, tasks, operators, scheduling and `ds`, retries, templating, params, backfill vs catchup, the UI, MWAA | read `dags/globalpartners_daily.py`; run and break the local DAG | you add a task and a run parameter and explain how a failed day is re-read |
| ☐ | **A11 AWS foundations** | accounts and regions, IAM (users, roles, policies, least privilege), VPC/subnets/NAT/security groups, S3, KMS, Secrets Manager, RDS, Glue, Athena, MWAA, ECS Fargate, ALB, CloudWatch, EventBridge/SNS, cost model | map every resource in the CloudFormation list to its job; estimate a monthly bill | you draw the deployed network and say what each piece costs per hour |
| ☐ | **A12 AWS CDK and CloudFormation** | stacks, constructs, synth vs deploy vs destroy, bootstrap, removal policies, asset staging, reading `infra/globalpartners_infra/*.py`, testing infrastructure | `cdk synth` and the 21 infra tests; add a resource with a test | you add an S3 bucket and an alarm to a stack and see the diff |
| ☐ | **A13 GitHub Actions (CI)** | workflows, jobs, steps, runners, caching, secrets, matrix, branch protection, reading `.github/workflows/ci.yml` | break CI on purpose and fix it | you add a lint step that fails the build on a style error |
| ☐ | **A14 Streamlit and the dashboard** | the rerun model, widgets and state, caching, plotly charts, pandas for dashboards, data access layer (`data.py`), testing pages with `AppTest` | read `dashboard/`; add a seventh page | you add a chart and its test |
| ☐ | **A15 How real teams handle environments** | local vs dev vs staging vs prod, same code + different config, trunk-based development, short-lived branches, ephemeral environments, why local never matches the cloud exactly (examples from this project: the Glue catalog, Athena vs Spark) | diagram of this project's environments; list the config differences in `config/environments.yaml` | you explain why the local stack is in the same branch and not a separate one |
| ☐ | **A16 What makes a project production-grade** | gap analysis of this project against a real team's standard: CI gates, observability, alerting, runbooks, security, reliability, cost, governance | score the project 1 to 5 per area with evidence | you have a written list of the gaps (it becomes Part C) |

## Part B: rebuild the project by hand

You type; Claude checks. Each stage ends with a check command and a known number, so you always know it works. Stages follow how a developer's code actually grows.

| ✔ | Stage | What you build | Check |
|---|---|---|---|
| ☐ | **B1 One script** | a single `main.py` that reads the CSVs with pandas and prints orders and revenue | 52,015 orders, $746,223.86 |
| ☐ | **B2 Functions** | the same logic split into small pure functions (clean, line revenue, filter test data) | functions return the same numbers |
| ☐ | **B3 Tests** | pytest tests for each function, written first for the next ones | green tests |
| ☐ | **B4 Config and modules** | `config/*.yaml`, the `src/globalpartners/` package layout, `common/` helpers | imports work; numbers unchanged |
| ☐ | **B5 SQL Server source** | the Docker SQL Server, the tables and the replay procedure | day 1 = 63 orders, day 2 = 96, day 3 = 130 |
| ☐ | **B6 PySpark bronze** | `extract_to_bronze` with the watermark and the 3-day window | bronze counts equal source counts |
| ☐ | **B7 Silver** | cleaning, typing, flags and quarantine in PySpark | silver + quarantine = bronze |
| ☐ | **B8 Gold** | facts and dimensions on Iceberg with MERGE | order and line revenue agree |
| ☐ | **B9 Metrics** | `customer_daily_snapshot`, sales and location tables | snapshot 2,283,740 rows; CLV $673,614.04 |
| ☐ | **B10 Data quality** | the 25 checks and the ops tables | 25/25 pass; break one on purpose |
| ☐ | **B11 Airflow DAG** | the six-task DAG locally, retries, the `replay_until` param | a full green run |
| ☐ | **B12 Dashboard** | the six pages and their tests | all pages load |
| ☐ | **B13 CI** | GitHub Actions for tests and infra | green on a PR |
| ☐ | **B14 Infrastructure** | the two CDK stacks, tested | `cdk synth` and the infra tests pass |
| ☐ | **B15 Deploy** | a small deployment of your own build and teardown | reference numbers on your dashboard, then `down.sh` |

## Part C: production hardening (the ten postponed items)

Each is a chapter with its own branch and pull request, so your repository shows real engineering history. Items 1 to 6 cost almost nothing; 7 to 10 cost money or need a domain, so they are built and explained, deployed only when you choose.

| ✔ | Chapter | What you build |
|---|---|---|
| ☐ | **C1 Repository safety** | branch protection (CI required, no direct pushes), CODEOWNERS, release tags |
| ☐ | **C2 Code quality in CI** | ruff, formatting, type checks, pre-commit, Dependabot, secret scanning, dependency audit |
| ☐ | **C3 End-to-end test** | a tiny CSV through silver → gold → metrics with known numbers, run in CI |
| ☐ | **C4 Observability** | freshness and volume alarms (CloudWatch), quarantine-rate alert, schema-drift check |
| ☐ | **C5 Runbook** | `docs/runbook.md`: failed run, backfill, restore with Iceberg time travel, teardown |
| ☐ | **C6 Table maintenance** | an Iceberg maintenance job: compaction, snapshot expiry, orphan files |
| ☐ | **C7 Continuous delivery** | GitHub Actions deploy with OIDC (no long-lived keys); dev, staging, prod |
| ☐ | **C8 Security** | HTTPS and sign-in (needs a domain), per-job least-privilege Glue roles, VPC endpoints instead of NAT, RDS certificate verification, audit logging |
| ☐ | **C9 Reliability** | multi-AZ RDS, backups and point-in-time recovery, disaster-recovery notes |
| ☐ | **C10 Governance and scale** | Lake Formation, data catalog and dictionary, retention, deletion on request, partitioning and sizing tests |

After Part C, we write your resume bullets together: what was built and deployed (a demo deployment built to production standard), described accurately.

---

## How a session works

1. Say "next chapter" (or name one). Claude reads this file, opens the chapter folder and checks you are ready.
2. You read the lessons and type every example.
3. You do the exercises; Claude checks your output against the *done when*.
4. You tick the chapter here and Claude commits the progress on a branch.

## Where things are

| What | Where |
|---|---|
| Chapters | `tutorial/A01_bash/`, `tutorial/A02_…` (one folder per chapter, created when we reach it) |
| The finished project (to compare with your rebuild) | the repository itself |
| History of every decision | `docs/decisions.md` |
