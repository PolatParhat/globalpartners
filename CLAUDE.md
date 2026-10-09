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
| 2 | Initial data analysis | Analysis done; SME questions open |
| 3 | Pipeline architecture + data model (SME approval) | In progress |
| 4 | Build pipeline on AWS | Not started |
| 5 | Metrics (CLV, RFM, churn, trends, loyalty, locations, discounts) | Not started |
| 6 | Streamlit dashboards | Not started |
| 7 | Submission, CI/CD, video | Not started |

## Repo layout

```
globalpartners/
├── README.md                      # Entry point: overview + index of every step
├── CLAUDE.md                      # Running log of decisions and changes
├── requirements.txt
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
| 6 | order_items | `user_id` blank in 17,808 rows (8.7%) | Open: CLV handling (SME Q4) |
| 7 | order_items | Blank `printed_card_number` ⇔ `is_loyalty` FALSE, zero exceptions | Resolved: blanks valid |
| 8 | order_items | 1 malformed row: blank lineitem_id/category/name, quantity 0, price $4.39 (2021) | Open: quarantine |
| 9 | options | Identical options repeated on one line (594 groups on qty-1 lines) | Open: SME Q9 |
| 10 | date_dim | `holiday_name` blank in 353 rows (12 holidays) | Expected |
| 11 | order_items | Orders span 2020-04-21 → 2024-02-21; date_dim covers 2023 | Resolved: 2023-only scope |
| 12 | order_items | 826 rows from `Alltown Fresh - DEVELOPMENT` (741 orders, 115 users, $7,221.54 item revenue) | Resolved: SME confirmed test data; exclude from metrics |
| 13 | order_items | `Alltown Neighborhood Perks` app, 1,270 rows | Open: SME Q6 |
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
| 28 | order_items | `item_price` is line total, not unit price | Resolved: revenue = item_price |
| 29 | options | 28 orphan options (15 line keys); their order_ids are absent from order_items entirely, ids suggest late Feb 2024 (extract cutoff) | Open: quarantine |
| 30 | options | Options recorded once per line; `option_price` is a unit price | Info |
| 31 | order_items | 2023 population (America/New_York): 80,665 lines, 52,641 orders, 10,604 customers, 21 locations, $752,776.30 revenue. After excluding DEVELOPMENT: 79,965 lines, 52,015 orders, 10,513 customers, 20 locations, $746,223.86 | Info |
| 32 | order_items | In scope (2023, excl. test): 4 Perks rows, 1 $0 item, 0 bulk lines (max qty 27), 0 repeated options on qty-1 lines, 2 name casing variants, 1,136 rows from top-2 user_ids (1,090 from one) | Info: Q6, Q8, Q9, Q12 have little 2023 impact; Q4, Q11 matter |
| 33 | order_items | 36 item names have casing variants (432 → 396 after lowercasing) | Open: normalize |
| 34 | order_items | `item_category` corrupted with pasted admin URLs in 98 rows (96 in scope), 3 values, e.g. `Drip Chttps://www.opendining.net/...#offee`; removing the URL fragment always yields an existing valid category | Open: fix in silver with regex (`https?://\S*?#` → ""); not yet in Step 2 notebook/report |
| 35 | order_items | Loyalty status changes per customer: in scope, 1,914 of 10,513 customers (18%) have both loyalty and non-loyalty orders; 1,809 of them started non-loyalty (i.e. joined later); max 9 switches | Info: model loyalty as of each day, not as a fixed customer attribute; not yet in Step 2 notebook/report |

## Open questions for SME

1. Is `restaurant_id` the `location_id` referenced in Step 5?
2. Data shows `item_price` is the line total, contradicting the doc. Please confirm.
3. Is `option_price` charged × `item_quantity` (assumption) or once per line? Impact: $12,455.65 (0.67%).
4. Should orders without a `user_id` be excluded from customer metrics but kept in sales/location revenue? *(Draft sent 2026-10-04; placeholder = yes)*
5. ~~Exclude `Alltown Fresh - DEVELOPMENT` orders (826 rows) as test data?~~ **Answered 2026-10-04: yes, exclude.**
6. What is the `Alltown Neighborhood Perks` app; include it?
7. No negative `option_price` values exist. How are discounts represented?
8. Are the 156 $0 menu items comps, rewards, or discounts?
9. Are repeated identical options on one line item extras or duplicate errors?
10. Which time zone defines the business day (timestamps are UTC)?
11. ~~Are the two user_ids with 2,400+ line items real customers?~~ **Answered 2026-10-05: `5ece77fe…` is faulty data, not a real customer; exclude from customer metrics, keep revenue in sales. No other non-customer accounts named.**
12. Are qty 300–500 lines legitimate (catering, bulk)?

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
