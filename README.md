# GlobalPartners Business Insights Pipeline

A data pipeline on AWS that gives GlobalPartners (Alltown Fresh) one view of customer behaviour,
spend and business performance, with **Customer Lifetime Value recalculated daily** as the primary
metric. Built step by step for SME review, to production standard.

- **Source:** SQL Server (Amazon RDS)
- **Processing:** PySpark on AWS Glue, Apache Iceberg tables on Amazon S3
- **Orchestration:** Apache Airflow on Amazon MWAA
- **Dashboard:** Streamlit
- **Deployment:** AWS CDK, GitHub Actions
- **Scope:** 2023 orders

## Status

| Step | Description | Status | Documents |
|---|---|---|---|
| 1 | Download and verify source files | Done | [Data verification findings](docs/01_data_verification/Step1_Data_Verification_Findings.md) · [integrity report](docs/01_data_verification/integrity_report.json) |
| 2 | Initial data analysis | Done | [Initial data analysis](docs/02_data_analysis/Step2_Initial_Data_Analysis.md) · [notebook](scripts/step2/data_analysis.ipynb) |
| 3 | Pipeline architecture and data model | **Approved by the SME (2026-10-14)** | [Solution design](docs/03_architecture/Step3_Solution_Design.md) · [data model](docs/03_architecture/Step3_Data_Model.md) · [architecture diagram](docs/03_architecture/global-partner-pipeline-architecture.png) · [data-model diagram](docs/03_architecture/global-partner-data-model.png) · [cost estimate](docs/03_architecture/cost_estimate.md) · [business rules](config/business_rules.yaml) |
| 4 | Build the pipeline (local first, then AWS) | **Done.** Built and tested locally, then deployed once to AWS ([`infra/`](infra/README.md)), run for all of 2023, and deleted | [Video script](docs/04_video/Video_Speaker_Notes.md) |
| 5 | Metrics: CLV, RFM, churn, sales trends, loyalty, locations | **Done** (matches the full-year reference) | [data model, section 10](docs/03_architecture/Step3_Data_Model.md) |
| 6 | Streamlit dashboards (6 pages) | **Done.** Ran on AWS (Fargate + load balancer, HTTP limited to one IP) and locally | [Run the dashboard](#run-the-dashboard) |
| 7 | Submission, CI/CD, video | CI runs on every push; AWS deployment verified (all 2023, 25/25 checks, numbers match the reference) and deleted; video recorded | [Tutorial](TUTORIAL.md) |

Requirements: [`docs/00_requirements/`](docs/00_requirements/GlobalPartners_Business_Analysis_Requirements.docx).
Decisions and change log: [`docs/decisions.md`](docs/decisions.md) · current state: [`STATUS.md`](STATUS.md) · project rules: [`CLAUDE.md`](CLAUDE.md).

## Run the dashboard

Six pages, one per question in the requirements: customer segmentation (RFM), churn risk, sales trends and
seasonality, loyalty program impact, location performance, pricing and discounts. The discount page states the
SME-confirmed data limitation (the source has no discounts).

```bash
docker compose build spark                 # once: the image now includes Streamlit
docker compose up -d dashboard             # then open http://localhost:8501
```

It reads the gold tables of your local lake (`lake/`), which holds the 3 replayed days. For a **full year** of data
to explore, build a separate demo lake (your own lake and SQL Server are not touched) and point the dashboard at it:

```bash
docker compose exec spark spark-submit scripts/build_demo_lake.py        # writes lake_demo/ (about 2 minutes)
DASHBOARD_WAREHOUSE=/home/hadoop/workspace/lake_demo docker compose up -d dashboard
```

On AWS the same code reads the gold tables through Amazon Athena (Streamlit on ECS Fargate behind a load balancer; see
[`infra/README.md`](infra/README.md)). Code: [`dashboard/`](dashboard/) (`queries.py` SQL, `logic.py` calculations,
`views/` the six pages, `data.py` Spark-or-Athena).

## Repository layout

```
docs/          Everything the SME reads, one folder per step
config/        Business rules applied by the pipeline (business_rules.yaml)
scripts/       One-off analysis scripts (Steps 1–2)
sql/           SQL Server table definitions and seed-data load (Step 4)
src/           PySpark pipeline (Steps 4–5)
dashboard/     Streamlit app (Step 6)
infra/         AWS CDK infrastructure + up.sh / down.sh (Step 4.9, see infra/README.md)
tests/         Automated tests
data/raw/      Source CSV files (not in Git; checksums in the Step 1 report)
```
