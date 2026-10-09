# Step 3: Data Model

GlobalPartners Business Insights Pipeline. Draft, last updated 2026-10-09.

This document specifies every table the pipeline writes. It becomes the data-model
section of the Step 3 solution design document.

| Layer | Table | Status |
|---|---|---|
| Silver | `silver.order_items` | Approved 2026-10-09 |
| Silver | `silver.order_item_options` | Approved 2026-10-09 |
| Silver | `silver.date_dim` | Proposed |
| Silver | `silver.quarantine` | Proposed |
| Gold | facts, dimensions, `customer_daily_snapshot`, `sales_daily` | To be specified |

---

## 1. Layers

| Layer | Purpose | Grain | Written by |
|---|---|---|---|
| **Bronze** | Exact copy of each SQL Server table, all values as text, plus `_batch_id`, `_ingested_at`, `_source_table` | Same as source | Append only |
| **Silver** | Cleaned, typed and flagged copy of each source table. Broken rows go to quarantine. Nothing is removed for business reasons | Same as source | MERGE |
| **Gold** | Star schema (facts + dimensions) and the metric tables the dashboard reads | Designed per question | MERGE / rebuild |

## 2. Conventions (all silver tables)

| Topic | Rule |
|---|---|
| Column names | lowercase `snake_case` |
| Text | trimmed; empty strings become NULL; repeated spaces collapsed where noted |
| Money | `DECIMAL(10,2)`, never floating point, so sums are exact to the cent |
| Booleans | source `"TRUE"`/`"FALSE"` become real booleans; any other value is invalid |
| Dates and times | parsed with an explicit format, never guessed. Spark session time zone = UTC. Business day = `America/New_York` (assumption pending SME Q10) |
| Keys | natural keys from the source; a SHA-256 key where the source has none |
| Quarantine vs flag | **Quarantine:** the row is broken and cannot be used (it moves to `silver.quarantine` with a reason). **Flag:** the row is valid but a business rule may exclude it (it stays, with a boolean column). Exclusions happen in gold, driven by `config/business_rules.yaml` |
| Duplicates from the 3-day lookback | one row per key is kept (newest `_ingested_at`), then MERGE: new keys inserted, changed rows (different `_row_hash`) updated, unchanged rows skipped |
| Audit columns | `_batch_id`, `_ingested_at` (from bronze), `_row_hash` (SHA-256 of the business columns), `_silver_updated_at` |
| Partitioning | none in silver. Tables are a few MB; splitting them would create many tiny files and slow queries down. Revisit above ~1 GB |

---

## 3. `silver.order_items`

**Grain:** one row per item line on an order. **Key:** `order_id + lineitem_id` (unique: 0 duplicates in 203,519 rows).

### Columns

| # | Column | Type | Source | Rule |
|---|---|---|---|---|
| 1 | `order_id` | string | order_id | required |
| 2 | `lineitem_id` | string | lineitem_id | required |
| 3 | `restaurant_id` | string | restaurant_id | required |
| 4 | `app_name` | string | app_name | |
| 5 | `user_id` | string | user_id | blank → NULL (guest order). Gold represents guests as `'GUEST'` |
| 6 | `printed_card_number` | string | printed_card_number | blank → NULL. Kept as text (no leading zeros lost). **Sensitive:** stays in silver, never copied to gold or the dashboard |
| 7 | `is_loyalty` | boolean | is_loyalty | `TRUE`/`FALSE`, otherwise quarantined |
| 8 | `currency` | string | currency | must be `USD` |
| 9 | `order_ts_utc` | timestamp | creation_time_utc | format `yyyy-MM-dd'T'HH:mm:ss[.SSS]X`; covers all four formats found in the data (no fraction: 187 rows, 1 digit: 1,853, 2 digits: 18,131, 3 digits: 183,348) |
| 10 | `order_ts_local` | timestamp (no zone) | order_ts_utc | converted to `America/New_York`, daylight saving included |
| 11 | `business_date` | date | order_ts_local | the day the order counts on; joins to the date dimension |
| 12 | `order_hour_local` | int 0–23 | order_ts_local | for time-of-day analysis |
| 13 | `item_category` | string | item_category | pasted admin URLs removed (regex `https?://\S*?#`): **98 rows repaired** to existing categories `Drip Coffee`, `BBQ Plates`, `Kid's` (finding 34) |
| 14 | `item_name` | string | item_name | trimmed, repeated spaces collapsed (**427 rows** affected). Display name |
| 15 | `item_name_key` | string | item_name | lowercase of #14, used for grouping: **432 spellings → 396 items** (findings 27, 33) |
| 16 | `item_price` | decimal(10,2) | item_price | **line total, not unit price** (finding 28). Not a number or negative → quarantined |
| 17 | `item_quantity` | int | item_quantity | whole number ≥ 1, otherwise quarantined |
| 18 | `is_guest` | boolean | user_id | `user_id` is NULL |
| 19 | `is_test_data` | boolean | app_name | app listed in config `excluded_apps` (`Alltown Fresh - DEVELOPMENT`) |
| 20 | `is_non_customer_account` | boolean | user_id | user listed in config `non_customer_ids` (`5ece77fe902ad501337b23fd`, SME Q11) |
| 21 | `is_category_repaired` | boolean | | the URL repair changed the value (audit trail) |
| 22–25 | `_batch_id`, `_ingested_at`, `_row_hash`, `_silver_updated_at` | | | audit (section 2) |

### Quarantine rules

| Rule | Rows today |
|---|---|
| `order_id`, `lineitem_id` or `restaurant_id` missing | 1 |
| `creation_time_utc` does not match the format | 0 |
| `item_price` not a number or negative | 0 |
| `item_quantity` not a whole number or < 1 | 1 |
| `is_loyalty` not TRUE/FALSE | 0 |
| `currency` not USD | 0 |
| **Rows quarantined** | **1** (finding 8: blank line id, blank item, quantity 0, $4.39, 2021) |

Rules that catch nothing today protect against future bad data from the source.

### Flags

| Flag | 2023 rows (New York time) | All years |
|---|---|---|
| `is_guest` | 6,395 | 17,808 |
| `is_test_data` | 700 | 826 |
| `is_non_customer_account` | 1,090 | 2,454 |
| `is_category_repaired` | | 98 |

Not flagged, kept as normal rows until the SME decides: $0 menu items (SME Q8; 1 row in 2023, 156 in all years) and lines with quantity ≥ 100 (SME Q12; 0 in 2023, 9 in all years).

### Data-quality check (run by the DQ step, not per row)

Loyalty card present ⇔ `is_loyalty` = true (0 exceptions today, finding 7).

---

## 4. `silver.order_item_options`

**Grain:** one row per option row in the source. **Key:** `option_key` (built, see below).
193,017 rows.

### Building a key

The source has no option id, and **2,915 rows are exact copies of another row** (616 groups,
up to 10 copies; 594 groups on quantity-1 lines; **0 in 2023**). Identical copies are numbered
1, 2, 3… within each extract batch (`option_seq`) and the key is:

`option_key = SHA-256(order_id | lineitem_id | option_group_name | option_name | option_price | option_seq)`

Identical copies cannot be told apart, so the numbering always produces the same set of keys.
A re-read by the lookback therefore matches the existing keys and creates no duplicates.
Whether repeated copies are real extras or recording errors is SME **Q9**: silver keeps and
flags them; gold counts each copy by default, switchable in config.

### Incremental extract

Options have no timestamp. They are extracted **through their parent order**: each run reads
the options of every order inside the order-items window (watermark − 3 days), so a line and
its options always arrive in the same batch.

### Columns

| # | Column | Type | Rule |
|---|---|---|---|
| 1 | `order_id` | string | required |
| 2 | `lineitem_id` | string | required; with `order_id` must exist in `silver.order_items` |
| 3 | `option_group_name` | string | trimmed, spaces collapsed (133 groups, e.g. *Milk Options*) |
| 4 | `option_name` | string | trimmed, spaces collapsed (**321 rows** affected) |
| 5 | `option_name_key` | string | lowercase of #4, for grouping (637 → 625 names) |
| 6 | `option_price` | decimal(10,2) | must be a number. **Negative values are allowed** (the requirements define them as discounts). Today: 127,980 at $0, 65,037 positive, max $8.00, none negative (SME Q7) |
| 7 | `option_quantity` | int | whole number ≥ 1 (always 1 today) |
| 8 | `option_seq` | int | copy number among identical rows |
| 9 | `option_key` | string | unique key (above) |
| 10 | `is_discount` | boolean | `option_price < 0` |
| 11 | `is_repeated_option` | boolean | row belongs to a group of identical copies (Q9) |
| 12–15 | `_batch_id`, `_ingested_at`, `_row_hash`, `_silver_updated_at` | | audit |

Option revenue (`option_price × item_quantity`, SME Q3 assumption) needs the item quantity,
so it is calculated in gold where lines and options are joined.

### Quarantine rules

| Rule | Rows today |
|---|---|
| `order_id`, `lineitem_id`, group or name missing | 0 |
| `option_price` not a number | 0 |
| `option_quantity` not a whole number ≥ 1 | 0 |
| parent line not found in `silver.order_items` | **28** (15 line keys; their orders are absent from the source, finding 29) |
| parent line quarantined | 0 |

### Data-quality check

Orphan options counted directly in SQL Server on every run and recorded in `ops.dq_results`,
because the daily parent-based extract cannot see them.

---

## 5. `silver.date_dim` (proposed)

**Grain:** one row per calendar date. **Key:** `date`. 365 rows (2023). Full reload each run (MERGE on `date`).

| # | Column | Type | Rule |
|---|---|---|---|
| 1 | `date` | date | from `date_key`, explicit format `dd-MM-yyyy` (finding 3); required, unique |
| 2 | `year` | int | |
| 3 | `month` | int 1–12 | the source holds numbers, although the requirements doc describes month names |
| 4 | `iso_week` | int | renamed from `week`: the source uses the **ISO 8601 week**, so 1–2 Jan 2023 belong to week 52 of ISO year 2022. Never group by `year + week`; the gold date dimension adds the ISO year |
| 5 | `day_of_week` | string | e.g. `Sunday` |
| 6 | `is_weekend` | boolean | |
| 7 | `is_holiday` | boolean | 12 US federal holidays in 2023 |
| 8 | `holiday_name` | string | blank → NULL |
| 9–12 | audit columns | | |

**Quarantine:** `date_key` that does not parse, or a duplicate date (0 today).
**Data-quality check:** every attribute agrees with the date itself (weekday, weekend, month, year,
ISO week; holiday flag ⇔ holiday name). 0 mismatches today.

The gold date dimension is generated for the full order range (2020–2024) and takes holiday
information from this table where available.

---

## 6. `silver.quarantine` (proposed)

**Grain:** one row per distinct broken source row. Shared by all silver tables.

The 3-day lookback re-reads recent rows every day, so the same broken row arrives several
times. Quarantine therefore uses MERGE on `source_table + record_hash` and counts sightings
instead of adding a new row each day.

| # | Column | Type | Meaning |
|---|---|---|---|
| 1 | `source_table` | string | `order_items`, `order_item_options` or `date_dim` |
| 2 | `record_key` | string | the row's business key if it has one (e.g. `order_id|lineitem_id`), else NULL |
| 3 | `record` | string (JSON) | the original row exactly as received |
| 4 | `record_hash` | string | SHA-256 of `record`; with #1 the key |
| 5 | `reasons` | string | every failed rule, e.g. `missing lineitem_id; bad item_quantity` |
| 6 | `first_seen_batch_id` / `last_seen_batch_id` | string | first and latest run that delivered it |
| 7 | `first_seen_at` / `last_seen_at` | timestamp | |
| 8 | `times_seen` | int | |
| 9 | `status` | string | `open`, or `resolved` once a valid row with the same `record_key` reaches silver (the source was corrected) |

Expected content after the first full load: **29 rows** (1 order line + 28 orphan options).
The quarantine rate per run is checked by the DQ step.

---

## 7. Gold layer

To be specified: `fact_order_line`, `fact_order`, `dim_customer`, `dim_location`, `dim_item`,
`dim_app`, `dim_date`, `customer_daily_snapshot`, `sales_daily`.

---

## 8. Known limitations

| Limitation | Effect | Production option |
|---|---|---|
| Rows **deleted** in SQL Server are not detected | Incremental extract sees new and changed rows only, so a deleted order stays in silver | Change data capture (SQL Server CDC) |
| Options extracted through their parent order | Options added to an order more than 3 days after it was placed would be missed | Add a timestamp to the options table at the source, or widen the lookback |
