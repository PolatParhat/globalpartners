# GlobalPartners Business Insights Pipeline

Learning project built to production standard, following the SME plan in
`docs/00_requirements/GlobalPartners_Business_Analysis_Requirements.docx`.

**Where we are:** `STATUS.md` (loaded at session start). **History** (all decisions with reasons,
data findings, SME Q&A, change log): `docs/decisions.md`; read it before re-deciding anything.

## Project context

- **Goal:** Unified view of customer behavior, spend, and business performance.
  Primary metric: daily-evolving Customer Lifetime Value (CLV).
- **Constraints (from SME):** source system is SQL Server (CSVs are seed data only); AWS resources
  only; no new licenses; no Snowflake, dbt, Terraform (on main), Great Expectations or other external
  tools; all transformation logic in PySpark; dashboard in Streamlit; CI/CD via GitHub.
- **Scope:** 2023 orders only (SME confirmed). Every figure and question uses 2023 only.
- Step 3 architecture and data model: **SME approved 2026-10-14**.

## Plan status

| Step | Description | Status |
|---|---|---|
| 1 | Download and verify source files | Done |
| 2 | Initial data analysis | Done |
| 3 | Architecture + data model (SME approval) | Done (approved 2026-10-14) |
| 4 | Build pipeline: local first (4.1–4.8 done), then AWS CDK (4.9 code done, not deployed) | In progress |
| 5 | Metrics: `customer_daily_snapshot`, `sales_daily`, `sales_daily_category` | Not started |
| 6 | Streamlit dashboard (adds ECS Fargate + ALB to PipelineStack) | Not started |
| 7 | Single AWS deployment, verify, record video, delete; submission | Not started |

## Key facts (a fresh session must not get these wrong)

- Business day = **America/New_York** (assumption, unconfirmed); timestamps are UTC.
- Line revenue = `item_price` (line total) + Σ `option_price` × `item_quantity` (option per unit:
  assumption Q3). Money is `DECIMAL`, never float.
- Exclude from metrics: app `Alltown Fresh - DEVELOPMENT` (test data); account `5ece77fe902ad501337b23fd`
  (faulty, excluded from customer metrics, revenue kept in sales); guests (`user_id` NULL) excluded from
  customer metrics, kept in sales. Rules live in `config/business_rules.yaml`.
- 2023 in-scope reference numbers: 52,015 orders, $746,223.86 revenue (items $711,616.66 + options
  $34,607.20); 10,512 customers, CLV total $673,614.04; snapshot 2,283,740 rows.
- Local replay reference: 1 Jan 63 orders / 120 lines / 105 options / $1,078.19; 2 Jan 96 / 159 / 173 /
  $1,424.16; 3 Jan 130 / 184 / 151 / $1,681.19.
- AWS: account 941377112484, region **us-east-1**, deploy once for the demo (`infra/up.sh` → verify →
  video → `infra/down.sh`); the user runs AWS commands, Claude explains them.

## Repo layout

```
globalpartners/
├── CLAUDE.md · STATUS.md · README.md      rules · current state · SME-facing index
├── config/                                environments.yaml (local/prod), business_rules.yaml
├── docs/                                  SME documents by step + decisions.md (history)
├── scripts/                               Step 1–2 analysis (pandas, notebook)
├── sql/                                   01 database + etl_reader login, 02 tables, 03 replay procedure
├── src/globalpartners/
│   ├── common/                            config, spark, job_args, credentials, source, sqlserver, tables, run_log
│   ├── transformations/                   pure functions: cleaning, silver_*, gold_facts, gold_dimensions
│   ├── quality/                           quarantine, checks (19 DQ checks)
│   ├── jobs/                              entry points: setup_source, load_seed, replay_day, extract_to_bronze,
│   │                                      bronze_to_silver, silver_to_gold, dq_checks, smoke_test
│   └── metrics/                           Step 5
├── dags/globalpartners_daily.py           Airflow DAG (local: docker exec; AWS: GlueJobOperator)
├── docker-compose.yml, docker/, airflow/  local stack: sqlserver, spark (Glue 5.1), spark-history, MWAA 3.3.1
├── infra/                                 AWS CDK (2 stacks), up.sh, down.sh, cleanup.py, tests (see infra/README.md)
├── tests/                                 pytest unit tests (run in the spark container or CI)
├── .github/workflows/ci.yml               unit tests + infra synth/tests on every push
└── data/raw/                              immutable source CSVs (not in Git)
```

## Conventions

- Raw files are immutable; fix data downstream. Column names lowercase snake_case.
- Never let a parser guess date formats: `creation_time_utc` = ISO 8601, `date_key` = `dd-MM-yyyy`;
  Spark CSV reads need `multiLine=True, escape='"'`.
- Validation never crashes on bad data: bad rows go to `silver.quarantine`; bad loads fail the DQ step.
- Load all data; filter (2023, test data) at the metrics layer.
- Jobs do I/O; transformations are pure functions with unit tests.
- Code changes on a branch (worktree) → CI green → PR → user merges. Never push to main.
- Local commands: jobs `docker compose exec spark spark-submit src/globalpartners/jobs/<job>.py`;
  tests `docker compose exec spark python3 -m pytest`; Airflow UI http://localhost:8080;
  Spark History http://localhost:18080.
- Debugging: VS Code attached to the `globalpartners-spark-1` container, "Python Debugger: Debug Python File".

## Open SME items (unconfirmed assumptions, documented in the design doc)

Q3 option price per unit · Q8 the $0 menu item · Q10 America/New_York business day ·
Q11a faulty-account sales are real · Q16 no source deletes, changes within the 3-day lookback.
Details and answered questions: `docs/decisions.md`.
