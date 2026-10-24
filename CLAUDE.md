# GlobalPartners Business Insights Pipeline

Learning project built to production standard, following the SME plan in
`docs/00_requirements/GlobalPartners_Business_Analysis_Requirements.docx`.

## Project context

- **Goal:** Unified view of customer behavior, spend, and business performance.
  Primary metric: daily-evolving Customer Lifetime Value (CLV).
- **Constraints (from SME):**
  - Source system is SQL Server (CSVs are seed data only)
  - AWS resources only; no new licenses; no Snowflake, dbt, or other external tools
  - All transformation logic in PySpark
  - Dashboard in Streamlit
  - CI/CD via GitHub
- **Approval gate:** Step 3 architecture requires written SME sign-off before Step 4.
- **Scope:** 2023 only (SME confirmed).

## Plan status

| Step | Description | Status |
|---|---|---|
| 1 | Download and verify source files | Done |
| 2 | Initial data analysis | Done; remaining SME questions tracked below |
| 3 | Pipeline architecture + data model (SME approval) | Done: SME approved 2026-10-14 |
| 4 | Build pipeline on AWS | In progress (local first) |
| 5 | Metrics (CLV, RFM, churn, trends, loyalty, locations, discounts) | Not started |
| 6 | Streamlit dashboards | Not started |
| 7 | Submission, CI/CD, video | Not started |

## Repo layout

```
globalpartners/
├── README.md                      # Entry point: overview + index of every step
├── CLAUDE.md                      # Running log of decisions and changes
├── requirements.txt
├── config/                        # business_rules.yaml (SME-changeable rules)
├── docker-compose.yml             # local stack: sqlserver, spark (Glue 5.1), spark-history
├── docker/spark/Dockerfile        # Glue 5.1 image + PyYAML
├── .env / .env.example            # local secrets (.env not in Git)
├── .gitignore
├── docs/                          # Everything the SME reads, in step order
│   ├── 00_requirements/
│   ├── 01_data_verification/      # findings report + integrity_report.json
│   ├── 02_data_analysis/          # findings report
│   ├── 03_architecture/
│   ├── 05_metrics/
│   └── 07_submission/
├── scripts/                       # One-off analysis scripts, by step
│   ├── step1/                     # verify_raw_file.py, inspect_dates.py
│   └── step2/                     # data_analysis.ipynb
├── sql/                           # SQL Server DDL, seed-data load
├── src/globalpartners/            # Step 4-5 PySpark pipeline
│   ├── ingestion/
│   ├── transformations/
│   ├── quality/
│   └── metrics/
├── dashboard/                     # Step 6 Streamlit app
├── infra/                         # AWS setup
├── tests/
├── .github/workflows/             # Step 7 CI/CD
└── data/raw/                      # Immutable source CSVs (not in Git)
```

## Conventions

- **Raw files are immutable.** Fix data downstream, never in `data/raw/`.
  SHA-256 checksums prove files are unchanged.
- **Column names are lowercase snake_case**, normalized right after reading.
- **Read raw CSVs as strings** (`dtype=str`, `keep_default_na=False`) so nothing is
  silently converted.
- **Scripts build paths from `Path(__file__)`**; notebooks find the root by
  searching upward for `requirements.txt`.
- **Validation code must never crash on bad data.** Report the problem and continue.
- **Never let a parser guess date formats.** `creation_time_utc` = ISO8601,
  `date_key` = `%d-%m-%Y`.
- **Load all data; filter at the metrics layer.** Scope filters (e.g. 2023) are
  reporting decisions, not ingestion decisions.
- **Environment:** project-local `.venv` (Python 3.13); conda `base` deactivated.
- **Debugging:** VS Code "Python Debugger: Debug Python File"; no `launch.json`.

## Decisions

| Date | Decision | Reason |
|---|---|---|
| 2026-10-01 | Use pandas for Step 1-2 analysis; rebuild checks in PySpark in Step 4 | One-off analysis; SME's PySpark rule applies to the pipeline |
| 2026-10-01 | SHA-256 for file checksums | Industry standard, native in S3, MD5/SHA-1 are broken |
| 2026-10-01 | Normalize column names to lowercase | Source headers are uppercase; SQL Server and Spark treat case differently |
| 2026-10-01 | Removed `.vscode/launch.json`; fixed paths in code instead | Script should run from any folder without editor config |
| 2026-10-01 | Explicit date formats: `creation_time_utc` = ISO8601, `date_key` = `%d-%m-%Y` | pandas guessed wrong: ms vs no-ms timestamps; DD-MM read as MM-DD |
| 2026-10-01 | Repo organized as numbered `docs/` per step + standard `src/` layout | SME can review steps in order; pipeline code separated from one-off scripts |
| 2026-10-01 | `data/raw/` excluded from Git; checksums documented instead | Never commit data to a code repo |
| 2026-10-01 | Step 2 analysis in a Jupyter notebook | Code, output, and notes together; SME can read results on GitHub |
| 2026-10-04 | Line revenue = `item_price` (not × quantity) | Data contradicts doc: item_price is the line total (0 of 13,650 multi-qty rows match unit price) |
| 2026-10-04 | Revenue formula: `item_price + Σ(option_price × item_quantity)` | option_price is a unit price; per-unit vs once-per-line differs by $12,455.65 (0.67%); assumption pending SME |
| 2026-10-04 | Left-join options to line items | 50% of line items have no options |
| 2026-10-04 | Analysis scope limited to 2023 | SME confirmed; date_dim covers 2023 only |
| 2026-10-04 | Load all years into raw/cleaned layers; filter to 2023 at metrics layer | Data stays available if scope changes |
| 2026-10-04 | Working business time zone `America/New_York` (assumption pending SME Q10) | Alltown is a New England chain; only 1 row changes year vs UTC, so low risk |
| 2026-10-04 | Exclude `Alltown Fresh - DEVELOPMENT` rows from all metrics (826 rows; 700 in 2023) | SME confirmed test data. Kept in raw/cleaned layers with an `is_test_data` flag; filtered at the metrics layer, like the 2023 scope |
| 2026-10-04 | Start Step 3 while SME Q4 and Q11 are pending; design with placeholders | Answers change filters, not architecture. Pipeline flags rows (`is_guest`, `is_non_customer_account`) and reads the rules from a config file, so an SME answer is a config change + gold rerun, not a code change |
| 2026-10-04 | Placeholder Q4: guests excluded from customer metrics, included in sales/location metrics | Proposed default sent to SME; 4,492 orders (8.6%), $60,247 (8.1%) in scope |
| 2026-10-04 | Placeholder Q11: account `5ece77fe902ad501337b23fd` excluded from customer metrics, revenue kept in sales totals | Proposed default sent to SME; 937 orders at 15 locations on 54 days in 2023, up to 95/day, would be #1 CLV |
| 2026-10-04 | Tool selection strictly follows the requirements doc: AWS services, PySpark, SQL Server, Streamlit, GitHub, draw.io only | User instruction. No Terraform, LocalStack, MinIO, Great Expectations, dbt, Snowflake. Local dev uses Docker images of the same components AWS runs |
| 2026-10-04 | Source DB: Amazon RDS for SQL Server Express (prod); SQL Server 2022 Developer in Docker (local) | Lowest-cost production-realistic option: managed, license included (no new license), encrypted, backed up; 10 GB limit vs 55 MB data. Developer edition is free for non-production use |
| 2026-10-04 | Orchestration: Apache Airflow on Amazon MWAA (prod); official MWAA Docker image locally | User wants industry-standard Airflow; MWAA is the AWS-managed service, so it satisfies "AWS resources only". Replaces the earlier Step Functions proposal. Cost: small env ~$0.49/h (~$360/mo 24/7), so the prod environment is created only when needed and destroyed with IaC |
| 2026-10-04 | Local-first: build and test the whole pipeline locally in Docker, then promote to AWS via GitHub CI/CD | Same code and images in both; only config (paths, catalog, credentials, operators) differs per environment (`PIPELINE_ENV=local|prod`) |
| 2026-10-04 | Transform compute: AWS Glue 5.1 (Spark 3.5.6, Python 3.11); pipeline code targets Python 3.11 | SME requires PySpark; Glue is serverless (no cluster). The Step 1-2 `.venv` (3.13) stays for analysis only |
| 2026-10-04 | Lake table format: Apache Iceberg on S3, registered in Glue Data Catalog, queried with Athena | Native in Glue 5.1 (Iceberg 1.10) and Athena, so no extra tool. ACID writes, MERGE for idempotent reruns, time travel to roll back a bad load (failure reload requirement) |
| 2026-10-04 | Infrastructure as code: AWS CDK (Python) | AWS-native (Terraform is an external tool), same language as the pipeline, deploys through CloudFormation with rollback |
| 2026-10-04 | Two versions: v1 = AWS CDK on `main` (the submission); v2 = Terraform on a separate branch (`iac/terraform`), built after v1 works | Learning goal: compare both IaC tools. v2 deviates from the SME's no-external-tools rule, so it is never merged to `main` or submitted. Pipeline code, DAGs and config are shared; only `infra/` differs |
| 2026-10-04 | Medallion layers on Iceberg: bronze (raw copy), silver (clean, typed, flagged), gold (star schema + metrics) | Rebuild silver/gold from bronze without touching the source; each layer has one job |
| 2026-10-04 | Incremental extract: watermark on `creation_time_utc` + 3-day lookback; `date_dim` full load | Data grows daily; lookback catches late-arriving rows (e.g. the 28 orphan options) |
| 2026-10-04 | Bronze append-only with audit columns (`_batch_id`, `_ingested_at`, `_source_table`); silver/gold written with MERGE | Idempotent reruns: a retry or backfill never duplicates rows (failure reload requirement) |
| 2026-10-04 | Bad rows go to `silver.quarantine` with a reason; every run logged in `ops.pipeline_runs`; watermarks in `ops.watermarks` | Never crash on bad data; full audit trail from dashboard number back to run and source |
| 2026-10-04 | Business rules in `config/business_rules.yaml` (excluded apps, non-customer ids, guest handling) | SME answers become config changes |
| 2026-10-04 | Replay script simulates daily order arrivals into SQL Server | Source data is a static snapshot; replay shows real incremental daily runs and daily-evolving CLV |
| 2026-10-04 | Step 2 notebook must pass Restart & Run All before commit | Stale outputs hid a NameError (`option_once`); evidence must be reproducible |
| 2026-10-05 | Q11 confirmed: account `5ece77fe902ad501337b23fd` excluded from customer metrics (CLV, RFM, churn, High-CLV threshold, customer counts); revenue kept in sales/location totals | SME confirmed findings: faulty data, not a real customer. Flagged `is_non_customer_account` in silver; id listed in `config/business_rules.yaml`. Assumes the sales are real but wrongly attributed; if SME says the orders never happened, drop from sales too (config change) |
| 2026-10-05 | No other non-customer accounts assumed (SME Q11 part 3 unanswered) | Config list can be extended without code change |
| 2026-10-06 | Step 3.3 data model approved: silver = `order_items`, `order_item_options`, `date_dim`, `quarantine` (same grain as source, typed, cleaned, flagged); gold star schema = `fact_order_line` (1 row per order line), `fact_order` (1 row per order), `dim_customer`, `dim_location`, `dim_item`, `dim_app`, `dim_date`; gold metrics = `customer_daily_snapshot` (customer × day), `sales_daily` (date × location × category × hour) | Primary goal (CLV evolving daily) needs a per-day snapshot; facts at two grains so order-level metrics (AOV, frequency, recency) never count item lines as orders. Loyalty and discount analysis are queries over `fact_order` + snapshot |
| 2026-10-06 | Natural keys (`user_id`, `restaurant_id`, `order_id + lineitem_id`); hash key for items (clean name + category); guests get `customer_id = 'GUEST'` with one GUEST row in `dim_customer` | Generated integer surrogate keys are not stable across Spark reruns and would break idempotent MERGE. A blank key would silently drop guest revenue from joins |
| 2026-10-06 | Loyalty kept per order on the facts and "as of that day" in the snapshot; no SCD Type 2 | Every order already records `is_loyalty` (finding 35), so the history exists without versioned customer rows |
| 2026-10-06 | `customer_daily_snapshot` is dense: one row per customer for every day from first order | Recency, churn status and tiers change on days with no orders; a sparse table could not show a customer drifting into "at risk". ~3.8 M rows for 2023 in-scope customers |
| 2026-10-06 | CLV = historical spend to date (no forecast); tiers High top 20 % / Medium mid 60 % / Low bottom 20 %, re-ranked daily among in-scope customers; RFM window N = 90 days; churn "at risk" > 45 days; all thresholds in config | Requirements doc defines CLV as aggregate total spend per customer and gives no prediction method; 45 days is the doc's example threshold |
| 2026-10-06 | `dim_date` generated in PySpark for the full order range (2020–2024); holiday flags taken from source `date_dim` where available (2023), null otherwise | All years are loaded but source `date_dim` covers 2023 only; without generated dates, pre-2023 facts would have no matching date |
| 2026-10-07 | (A) Streamlit dashboard runs on Amazon ECS Fargate; same Docker image locally | No server to patch; can be scaled to 0 when not demoing |
| 2026-10-07 | (B) Failure alerts: CloudWatch alarms → SNS email | Production standard; failed runs must not go unnoticed |
| 2026-10-07 | (C) Extract from SQL Server with a Glue PySpark job over JDBC (TLS, `encrypt=true`); password from Secrets Manager | Keeps all logic in PySpark, one tool for every step; DMS would add a service with non-PySpark logic |
| 2026-10-07 | (D) Final DAG step runs PySpark data-quality checks (row-count reconciliation, revenue tie-out across facts/aggregates, unique and non-null keys, quarantine rate); results in `ops.dq_results`; a failed check fails the run | Quarantine catches bad rows; DQ checks catch bad loads. Dashboard keeps the last good data. Great Expectations excluded by the tool rule |
| 2026-10-07 | `ops` database holds pipeline bookkeeping: `ops.watermarks`, `ops.pipeline_runs`, `ops.dq_results` | Separates data about the pipeline from business data |
| 2026-10-07 | Cost estimate in `docs/03_architecture/cost_estimate.md` (us-east-1 list prices from the AWS Price List API) | As designed 24/7 ≈ $455/mo (79 % idle MWAA small); optimized 24/7 ≈ $307/mo; chosen setup ≈ $22 per working month (40 h deployed), ≈ $2 idle; local $0 |
| 2026-10-07 | (E) Provisioned MWAA **micro** environment, created and destroyed with `PipelineStack`; not MWAA Serverless | Serverless (≈ $1/mo) would mean YAML DAGs, Airflow 3 and no Airflow UI in AWS. Provisioned keeps Python DAGs + UI (industry standard, matches the official local MWAA image) for ≈ $12 more per working month. Full deploy ≈ 40 min |
| 2026-10-07 | (F) AWS region us-east-1 | 10–14 % cheaper than us-west-1 (the local CLI default); new features first. Set region explicitly in CDK and CLI profile |
| 2026-10-07 | (G) Two CDK stacks: permanent `DataStack` (S3 lake, KMS key, ECR, RDS snapshot) + disposable `PipelineStack` (VPC, NAT, RDS, Glue, MWAA, Fargate, ALB, alarms), deployed only for testing/demos; one always-on week before submission (≈ $71) | Stateful/stateless split is standard practice; rebuild-from-code proves IaC completeness; final week shows unattended daily operation |
| 2026-10-07 | (H) Glue Flex execution class for scheduled daily jobs, configurable per job | −34 % on Glue; standard class for urgent reruns |
| 2026-10-07 | (I) Full 2023 replay runs locally; on AWS one full initial load + ~14-day replay | Full replay on AWS ≈ $104–131 and ~5 days; backfill skills learned locally for free |
| 2026-10-07 | Stay on Glue 5.1 (not 6.0) | Glue 6.0 (Spark 4.1, Python 3.13, 30 % cheaper) has no local Docker image yet; newest is `aws-glue-libs:5.1.0`. Revisit when published |
| 2026-10-07 | Free cost guardrails: AWS Budgets alert $20/mo, Cost Anomaly Detection, tags `project`/`env`/`stack` on every resource | Catch forgotten resources early |
| 2026-10-09 | `silver.order_items` spec approved: 25 columns (keys, time, item, flags, audit); grain one row per `order_id + lineitem_id` | Same grain as source; cleaned, typed, flagged; nothing removed for business reasons |
| 2026-10-09 | Timestamp parse format `yyyy-MM-dd'T'HH:mm:ss[.SSS]X`; Spark session time zone UTC; `business_date` and `order_hour_local` from `America/New_York` | Covers all 4 source formats (no fraction 187, 1 digit 1,853, 2 digits 18,131, 3 digits 183,348); session TZ makes local and AWS identical |
| 2026-10-09 | Guests: `user_id` NULL in silver; `'GUEST'` only in gold | Silver stays faithful to source |
| 2026-10-09 | `item_name` trimmed + spaces collapsed (427 rows) for display; `item_name_key` = lowercase for grouping (432 → 396 items); `item_category` URL fragment removed (98 rows) with `is_category_repaired` audit flag | Findings 27, 33, 34 |
| 2026-10-09 | `printed_card_number` is sensitive: string, kept in silver only, never in gold or dashboard | Tokenized card number; gold only needs `is_loyalty` |
| 2026-10-09 | Quarantine (broken rows): missing key/restaurant, bad timestamp, price not number or < 0, quantity not whole or < 1, `is_loyalty` not TRUE/FALSE, currency not USD. Today: 1 row (finding 8). `$0` items and bulk lines stay as normal rows | Quarantine = row unusable; flag = valid row a business rule may exclude |
| 2026-10-09 | Silver dedup: keep newest `_ingested_at` per key; MERGE updates only when `_row_hash` (SHA-256 of business columns) changed; no partitioning on silver | Lookback re-reads rows; ~200k rows is too small to partition (small-files problem) |
| 2026-10-09 | Money columns are `DECIMAL(10,2)`, never float | Sums must be exact to the cent |
| 2026-10-09 | `silver.order_item_options` key: `option_key` = SHA-256(order_id, lineitem_id, group, name, price, `option_seq`), `option_seq` = copy number among identical rows within a batch | Source has no option id; 2,915 rows are exact copies (616 groups, max 10, 0 in 2023). Numbering identical copies is deterministic, so lookback re-reads match existing keys |
| 2026-10-09 | Options extracted through their parent order: options of every order in the order-items window (watermark − 3 days) | Options table has no timestamp; line and options always arrive in the same batch. Adds to the 3.2 extract design |
| 2026-10-09 | Orphan options (parent line not in silver) quarantined (28 rows today); DQ step counts orphans directly in SQL Server | Parent-based daily extract cannot see orphans (finding 29) |
| 2026-10-09 | Negative `option_price` allowed and flagged `is_discount` (0 today); repeated copies kept and flagged `is_repeated_option`, gold counts each copy by default with a config switch (Q9) | Requirements define negative prices as discounts; Q9 open |
| 2026-10-09 | Option revenue computed in gold, not silver | Needs `item_quantity` from the parent line |
| 2026-10-09 | Known limitations recorded: source deletes not detected (CDC out of scope); options added > 3 days after the order would be missed | Documented for the production-rollout section |
| 2026-10-09 | Specs collected in `docs/03_architecture/Step3_Data_Model.md` (becomes the data-model section of the solution design doc) | Approved specs must live in an SME-facing document, not only in chat/CLAUDE.md |
| 2026-10-09 | `silver.date_dim` approved: typed copy, full reload, `week` renamed `iso_week`; gold date dimension adds ISO year | Source week is ISO 8601: 1–2 Jan 2023 are week 52 of ISO year 2022; grouping by year + week would mix them with late December |
| 2026-10-09 | `silver.quarantine` approved: one table for all sources, MERGE on `source_table + record_hash`, `times_seen`, first/last seen, `status` open/resolved | Lookback re-reads broken rows daily; append would duplicate them. Expected after first load: 29 rows |
| 2026-10-09 | `customer_daily_snapshot` approved: customer × day, dense from first in-scope order, 2,283,740 rows for 2023 (10,512 customers, $673,614.04) | Primary goal: CLV evolving daily |
| 2026-10-09 | CLV = 2023 spend to date only | User decision: work on 2023 orders only; not an SME question |
| 2026-10-09 | CLV tier by `cume_dist`, re-ranked daily, ties share a tier (≈ not exactly 20/60/20) | 311 customers tie at $10.99 at the Low cut-off |
| 2026-10-09 | Churn status active ≤ 45 / at_risk 46–90 / lapsed > 90 days (SME Q13) | Single > 45-day rule flags 77 % (8,103) at year end; 49 % are one-time buyers |
| 2026-10-09 | RFM fixed bands from config (R days 7/30/45/90; F orders 0/1/2/3–5/6+; M $0/15/30/60) and segments VIP / New / Churn Risk / Regular | Quintiles impossible: 82.5 % have 0–1 orders in 90 days; fixed bands are stable over time |
| 2026-10-09 | Snapshot fully rebuilt each run, partitioned by month of `snapshot_date`; DQ tie-out against `fact_order` | Cheap at 2.3 M rows; late data corrects history |
| 2026-10-09 | Gold facts approved: `fact_order_line` (line grain; `customer_id` = user_id or 'GUEST'; option revenue = Σ price × item qty, repeated copies counted each, config switch for Q9) and `fact_order` (order grain; 52,015 orders, $746,223.86 in 2023 scope) | Order-level fields never conflict within an order (0 of 131,328) |
| 2026-10-09 | Facts updated by "affected orders" (order_ids with new/changed silver items or options this run) + MERGE; dimensions, aggregates and snapshot rebuilt each run | An added option changes line revenue, so the order is the unit; rebuild is cheap for small tables |
| 2026-10-09 | `dim_item` key = SHA-256(item_name_key + item_category): 444 items; display name = most common spelling | 49 names appear in more than one category |
| 2026-10-09 | `dim_date` generated 2020-01-01 → 2024-12-31 (1,827 days) with `iso_year`; `is_holiday` NULL outside 2023 | Holiday data only for 2023; unknown ≠ false |
| 2026-10-09 | Two sales aggregates: `sales_daily` (date × location × hour, from fact_order, includes order counts) and `sales_daily_category` (date × location × category, from fact_order_line, no order counts); sums only, ratios computed after summing | 24.5 % of 2023 orders span categories: order counts are non-additive across categories |
| 2026-10-09 | `dim_location.is_test_location` (1 location has only test orders); `location_name` empty pending SME Q15 | Source has ids only |
| 2026-10-09 | Design doc states discount analysis is empty until SME Q7 | No negative option prices exist |
| 2026-10-09 | SME questions and their impact figures are 2023-only; questions with no 2023 rows are not asked (Q9, Q12); Q14 removed | User instruction: work only on 2023 orders |
| 2026-10-10 | SME answers: Q1 `restaurant_id` is the location; Q2 `item_price` is the line total; Q4 guests excluded from customer metrics, kept in sales (placeholder confirmed); Q6 Perks app included; Q11b `5ece77fe…` is the only non-customer account | Placeholders become confirmed rules; no design change |
| 2026-10-10 | Q15 dropped (no SME request for names); `location_name` kept in `dim_location` but empty; dashboards show `restaurant_id` when it is NULL | User decision: keep the column, use the ids the data has |
| 2026-10-10 | `config/business_rules.yaml` written by the user and validated (11 sections: scope, test data, customers, revenue, CLV tiers, RFM bands + segments, churn, spend trend, extract lookback, DQ threshold); every rule cites its source (SME answer or assumption) | Step 3.4: SME answers become config edits, not code changes |
| 2026-10-10 | `.claude/` added to `.gitignore` | Claude Code worktrees must not be committed |
| 2026-10-14 | **SME approved Step 3** ("Looks nice"); Step 4 may start | Approval gate passed |
| 2026-10-14 | Q13 confirmed: churn active ≤ 45 / at_risk 46–90 / lapsed > 90 | SME answer |
| 2026-10-14 | Q7 and location names recorded as data limitations; location analysis uses `restaurant_id` | SME instruction |
| 2026-10-14 | Q3 (option per unit) and Q10 (America/New_York) kept as assumptions, labelled "not confirmed by the SME" in docs and config; Q8, Q11a, Q16 unanswered, also kept as labelled assumptions | SME: "proceed with your assumptions but clearly document them" |
| 2026-10-14 | Spark CSV reads use `multiLine=True, escape='"'` | 12 rows have a line break inside a quoted `item_name` (`MANDARIN CARDAMOM\nJUICE`, none in 2023); a plain Spark read returns 203,531 rows instead of 203,519 and shifts columns |
| 2026-10-14 | Local Spark sets `PYSPARK_PYTHON = sys.executable` before the SparkSession starts | Python workers otherwise start the PATH `python3` (3.13) and fail with PYTHON_VERSION_MISMATCH against a 3.11 driver |
| 2026-10-14 | PySpark practice environment `.venv-spark` (Python 3.11.9, pyspark 3.5.6, pandas < 2.3, numpy < 2, Java 17), notebook `scripts/practice/pyspark_basics.ipynb` | Matches Glue 5.1 versions; `.venv` (3.13) stays for analysis |
| 2026-10-15 | Local stack in `docker-compose.yml`: `sqlserver` (SQL Server 2022 Developer, `linux/amd64` via Rosetta, named volume `mssql-data`, healthcheck `SELECT 1`), `spark` (AWS Glue 5.1 image + PyYAML, project bind-mounted at `/home/hadoop/workspace`, idle with `sleep infinity`, jobs via `docker compose exec spark spark-submit`), `spark-history` (Spark History Server on :18080); Airflow added in 4.7 | Same components as AWS; verified on M4: Spark 3.5.6-amzn-1, Python 3.11, Java 17, Iceberg 1.10, mssql-jdbc 11.2.3 all in the Glue image |
| 2026-10-15 | `docker/spark/Dockerfile` = `public.ecr.aws/glue/aws-glue-libs:5.1.0` + `PyYAML==6.0.3`; on AWS PyYAML ships as a pinned wheel via `--additional-python-modules` (AWS-recommended, works in a private VPC) | Glue 5.1 does not include PyYAML (4.0 and 6.0 do); keeps the YAML config with comments |
| 2026-10-15 | `config/environments.yaml` (local vs prod: raw dir, Iceberg catalog `lake` = hadoop folder `lake/` locally / Glue Data Catalog + S3 in AWS, source DB host, certificate trust, password from env var locally / Secrets Manager in AWS); `PIPELINE_ENV` selects the section | Code identical in both environments; tables always named `lake.<layer>.<table>` |
| 2026-10-15 | Shared code: `src/globalpartners/common/config.py` (`pipeline_env`, `load_environment`, `load_business_rules`, fails fast on unknown env) and `common/spark.py` (`build_spark`: UTC, Iceberg extensions, catalog from config; `jdbc_url`: always `encrypt=true`) | Every job starts Spark and reads config the same way |
| 2026-10-15 | Spark UI: Glue image sets `spark.ui.enabled false`; live UI via `--conf spark.ui.enabled=true` on host port 4050 (4040 was taken by the practice notebook); event logs (`/var/log/spark/apps`) kept in named volume `spark-events` and served by the History Server at :18080 | Keep the Spark UI for every finished job to diagnose skew and slow stages; verified a skewed stage shows median 0 vs max 1,800,000 records per task. On AWS: Glue Spark UI from event logs in S3 |
| 2026-10-15 | `.env` (SA password) and `lake/` git-ignored; `.env.example` committed | Secrets and local data never in Git |
| 2026-10-17 | Source tables use typed columns (DATETIME2(3), DECIMAL(10,2), INT, BIT, DATE, VARCHAR/NVARCHAR); CSV text converted once at seed load with explicit formats | User choice A: matches the requirements doc and real systems; the extract's time-window query works on a real timestamp. Silver still validates every value |
| 2026-10-17 | No NOT NULL / key constraints on source tables; indexes on `creation_time_utc` and `order_id` | Source quirks (e.g. the line with no lineitem_id) must reach the pipeline so quarantine is exercised |
| 2026-10-17 | Source layout: `dbo.*` live tables (read by the pipeline), `seed.*` full CSV copy (filled by `load_seed.py`), `dbo.date_dim` loaded directly | Replay copies seed → dbo by business day to simulate daily trading |
| 2026-10-17 | `seed.replay_days(@from_date, @to_date)`: copies whole orders (lines + options) whose New York business date is in range, in one transaction, skipping orders already live | Idempotent (repeat adds 0); options follow their order, as in the extract design |
| 2026-10-17 | Read-only login `etl_reader` (SELECT on `dbo` only; denied on `seed` and on DELETE); password `MSSQL_ETL_PASSWORD` in `.env`; created by `sql/01_create_database.sql` via `sqlcmd -v` | Least privilege: the pipeline never uses `sa` |
| 2026-10-17 | SQL scripts in `sql/` (01 database + login, 02 tables, 03 replay), mounted read-only into the sqlserver container at `/sql` and run with `sqlcmd` | Setup is versioned and re-runnable |
| 2026-10-17 | Extract job `src/globalpartners/jobs/extract_to_bronze.py`: reads `dbo.order_items` after (watermark − `extract.lookback_days`) or everything on the first run, options through their orders (`order_id IN (...)` same window), `date_dim` in full; filters run in SQL Server (JDBC `query` pushdown) | Incremental + lookback design from 3.2; options have no timestamp |
| 2026-10-17 | Bronze tables `lake.bronze.{order_items, order_item_options, date_dim}` are append-only Iceberg tables with source types kept, plus `_batch_id`, `_ingested_at`, `_source_table`; created on first write | Delivery log; lookback re-reads are stored again and de-duplicated in silver |
| 2026-10-17 | Watermark in `lake.ops.watermarks` (source_table, last_loaded_ts, batch_id, updated_at), MERGE-updated last and only forward (`newest > watermark`) | Failure reload: a failed run leaves the watermark, the next run re-reads the window (tested: wrong password → nothing written, watermark unchanged) |
| 2026-10-17 | Pipeline reads SQL Server as `etl_reader` via `reader_user_env`/`reader_password_env` in `environments.yaml` and `MSSQL_ETL_USER`/`MSSQL_ETL_PASSWORD` in the spark container; `sa` (`user_env`) only for setup jobs | Least privilege |
| 2026-10-17 | `--batch-id` argument (default UTC time `YYYYMMDDTHHMMSSZ`); Airflow will pass its run id | Every bronze row traceable to its run |
| 2026-10-17 | Querying locally: lake via `spark-sql` with `--conf spark.sql.catalogImplementation=in-memory` plus the `lake` Iceberg settings; SQL Server via interactive `sqlcmd` or the VS Code "SQL Server (mssql)" extension (`localhost,1433`, trust certificate) | Glue image defaults to the Hive catalog backed by AWS Glue Data Catalog, which fails without AWS credentials |
| 2026-10-19 | Silver job `jobs/bronze_to_silver.py` processes one extract batch (`--batch-id`, default newest in bronze): order lines, then options (parent check needs silver lines), then date_dim | One batch at a time matches the daily DAG; idempotent re-runs |
| 2026-10-19 | Silver code split by responsibility: `common/tables.py` (`merge_into`), `transformations/cleaning.py` (`clean_text`, `collapse_spaces`, `row_hash`, `failed_rules`, `keep_newest`), `transformations/silver_{order_items,order_item_options,date_dim}.py` (`transform` returns good + bad DataFrames, no I/O), `quality/quarantine.py` (`record`, `resolve`) | Small files are teachable one at a time and unit-testable in 4.8 |
| 2026-10-19 | Silver MERGE updates a row only when `_row_hash` changed; `_batch_id` on a silver row = the last batch that changed it | Lookback re-reads rewrite nothing (tested: 430 re-read lines, 0 rewritten); gold can find changed orders by `_batch_id` |
| 2026-10-19 | Quarantine keeps the original bronze row as JSON captured before any cleaning; MERGE on `source_table + record_hash`; `times_seen` grows only on a new batch; `resolve` sets `status = resolved` when a valid row with the same key reaches silver | Spec section 6; re-running a batch does not inflate counts |
| 2026-10-19 | Source is typed (decision A), so silver validates types it receives (NULL/range checks) instead of parsing text; timestamp/boolean/decimal parsing happens once in `load_seed.py` | Follows from 4.2 |
| 2026-10-22 | Gold job `jobs/silver_to_gold.py`: affected orders = order_ids of silver lines or options whose `_batch_id` is the batch; their lines/options rebuilt into `fact_order_line` and `fact_order` and MERGEd; 5 dimensions rebuilt with `createOrReplace` | Silver `_batch_id` changes only on real changes, so lookback re-reads cause no gold work (tested: +$1.00 source change → 1 order, 2 lines rebuilt; time travel $13.98 → $14.98) |
| 2026-10-22 | Gold code: `transformations/gold_dimensions.py` (`item_key`, `dim_customer` + GUEST row, `dim_location`, `dim_item` display name = most common spelling, `dim_app`, `dim_date` generated with ISO year/week and holidays from source), `transformations/gold_facts.py` (`fact_order_line`, `fact_order`) | Spec sections 8–9 |
| 2026-10-22 | Line revenue = `item_price` + Σ option_price × item_quantity (config `option_price_times_item_quantity`), repeated options per config `repeated_options`; money columns `DECIMAL(12,2)` in gold | Q3 assumption kept configurable; totals need more digits than prices |
| 2026-10-22 | Run log: `common/run_log.py` context manager `logged_run` writes one row per job run to `lake.ops.pipeline_runs` (run_id, job, started/finished, SUCCESS/FAILED, rows_in/out/quarantined, error) in `finally`, re-raising the job's error; used by all four jobs | Audit trail; a crashed job still leaves a FAILED row; a logging error never hides the job's error |
| 2026-10-22 | `read_source` moved to `common/source.py` (used by extract and DQ checks) | Shared code lives in `common/` |
| 2026-10-22 | DQ job `jobs/dq_checks.py` + `quality/checks.py`: 19 checks (source→bronze→silver+quarantine counts, revenue Σ orders = Σ lines, gold item revenue = silver, every silver line in gold, unique non-null keys ×4, fact→dimension ×5, quarantine rate ≤ config, loyalty card ⇔ flag, dim_date ISO week = source, source orphan options as WARN); results replace the batch's rows in `lake.ops.dq_results`; any FAIL raises → exit code 1 | Decision D; scheduler stops and alerts instead of publishing wrong numbers |
| 2026-10-24 | Local Airflow = official `aws/amazon-mwaa-docker-images` image, Airflow 3.3.1 (Python 3.12), built on the Mac (clone outside the repo, `create_venvs.py`, `Dockerfile.base` + `Dockerfile-dev`); services in `docker-compose.yml`: `airflow-db` (Postgres 13), `airflow-sqs` (ElasticMQ, stands in for SQS), `airflow-migratedb`, `airflow-webserver` (:8080, `testing` auth, no login), `airflow-scheduler`, `airflow-worker` | Same image MWAA runs; Celery over SQS as in AWS |
| 2026-10-24 | Airflow packages in `airflow/requirements.txt` with the Airflow 3.3.1 constraints file + `docker==7.2.0`; Fernet key in `.env` (`AIRFLOW_FERNET_KEY`, JSON `{"FernetKey": …}`); all 18 `MWAA__LOGGING__*` variables set (CloudWatch off, INFO) | The MWAA entrypoint fails with KeyError without the logging variables; constraints pin versions like MWAA does |
| 2026-10-24 | DAG `dags/globalpartners_daily.py`: replay_day → extract_to_bronze → bronze_to_silver → silver_to_gold → dq_checks; daily 06:00, `catchup=False`, `max_active_runs=1`, 2 retries × 2 min; logical date = business day (`ds`), `run_id` = `--batch-id` | One business day at a time, in order; a failed task stops the run before data is published |
| 2026-10-24 | Locally tasks run jobs with the docker SDK `exec` into the `spark`/`sqlserver` containers (worker mounts `/var/run/docker.sock`, `group_add: ["0"]`); `PIPELINE_ENV=prod` path raises until Step 4.9 (GlueJobOperator) | Reuses the existing containers; local only, never in AWS |
| 2026-10-24 | Fix: `dim_date` year range = order dates ∪ source calendar dates | On a run with no orders yet, `silver_to_gold` crashed (`DATE'None-01-01'`); found by the Airflow test |
| 2026-10-10 | Step 3 package: `docs/03_architecture/Step3_Solution_Design.md` (requirements traceability, architecture, data flow, data model, business rules, security, operations, deployment, cost, limitations, open questions, approval table) + `README.md` index | Requirements doc deliverable: solution design document for SME sign-off |

## Source file baseline (Step 1)

| File | Rows | Size (bytes) | SHA-256 |
|---|---|---|---|
| order_items.csv | 203,519 | 37,894,585 | `03c8bf5030093e649b4f1d8da152e95dda6fbfb53d0978e1a367ff8621651d63` |
| order_item_options.csv | 193,017 | 17,604,850 | `9bd8a388b48d09e00bfef16dbe84b9953d8b59ce416d1af46614626573d0f64d` |
| date_dim.csv | 365 | 15,901 | `4168f66d142e8263ee5ed4e223399d62eb7e7eea4c5b5f19f8dbc9c1bf9a1ea1` |

## Data quality findings

| # | File | Finding | Status |
|---|---|---|---|
| 1 | order_items, options | Column headers uppercase; doc shows lowercase | Resolved: normalize on read |
| 2 | order_items | `creation_time_utc`: 187 values lack milliseconds (valid ISO 8601) | Resolved: format="ISO8601" |
| 3 | date_dim | `date_key` is DD-MM-YYYY; pandas guessed MM-DD | Resolved: format="%d-%m-%Y" |
| 4 | order_items | `order_id + lineitem_id` unique | Confirmed: join key |
| 6 | order_items | `user_id` blank in 17,808 rows (8.7%) | Resolved: SME Q4, guests excluded from customer metrics, kept in sales |
| 7 | order_items | Blank `printed_card_number` ⇔ `is_loyalty` FALSE, zero exceptions | Resolved: blanks valid |
| 8 | order_items | 1 malformed row: blank lineitem_id/category/name, quantity 0, price $4.39 (2021) | Open: quarantine |
| 9 | options | Identical options repeated on one line (594 groups on qty-1 lines) | Open: SME Q9 |
| 10 | date_dim | `holiday_name` blank in 353 rows (12 holidays) | Expected |
| 11 | order_items | Orders span 2020-04-21 → 2024-02-21; date_dim covers 2023 | Resolved: 2023-only scope |
| 12 | order_items | 826 rows from `Alltown Fresh - DEVELOPMENT` (741 orders, 115 users, $7,221.54 item revenue) | Resolved: SME confirmed test data; exclude from metrics |
| 13 | order_items | `Alltown Neighborhood Perks` app, 1,270 rows | Resolved: SME Q6, include |
| 14 | order_items | 131,328 orders, avg 1.55 items; max 61 | Info |
| 16 | order_items | 20,174 identified customers | Info |
| 17 | order_items | Two user_ids with 2,400+ line items | Resolved: SME confirmed `5ece77fe…` is faulty data (non-customer), excluded from customer metrics; `5f1b00e5…` is a normal customer in 2023 (42 orders, $466) |
| 18 | all | Booleans stored as "TRUE"/"FALSE" strings | Pipeline converts to boolean |
| 19 | order_items | Currency USD only | Info |
| 20 | order_items | `lineitem_id` unique across file | Info |
| 21 | options | `option_quantity` always 1 | Info |
| 22 | options | Options cover 78,600 orders (60%), 102,697 line items (50%), excluding orphans | Left join required |
| 23 | options | No negative `option_price` values (doc: negative = discount) | Open: SME Q7 |
| 24 | order_items | Qty 300–500 lines (e.g. $5,000 Korean Kimchi), not test data | Open: SME Q12 |
| 25 | order_items | 156 regular menu items at $0 | Open: SME Q8 |
| 27 | order_items | Inconsistent item_name casing/spelling | Open: normalize |
| 28 | order_items | `item_price` is line total, not unit price | Resolved: SME confirmed (Q2); revenue = item_price |
| 29 | options | 28 orphan options (15 line keys); their order_ids are absent from order_items entirely, ids suggest late Feb 2024 (extract cutoff) | Open: quarantine |
| 30 | options | Options recorded once per line; `option_price` is a unit price | Info |
| 31 | order_items | 2023 population (America/New_York): 80,665 lines, 52,641 orders, 10,604 customers, 21 locations, $752,776.30 revenue. After excluding DEVELOPMENT: 79,965 lines, 52,015 orders, 10,513 customers, 20 locations, $746,223.86 | Info |
| 32 | order_items | In scope (2023, excl. test): 4 Perks rows, 1 $0 item, 0 bulk lines (max qty 27), 0 repeated options on qty-1 lines, 2 name casing variants, 1,136 rows from top-2 user_ids (1,090 from one) | Info: Q6, Q8, Q9, Q12 have little 2023 impact; Q4, Q11 matter |
| 33 | order_items | 36 item names have casing variants (432 → 396 after lowercasing) | Open: normalize |
| 34 | order_items | `item_category` corrupted with pasted admin URLs: 96 rows in scope (70 `BBQ Plates`, 26 `Drip Coffee`), e.g. `Drip Chttps://www.opendining.net/...#offee`; removing the URL fragment always yields an existing valid category | Resolved: repaired + flagged in silver; in Step 2 notebook (section 11) and report (2026-10-10) |
| 35 | order_items | Loyalty status changes per customer: in scope (excl. guests and the non-customer account), 1,913 of 10,512 customers (18.2 %) have both loyalty and non-loyalty orders; 1,808 started non-loyalty (joined later); max 9 switches | Resolved: loyalty per order and per day in the data model; in Step 2 notebook (section 11) and report (2026-10-10) |

## Open questions for SME

1. ~~Is `restaurant_id` the `location_id` referenced in Step 5?~~ **Answered 2026-10-10: yes.**
2. ~~Data shows `item_price` is the line total, contradicting the doc. Please confirm.~~ **Answered 2026-10-10: line total.**
3. Is `option_price` charged × `item_quantity` (assumption) or once per line? 2023 impact: $2,739.90 (0.37 %). **2026-10-14: SME said proceed with the assumption; documented as unconfirmed.**
4. ~~Should orders without a `user_id` be excluded from customer metrics but kept in sales/location revenue?~~ **Answered 2026-10-10: yes.**
5. ~~Exclude `Alltown Fresh - DEVELOPMENT` orders (826 rows) as test data?~~ **Answered 2026-10-04: yes, exclude.**
6. ~~What is the `Alltown Neighborhood Perks` app; include it?~~ **Answered 2026-10-10: include.**
7. ~~No negative `option_price` values exist. How are discounts represented?~~ **Answered 2026-10-14: data limitation; document it.**
8. Is the $0 menu item a comp, reward, or discount? (2023: 1 line.)
9. ~~Are repeated identical options on one line item extras or duplicate errors?~~ **Not asked: 0 cases in 2023.**
10. Which time zone defines the business day (timestamps are UTC)? **2026-10-14: SME said proceed with America/New_York; documented as unconfirmed.**
11. ~~Are the two user_ids with 2,400+ line items real customers?~~ **Answered 2026-10-05: `5ece77fe…` is faulty data, not a real customer; exclude from customer metrics, keep revenue in sales. No other non-customer accounts named.**
12. ~~Are qty 300–500 lines legitimate (catering, bulk)?~~ **Not asked: none in 2023 (max quantity 27).**
13. ~~Churn: use three statuses active ≤ 45 days, at_risk 46–90, lapsed > 90?~~ **Answered 2026-10-14: yes.**
14. ~~Should CLV include spend before 2023?~~ **Not a question: user decision, CLV counts 2023 orders only (2023 is the scope).**
15. ~~Location names?~~ **Removed 2026-10-10: use the location ids as they are.**
16. Are orders ever edited or deleted in SQL Server after placement, and can options be added to an order days later? *(Placeholder = no deletes; changes within the 3-day lookback)*
- Q11 follow-ups: (a) are `5ece77fe…` orders real sales wrongly attributed (keep revenue) or orders that never happened (remove from sales)? *(Placeholder = real sales)*; ~~(b) any other known non-customer accounts?~~ **Answered 2026-10-10: just the one.**

## Change log

- **2026-10-01**
  - Created project folder, `.venv`, `requirements.txt`, folder structure, `.gitignore`
  - Wrote `verify_raw_file.py`: checksum, row count, schema, blanks, duplicates, parse checks, date ranges
  - Fixed: duplicate-key check crash, lowercase normalization, `Path(__file__)` paths, explicit date formats
  - Step 1 complete; findings in `docs/01_data_verification/`
- **2026-10-04**
  - Step 2 notebook: profiled columns, outliers, loyalty crosstab, revenue formula tests, option recording, revenue impact
  - SME confirmed 2023-only scope
  - Step 2 findings in `docs/02_data_analysis/Step2_Initial_Data_Analysis.md`
  - Initialized git repo; first commit `865e713`
  - Rebuilt `scripts/step2/data_analysis.ipynb` (48 cells): fixed `option_once` NameError and `pd.DataFrame()` annotation; added typed copies, dataset profile, DQ checks (malformed row, orphans, option coverage, apps, heavy users, bulk lines, item names), line revenue with working formula, 2023 population under UTC vs local time, date_dim coverage
  - 2023 volume measured (finding 31); date_dim covers every 2023 order date
  - SME confirmed DEVELOPMENT app rows are test data: exclude from metrics (Q5 closed, finding 12 resolved)
  - Notebook: added test-data exclusion and in-scope impact cells (50 cells); executed with outputs saved, 0 errors
  - Step 2 report updated: new section 6 (2023 population + in-scope impact of open findings); finding 12 resolved; Q5 answered; corrected option coverage (102,697 / 78,600), blank user_id (8.75%), all-years revenue ($1,876,434.32); sections renumbered
  - Drafted SME questions Q4 (guest orders) and Q11 (heavy accounts) with in-scope evidence
  - Step 3 started with placeholders for Q4 and Q11
  - Step 3.1 tech decisions: tool selection per requirements doc, RDS SQL Server Express, MWAA (Airflow), local-first Docker, Glue 5.1, Iceberg, CDK
  - Decided two IaC versions: v1 CDK on `main` (focus now), v2 Terraform on branch `iac/terraform` later
  - Step 3.2 data flow confirmed: medallion on Iceberg, incremental + lookback, MERGE, quarantine, audit tables, config rules, replay script
  - Step 3.3 prep: found findings 34 (URL-corrupted item_category) and 35 (customers' loyalty status changes over time)
- **2026-10-05**
  - SME answered Q11: `5ece77fe…` confirmed faulty data; Q11 placeholder becomes the confirmed rule; finding 17 resolved
  - Q11 part 3 (other non-customer accounts) unanswered: assume none
  - Remaining Step 3 placeholder: Q4 (guest orders)
- **2026-10-06**
  - Step 3.3 data model walkthrough: real order `64d3b041…` and customer `642d6946…` (6 orders, $74.94 CLV in 2023) traced through the source files; concepts (grain, bronze/silver/gold, fact vs dimension, star schema, keys, snapshot, RFM, SCD2) explained on a 5-row toy dataset
  - Approved 5 data-model decisions: natural keys + GUEST row, loyalty on facts/snapshot (no SCD2), dense daily snapshot, historical CLV with 90-day RFM and 45-day churn, generated `dim_date`
  - Next: column-by-column design of `silver.order_items`
- **2026-10-07**
  - Pipeline diagram walkthrough (12 components); explained ops tables, DQ checks, TLS, OIDC
  - Approved A (Streamlit on ECS Fargate), B (CloudWatch + SNS alerts), C (Glue JDBC extract), D (DQ check step + `ops.dq_results`)
  - Wrote `docs/03_architecture/cost_estimate.md`; found Glue 6.0 (30 % cheaper, Python 3.13) has no local Docker image yet, and MWAA Serverless (≈ $1/mo vs $212–358/mo provisioned)
  - Approved E–I: provisioned MWAA micro in disposable PipelineStack (changed from Serverless recommendation after weighing production learning), us-east-1, two CDK stacks + one always-on week, Glue Flex, full replay locally; cost estimate updated (≈ $22 working month, ≈ $71 final week)
- **2026-10-08**
  - Pipeline architecture diagram drawn in draw.io by the user: `docs/03_architecture/global-partner-pipeline-architecture.drawio` + `.png` (commit `bd9f142`)
  - Reviewed in 3 rounds against SME requirements (SQL Server, AWS only, PySpark, scheduling, encryption, failure reload, CI/CD + OIDC): all visible. Fixes made: MWAA connected to the control line and the 5 Glue jobs, OIDC label, light-mode colours, title, gold_metrics two-way arrow, label typos
  - Optional cosmetics left: 3 labels crossed by lines, 3 ops arrows black instead of grey, catalog bar fill
  - Lesson: draw.io dark mode saves colours as `light-dark()` pairs that turn black in light-mode exports; draw in light mode
  - Next: Step 3.3 `silver.order_items` column spec
- **2026-10-09**
  - `silver.order_items` spec approved (rules measured on real data: 1 row quarantined; flags 2023/all: guest 6,395/17,808, test 700/826, non-customer 1,090/2,454)
  - `silver.order_item_options` spec approved; found options have no timestamp (extract through parent order) and no unique id (SHA-256 key with copy number)
  - Created `docs/03_architecture/Step3_Data_Model.md` with both approved silver specs; proposed `silver.date_dim` (found `week` is the ISO week: 1–2 Jan 2023 = week 52) and `silver.quarantine` (MERGE on source_table + record_hash, sightings counted, status open/resolved)
  - `silver.date_dim` and `silver.quarantine` approved: silver layer complete
  - `customer_daily_snapshot` approved after simulating 2023 on real data; added SME Q13 (churn statuses) and Q14 (CLV scope)
  - Gold facts, dimensions and sales aggregates approved: data model fully specified; added SME Q15 (location names)
  - Data-model diagram generated by Claude at the user's request: `docs/03_architecture/global-partner-data-model.drawio` (10 tables, 10 one-to-many relationships, 3 built-from arrows; layout checked with a rendered preview). PNG export pending (draw.io desktop not installed)
  - Compiled all open SME questions into one email (16 incl. new Q16 source edits/deletes and Q11 follow-ups a/b), grouped by 2023 impact
  - Corrected SME email to 2023-only figures (user instruction): dropped Q9, Q12, Q14
- **2026-10-10**
  - SME answers: Q1 yes, Q2 line total, Q4 yes, Q6 include, Q11b only one account; Q15 removed (use ids)
  - Kept `location_name` in `dim_location` (empty, ids shown); diagram unchanged
  - Outstanding SME questions: Q3, Q7, Q8, Q10, Q11a, Q13, Q16
  - Data-model PNG committed (`9cb5800`); `config/business_rules.yaml` + `.gitignore` committed (`199710a`): Step 3.4 done
  - Drafted `Step3_Solution_Design.md` and `README.md` for SME review (2023 figures only)
  - Step 3 package sent to the SME with a walkthrough video (shared by link; `*.mov`/`*.mp4` ignored in Git after a 147 MB commit was undone before push)
  - Step 2 notebook: added findings 34 and 35 (2023 scope) in section 11, summary updated; Restart & Run All, 56 cells, 0 errors
  - Step 2 report: findings 34 and 35 added; SME answers Q1, Q2, Q4, Q6, Q11 recorded; open findings now only 23 (Q7) and 25 (Q8)
- **2026-10-11 to 2026-10-14**
  - PySpark practice sessions 1–3 (read, types, filter; groupBy, join, Window, cume_dist; mini daily snapshot with sequence/explode and rangeBetween); all results matched the design numbers (2,283,740 snapshot rows, $673,614.04 CLV, churn 2,409/1,553/6,550, tiers 2,103/6,604/1,805)
  - Found: Spark needs `multiLine=True, escape='"'` for order_items.csv; `PYSPARK_PYTHON` must point to the 3.11 kernel
  - **SME approved Step 3 (2026-10-14).** Q13 confirmed; discounts and location names documented as data limitations; Q3, Q10 (and unanswered Q8, Q11a, Q16) labelled as unconfirmed assumptions in the design doc, data model and config
  - Step 4 started
- **2026-10-15**
  - Step 4.1 local foundation done (commit `253e2e4`): verified on M4 that SQL Server 2022 runs under Rosetta, the Glue 5.1 image is native arm64 with Spark 3.5.6 / Python 3.11 / Java 17 / Iceberg 1.10 / SQL Server JDBC driver; JDBC connection encrypted; Iceberg MERGE idempotent and time travel work locally
  - Smoke test (`src/globalpartners/jobs/smoke_test.py`) passes: config loads, 203,519 raw rows, encrypted SQL Server connection, Iceberg write/read
  - Found and fixed: PyYAML missing in Glue 5.1 (Dockerfile); port 4040 in use (live UI on 4050); Spark UI disabled in the Glue image (History Server added)
  - Teaching change: build steps now given one file at a time, in order, with a check (user feedback)
- **2026-10-17**
  - Step 4.2 source database done (commit `2316935`): seed load 203,519 / 193,017 / 365 rows with money totals identical to the CSVs; known order time, malformed row, 12 line-break names and loyalty flags verified in SQL Server
  - Replay of 2023-01-01: 63 orders, 120 lines, 105 options (matches pandas); repeat run adds 0; `etl_reader` reads dbo, denied on seed and DELETE
  - Explained to the user: Docker/Compose, shell commands, and how `.env` → Compose → container env vars → SQL Server / Python `os.environ` → JDBC over the Docker network connect
  - Gotcha recorded: SQL Server applies `MSSQL_SA_PASSWORD` only on first start (stored in the `mssql-data` volume); changing `.env` later needs `docker compose down -v`
  - Step 4.3 extract job done (commit `98b8d95`). Tested in scratch: first run 120 / 105 / 365 rows, watermark 2023-01-01 23:14:44.948; after replaying 2 Jan the lookback run re-read both days (279 / 278) and moved the watermark to 2023-01-03 03:01:45.596; a no-new-data run left it unchanged; a failed login wrote nothing
  - User ran the first extract on the real stack; a typo (`batch_id` instead of `_batch_id`) was fixed before commit; the existing local bronze tables still have the old column and will be rebuilt in the planned from-scratch end-to-end run
  - Deferred by the user: Step 4.3's 2 Jan lookback demo on the real stack, to be done in the from-scratch run once the whole pipeline exists
- **2026-10-19**
  - Step 4.4 bronze → silver done (commit `ea67336`). Tested in scratch on the full history (user's own code synced in): 203,518 valid lines + 1 quarantined (the 2021 malformed row, reasons "missing lineitem_id; bad item_quantity", original JSON kept), 192,989 options (unique `option_key`, 2,915 repeated rows, max copy 10), 365 dates with `iso_week`; flags match the spec (2023: guest 6,395 / test 700 / non-customer 1,090); 2023 in scope 79,965 lines, 52,015 orders, 20 locations, item revenue $711,616.66 (= pandas); no line breaks or URLs left; known order 15:26 UTC → 11:26 New York
  - Bugs found while testing and fixed before handing over: quarantine JSON referenced renamed columns (now captured first); `is_test_data` NULL-safe; `_record` dropped from date_dim output
  - On the real stack (only 2023-01-01 live): lake rebuilt (old `batch_id` column), extract 120 / 105 / 365, silver 120 / 105 / 365 valid, 0 quarantined
  - Planned with the user: once the whole pipeline exists, a guided end-to-end session from an empty database and lake, browsing inputs in VS Code (mssql extension), running job by job, and line-by-line debugging of the jobs in the Spark container (VS Code attach; to be configured then)
- **2026-10-22**
  - Step 4.5 silver → gold done (commit `2cfc7b1`). Tested in scratch (full history): 2023 in scope 52,015 orders, Σ order_revenue = Σ line_revenue = $746,223.86 (items $711,616.66 + options $34,607.20); guests 4,492 / $60,247.36; faulty account 937 / $12,362.46; customer revenue $673,614.04 over 10,512 customers; dims customer 20,175 (incl. GUEST), location 28 (1 test-only), item 444, app 3, date 1,827; 0 fact keys missing from any dimension; ISO weeks match the source (2023-01-01 = ISO 2022-W52)
  - On the real stack: silver had never actually run (error hidden by `2>/dev/null`); ran silver (120 / 105 / 365) and gold (63 orders, 120 lines, $1,078.19, dims 54 / 12 / 40 / 1 / 365). Lesson for the user: re-run without `2>/dev/null` when output is missing
  - Step 4.6 DQ checks + run log done (commit `b2c69de`). Tested in scratch: normal cycle 19/19 PASS, all jobs SUCCESS; simulated bad load (58 gold lines deleted) → 3 checks FAIL, exit code 1, run log FAILED with reason; Iceberg `CALL lake.system.rollback_to_snapshot` restored the table and checks passed again
  - Real stack, quiet-day batch `day2`: extract re-read 590 rows (lookback), silver 120 valid, gold 0 affected orders, dq 19/19 PASS ($1,078.19 both ways); all four jobs SUCCESS in `ops.pipeline_runs`
  - User now copy-pastes during the build; build-step messages kept short; deep understanding deferred to the end-to-end debugging session
- **2026-10-24**
  - Step 4.7 Airflow done (commit `79bfeff`). Scratch test from empty source + lake: 2023-01-01 and 2023-01-02 runs all SUCCESS, 19/19 DQ PASS; empty-day run failed 3 tries in `silver_to_gold` (retries work, `dq_checks` upstream_failed) → `dim_date` fix → success
  - User's stack: unpausing created today's scheduled run (empty replay, all green, 0 affected orders); manual run for 2023-01-02: 96 orders, $1,424.16, 19/19 PASS; 2023-01-01 unchanged (63 orders, $1,078.19)
  - Lessons: a DAG file without the final `globalpartners_daily()` call parses with 0 DAGs and no error; the UI trigger uses the browser time zone (06:00 Pacific = 14:00 UTC, `ds` unchanged); `docker exec … airflow` CLI skips the MWAA entrypoint (no DB config), use the UI or REST API
  - Next: Step 4.8, pytest unit tests + GitHub Actions CI
