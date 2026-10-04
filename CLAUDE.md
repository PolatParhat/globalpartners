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
| 3 | Pipeline architecture + data model (SME approval) | Not started |
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
| 8 | order_items | 1 malformed row: blank lineitem_id/category/name, quantity 0 | Open: quarantine |
| 9 | options | Identical options repeated on one line (594 groups on qty-1 lines) | Open: SME Q9 |
| 10 | date_dim | `holiday_name` blank in 353 rows (12 holidays) | Expected |
| 11 | order_items | Orders span 2020-04-21 → 2024-02-21; date_dim covers 2023 | Resolved: 2023-only scope |
| 12 | order_items | 826 rows from `Alltown Fresh - DEVELOPMENT` | Open: SME Q5 |
| 13 | order_items | `Alltown Neighborhood Perks` app, 1,270 rows | Open: SME Q6 |
| 14 | order_items | 131,328 orders, avg 1.55 items; max 61 | Info |
| 16 | order_items | 20,174 identified customers | Info |
| 17 | order_items | Two user_ids with 2,400+ line items | Open: SME Q11 |
| 18 | all | Booleans stored as "TRUE"/"FALSE" strings | Pipeline converts to boolean |
| 19 | order_items | Currency USD only | Info |
| 20 | order_items | `lineitem_id` unique across file | Info |
| 21 | options | `option_quantity` always 1 | Info |
| 22 | options | Options cover 60% of orders, 50% of line items | Left join required |
| 23 | options | No negative `option_price` values (doc: negative = discount) | Open: SME Q7 |
| 24 | order_items | Qty 300–500 lines (e.g. $5,000 Korean Kimchi), not test data | Open: SME Q12 |
| 25 | order_items | 156 regular menu items at $0 | Open: SME Q8 |
| 27 | order_items | Inconsistent item_name casing/spelling | Open: normalize |
| 28 | order_items | `item_price` is line total, not unit price | Resolved: revenue = item_price |
| 29 | options | 28 orphan options | Open: quarantine |
| 30 | options | Options recorded once per line; `option_price` is a unit price | Info |

## Open questions for SME

1. Is `restaurant_id` the `location_id` referenced in Step 5?
2. Data shows `item_price` is the line total, contradicting the doc. Please confirm.
3. Is `option_price` charged × `item_quantity` (assumption) or once per line? Impact: $12,455.65 (0.67%).
4. Should orders without a `user_id` be excluded from customer metrics but kept in sales/location revenue?
5. Exclude `Alltown Fresh - DEVELOPMENT` orders (826 rows) as test data?
6. What is the `Alltown Neighborhood Perks` app; include it?
7. No negative `option_price` values exist. How are discounts represented?
8. Are the 156 $0 menu items comps, rewards, or discounts?
9. Are repeated identical options on one line item extras or duplicate errors?
10. Which time zone defines the business day (timestamps are UTC)?
11. Are the two user_ids with 2,400+ line items real customers?
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
  - Pending: 2023 order volume (Cell 9)
