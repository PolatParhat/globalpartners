# Chapter A3: Data engineering concepts

**Time:** 2 sessions. **Goal:** explain, in plain words and with examples from this project, the ideas every data engineering interview asks about.

## 1. What a data engineer does

Moves data from where it is created (apps, databases, files) to where people can trust and use it (dashboards, models), reliably, repeatedly and cheaply. Not "write SQL once", but **keep it working every day**.

## 2. Systems and storage

| Term | Meaning | Here |
|---|---|---|
| **OLTP** | database for running the business: many small reads/writes | SQL Server (the restaurants' orders) |
| **OLAP** | database/engine for analysis: few big reads over many rows | Athena / Spark over the lake |
| **Data warehouse** | structured, modeled, SQL-first store (Snowflake, Redshift) | not used; the requirements ask for a lake |
| **Data lake** | cheap files (S3) in open formats, any structure | S3 |
| **Lakehouse** | lake + table format (transactions, MERGE, time travel) | S3 + Apache Iceberg |
| **Batch vs streaming** | process in scheduled chunks vs continuously | daily batch |

## 3. ETL vs ELT

- **ETL**: Extract → Transform → Load. Transform before loading into the target.
- **ELT**: Extract → Load raw → Transform inside the target. Keeps raw data, lets you re-transform when rules change.
- This project is ELT-style: bronze keeps the raw copy; silver and gold transform it.

## 4. Medallion layers (bronze, silver, gold)

| Layer | Purpose | Rules |
|---|---|---|
| Bronze | exact copy of the source + batch id + load time | append-only; never edit |
| Silver | cleaned, typed, deduplicated, flagged; bad rows quarantined | MERGE on business keys |
| Gold | business-ready: facts, dimensions, metrics | modeled for questions |
| Ops | the pipeline's own logbook (watermarks, runs, DQ results) | written every run |

**Why layers?** Rebuild downstream layers when a rule changes without touching the source; trace any number back to the raw row; isolate failures.

## 5. Loading patterns

- **Full load:** reload everything each time. Simple, expensive, fine for small tables.
- **Incremental load:** load only new/changed rows since last time.
- **Watermark:** a bookmark (the newest timestamp loaded). Move it forward **only after success**.
- **Lookback window:** re-read a few days before the watermark to catch late-arriving rows (this project: 3 days). Safe because writes are MERGE.
- **CDC (change data capture):** the database reports inserts/updates/deletes (SQL Server CDC, Debezium). Needed to detect **deletes**, which a watermark cannot see.
- **Backfill:** re-run history (this project: 1 Jan to 31 Dec 2023 through the same DAG).

## 6. Idempotency and exactly-once

**Idempotent:** running a step twice gives the same result as once. How: MERGE on a key, overwrite a partition, deterministic code, bookmarks that move only on success. This is the central idea of reliable pipelines: **retries must be safe**.

**Delivery guarantees:** at-most-once (may lose), at-least-once (may duplicate), exactly-once (the effect happens once; in practice = at-least-once + idempotent sink).

## 7. Modeling: star schema

- **Fact table:** measurable events (orders, order lines). Foreign keys + numbers.
- **Dimension table:** descriptions (customer, location, item, date).
- **Grain:** what one row means. State it first. `fact_order_line` = one row per order line; `fact_order` = one per order; `customer_daily_snapshot` = one per customer per day. Mixing grains double-counts revenue.
- **Surrogate vs natural keys:** a generated key vs the business id.
- **Slowly changing dimensions (SCD):** how to handle changing attributes. Type 1 overwrite; Type 2 new row with valid-from/valid-to dates (keeps history); Type 3 extra column for the previous value. Here, history lives in the daily snapshot instead.
- **Snowflake vs star:** normalized dimensions vs flat dimensions. Star = simpler queries.
- **Normalization vs denormalization:** OLTP normalizes (no duplication); analytics denormalizes (fewer joins).

See `docs/03_architecture/Step3_Data_Model.md` and the diagram.

## 8. Data quality

Dimensions: **completeness, uniqueness, validity, consistency, timeliness, accuracy**. Practices in this project:
- **Quarantine** unusable rows with reasons instead of crashing or silently dropping.
- **Checks that reconcile**: row counts source → bronze → silver (+ quarantine); revenue equal across orders, lines, aggregates; keys unique; every fact finds its dimensions.
- **Fail loudly:** a bad load fails the run so the dashboard keeps the last good data.
- Real-life example from the deployment: an empty run (no orders for today's date) correctly failed `location_summary_ties_to_fact_order`.

## 9. Orchestration

A scheduler runs tasks in order, retries, alerts and keeps history (Airflow). **DAG:** tasks and dependencies with no cycles. **Idempotent tasks + retries + alerts** = a pipeline you can sleep next to. Chapter A10.

## 10. Metadata, lineage, governance

- **Catalog:** the address book of tables (Glue Data Catalog).
- **Lineage:** where a number came from. Here: the batch id on every row and `ops.pipeline_runs`.
- **Governance:** access control, PII handling (the loyalty card number stays in silver, never reaches gold), retention, auditing.

## 11. Business metrics used here

- **CLV (Customer Lifetime Value):** here, total spend to date per customer (historical, no prediction).
- **RFM:** score customers 1 to 5 on Recency, Frequency, Monetary.
- **Churn status:** active ≤ 45 days since last order, at risk 46 to 90, lapsed > 90.
- **Revenue per line:** `item_price` + Σ `option_price × quantity`.

## 12. Exercises

1. Draw the data flow from memory (source → bronze → silver → gold → dashboard) and label which file/job does each arrow.
2. For each of these, say which concept fixes it: duplicate rows after a retry (idempotency/MERGE); late-arriving rows (lookback); a rule changed (rebuild from bronze); a bad load (DQ check + fail); someone asks "where did this number come from?" (lineage).
3. Name the grain of every table in `docs/03_architecture/Step3_Data_Model.md`.
4. Explain why `customer_daily_snapshot` has rows for days without orders (recency and churn status change on those days).
5. Explain a **watermark with a 3-day lookback** to a friend in 60 seconds.

## Interview questions

1. ETL vs ELT? 2. What is idempotency and how do you achieve it? 3. Full vs incremental load; how do you detect deletes? 4. Star schema vs snowflake? 5. What is grain? 6. SCD types? 7. Data lake vs warehouse vs lakehouse? 8. How do you ensure data quality? 9. What is a watermark? 10. How do you handle late-arriving data? 11. What is a backfill and how do you do it safely? 12. Batch vs streaming, when each? 13. How do you design for failure? (retries, idempotency, alerts, quarantine, bookmarks only on success) 14. What is data lineage? 15. What would you monitor? (freshness, volume, quality, cost, failures)

## Done when

You answer questions 1 to 15 aloud without notes, using this project as the example for each.
