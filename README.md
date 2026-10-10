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
| 3 | Pipeline architecture and data model | **Awaiting SME approval** | [Solution design](docs/03_architecture/Step3_Solution_Design.md) · [data model](docs/03_architecture/Step3_Data_Model.md) · [architecture diagram](docs/03_architecture/global-partner-pipeline-architecture.png) · [data-model diagram](docs/03_architecture/global-partner-data-model.png) · [cost estimate](docs/03_architecture/cost_estimate.md) · [business rules](config/business_rules.yaml) |
| 4 | Build the pipeline on AWS | Not started | |
| 5 | Metrics: CLV, RFM, churn, sales trends, loyalty, locations, discounts | Not started | |
| 6 | Streamlit dashboards | Not started | |
| 7 | Submission, CI/CD, video | Not started | |

Requirements: [`docs/00_requirements/`](docs/00_requirements/GlobalPartners_Business_Analysis_Requirements.docx).
Running log of decisions: [`CLAUDE.md`](CLAUDE.md).

## Repository layout

```
docs/          Everything the SME reads, one folder per step
config/        Business rules applied by the pipeline (business_rules.yaml)
scripts/       One-off analysis scripts (Steps 1–2)
sql/           SQL Server table definitions and seed-data load (Step 4)
src/           PySpark pipeline (Steps 4–5)
dashboard/     Streamlit app (Step 6)
infra/         AWS CDK infrastructure (Step 4)
tests/         Automated tests
data/raw/      Source CSV files (not in Git; checksums in the Step 1 report)
```
