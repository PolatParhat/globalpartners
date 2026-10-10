# Step 3: Data Model

GlobalPartners Business Insights Pipeline. Draft, last updated 2026-10-09.

This document specifies every table the pipeline writes. It becomes the data-model
section of the Step 3 solution design document.

**Diagram:** `global-partner-data-model.drawio` (gold star schema: facts, dimensions, metric tables).

| Layer | Table | Status |
|---|---|---|
| Silver | `silver.order_items` | Approved 2026-10-09 |
| Silver | `silver.order_item_options` | Approved 2026-10-09 |
| Silver | `silver.date_dim` | Approved 2026-10-09 |
| Silver | `silver.quarantine` | Approved 2026-10-09 |
| Gold | `customer_daily_snapshot` | Approved 2026-10-09 |
| Gold | facts, dimensions, sales aggregates | Approved 2026-10-09 |

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
| 16 | `item_price` | decimal(10,2) | item_price | **line total, not unit price** (finding 28, SME confirmed Q2). Not a number or negative → quarantined |
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

Not flagged, kept as normal rows until the SME decides: $0 menu items (SME Q8; 1 line in 2023). Bulk lines do not occur in 2023 (maximum quantity 27).

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
No repeated copies occur in 2023 orders; silver keeps and flags any that arrive, and gold counts
each copy (switchable in config).

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
| 11 | `is_repeated_option` | boolean | row belongs to a group of identical copies (0 in 2023) |
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

## 5. `silver.date_dim`

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

## 6. `silver.quarantine`

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

## 7. Gold: `customer_daily_snapshot` (daily-evolving CLV)

**Purpose:** the primary requirement, showing how each customer's lifetime value evolves day by day.
**Grain:** one row per customer per day, from the customer's first in-scope order to the latest
loaded business date (dense: days without orders included, because recency, churn status and
tiers change on those days too). **Key:** `snapshot_date + customer_id`.

**Population (from config):** orders in the reporting scope (2023), excluding test data, guest
orders and non-customer accounts. **CLV counts 2023 orders only** (the confirmed reporting scope).

**Size for 2023:** 10,512 customers, 46,586 orders, $673,614.04 CLV at year end,
**2,283,740 rows**. 49 % of customers ordered once.

### Columns

| Group | Column | Meaning |
|---|---|---|
| Key | `snapshot_date`, `customer_id` | |
| That day | `orders_on_day`, `revenue_on_day` | |
| To date | `first_order_date`, `last_order_date`, `orders_to_date`, **`revenue_to_date`** (= **CLV**), `avg_order_value_to_date`, `days_since_first_order`, `is_repeat_customer` (≥ 2 orders) | |
| CLV tier | `clv_cume_dist` | share of customers that day with CLV ≤ this customer's |
| | `clv_tier` | **High** if `clv_cume_dist` > 0.8, **Low** if ≤ 0.2, else **Medium**. Re-ranked every day; equal CLV always gets the same tier, so groups are close to (not exactly) 20/60/20. 31 Dec 2023: High 2,103 (≥ $75.93), Medium 6,604, Low 1,805 (≤ $10.98; 311 customers tie at $10.99) |
| Behaviour | `days_since_last_order` | recency |
| | `avg_days_between_orders` | between distinct order days; NULL with one order day (median 26 days) |
| | `orders_last_90d`, `revenue_last_90d` | frequency and monetary window (N = 90 days, config) |
| | `revenue_last_30d`, `revenue_prev_30d`, `spend_change_pct_30d` | spend trend: last 30 days vs the 30 before; NULL when the earlier period is $0 |
| RFM | `r_score`, `f_score`, `m_score` | fixed bands from config (below) |
| | `rfm_segment` | VIP / New / Churn Risk / Regular (below) |
| Churn | `churn_status` | **active** ≤ 45 days since last order, **at_risk** 46–90, **lapsed** > 90 (SME Q13) |
| Loyalty | `is_loyalty_as_of` | loyalty flag of the customer's latest order up to that day |
| Audit | `_run_id`, `_computed_at` | |

### RFM bands (config)

Fixed bands instead of quintiles: 82.5 % of customers have 0 or 1 orders in any 90-day window,
so equal-sized groups are impossible, and quintile cut-offs would shift every day.

| Score | R: days since last order | F: orders in last 90 days | M: spend in last 90 days |
|---|---|---|---|
| 5 | ≤ 7 | 6+ | > $60 |
| 4 | 8–30 | 3–5 | $30–60 |
| 3 | 31–45 | 2 | $15–30 |
| 2 | 46–90 | 1 | $0.01–15 |
| 1 | > 90 | 0 | $0 |

| Segment (checked in order) | Rule |
|---|---|
| VIP | R ≥ 4 and F ≥ 4 and M ≥ 4 |
| New | R ≥ 4 and F ≤ 2 and first order within the last 90 days |
| Churn Risk | R ≤ 2 and F ≤ 2 |
| Regular | everything else |

### Churn status at 31 Dec 2023

| Status | Customers |
|---|---|
| active (≤ 45 days) | 2,409 |
| at_risk (46–90) | 1,553 |
| lapsed (> 90) | 6,550 |

Under the single "> 45 days = at risk" rule, 8,103 customers (77 %) would be at risk;
the three statuses separate customers who recently drifted away from long-gone one-time buyers.

### Example: customer `642d6946…`

| Date | CLV to date | Days since last order | Orders 90 d | Spend 90 d | R-F-M | Segment | Status |
|---|---|---|---|---|---|---|---|
| 2023-05-08 | $12.99 | 0 | 1 | $12.99 | 5-2-2 | New | active |
| 2023-06-25 | $12.99 | 48 | 1 | $12.99 | 2-2-2 | Churn Risk | at_risk |
| 2023-06-26 | $34.97 | 0 | 3 | $34.97 | 5-4-4 | VIP | active |
| 2023-10-23 | $74.94 | 0 | 3 | $39.97 | 5-4-4 | VIP | active |
| 2023-12-31 | $74.94 | 69 | 1 | $10.99 | 2-2-2 | Churn Risk | at_risk |

### Build

- **Full rebuild every run** (overwrite). 2.3 M rows takes seconds; late data corrects past days
  automatically. Iceberg keeps earlier versions.
- **Partitioned by month of `snapshot_date`** (12 partitions of about 190,000 rows).
- **DQ tie-out:** Σ `revenue_on_day` = in-scope customer revenue in `fact_order` ($673,614.04 for 2023).

---

## 8. Gold: facts

### `fact_order_line`

**Grain:** one row per item line. **Key:** `order_id + lineitem_id`. **Source:** `silver.order_items`
left-joined to its options. 203,518 rows (all years); 79,965 in the 2023 reporting scope.

| Column | Rule |
|---|---|
| `order_id`, `lineitem_id` | key |
| `business_date`, `order_hour_local` | joins to `dim_date`; time of day |
| `customer_id` | `user_id`, or `'GUEST'` when NULL |
| `restaurant_id`, `app_name`, `item_key` | join to `dim_location`, `dim_app`, `dim_item` |
| `is_loyalty` | from the order |
| `item_quantity` | |
| `item_revenue` | `item_price` (line total) |
| `option_count` | options on the line |
| `option_revenue` | Σ `option_price × item_quantity` (SME Q3 assumption). Repeated identical options counted each (config `repeated_options: count_each`; none in 2023) |
| `discount_amount` | Σ negative option amounts ($0 today, see section 11) |
| `line_revenue` | `item_revenue + option_revenue` |
| `has_discount` | `discount_amount < 0` |
| `is_test_data`, `is_guest`, `is_non_customer_account` | from silver |
| `_run_id`, `_gold_updated_at` | audit |

### `fact_order`

**Grain:** one row per order. **Key:** `order_id`. **Source:** `fact_order_line` grouped by order.
About 131,000 rows (all years); **52,015 orders and $746,223.86 in the 2023 reporting scope**.

Columns: `order_id`, `business_date`, `order_ts_local`, `order_hour_local`, `customer_id`,
`restaurant_id`, `app_name`, `is_loyalty`, `line_count`, `item_quantity`, `order_revenue`,
`discount_amount`, `has_discount`, the three flags, audit columns.

Order-level fields (customer, location, app, time, loyalty, card) are repeated on every line in
the source and never conflict within an order (0 of 131,328 orders). A DQ check keeps verifying this.

### How facts are updated

Each run finds the **affected orders** (any `order_id` with a new or changed row in
`silver.order_items` or `silver.order_item_options`), recomputes only those orders, and MERGEs
them into both facts. The unit is the order because an added option changes its line's revenue.

---

## 9. Gold: dimensions (rebuilt each run)

| Table | Key | Rows | Columns and notes |
|---|---|---|---|
| `dim_customer` | `customer_id` | 20,174 + 1 `GUEST` | `first_order_date`, `last_order_date`, `first_loyalty_order_date`, `is_non_customer_account`, `is_guest` (true only for `GUEST`) |
| `dim_location` | `restaurant_id` | 20 locations with real 2023 orders (+1 test-only location) | `first_order_date`, `last_order_date`, `is_test_location`. `restaurant_id` is the location (SME confirmed Q1); locations are shown by id, no names (decided) |
| `dim_item` | `item_key` = SHA-256(`item_name_key` + `item_category`) | 444 | `item_name` (most common spelling; ties alphabetical), `item_category` (42), `first_sold_date`, `last_sold_date`. An item is name + category: 49 names appear in more than one category |
| `dim_app` | `app_name` | 3 | `is_test_app` (`Alltown Fresh - DEVELOPMENT`). `Alltown Neighborhood Perks` included (SME confirmed Q6) |
| `dim_date` | `date` | 1,827 (2020-01-01 to 2024-12-31) | `year`, `quarter`, `month`, `month_name`, `iso_year`, `iso_week`, `day_of_week`, `day_of_week_num`, `is_weekend`, `is_holiday`, `holiday_name`, `is_in_scope`. Holiday data exists for 2023 only; elsewhere `is_holiday` is NULL (unknown), not false |

---

## 10. Gold: sales aggregates (rebuilt each run)

24.5 % of 2023 orders (12,752 of 52,015) contain items from more than one category. Revenue
adds up across categories, but order counts do not (such an order would be counted once per
category). Order-level and category-level aggregates are therefore separate tables, and both
store **sums only**; ratios such as average order value are calculated after summing.

| Table | Grain | Source | Measures |
|---|---|---|---|
| `sales_daily` | `business_date` × `restaurant_id` × `order_hour_local` | `fact_order` | `orders`, `revenue`, `item_quantity`, `loyalty_orders`, `loyalty_revenue`, `guest_orders`, `discounted_orders` |
| `sales_daily_category` | `business_date` × `restaurant_id` × `item_category` | `fact_order_line` | `revenue`, `item_quantity`, `line_count` (no order count) |

**Scope:** 2023, excluding test data. Guest orders and the non-customer account are included (real sales).
Weekly and monthly views join to `dim_date` (`iso_year` + `iso_week`, `month`).

**Where each Step 5 metric comes from**

| Metric | Table(s) |
|---|---|
| CLV, CLV tiers | `customer_daily_snapshot` |
| RFM segments, churn indicators | `customer_daily_snapshot` |
| Sales trends (daily/weekly/monthly; by location, category, time of day) | `sales_daily`, `sales_daily_category`, `dim_date` |
| Loyalty vs non-members | `fact_order`, `customer_daily_snapshot` (`is_loyalty_as_of`) |
| Top/bottom locations (revenue, average order value, orders per day/week) | `sales_daily`, `dim_location` |
| Discount effectiveness | `fact_order` (`has_discount`, `discount_amount`), `sales_daily` (`discounted_orders`) |

**DQ tie-out:** Σ `fact_order.order_revenue` = Σ `fact_order_line.line_revenue` = Σ `sales_daily.revenue`
= Σ `sales_daily_category.revenue` (= $746,223.86 for 2023).

---

## 11. Discount analysis depends on SME Q7

The requirements detect discounts as `option_price < 0`. **No such rows exist in the data**, so
the discount analysis will show no discounted orders until the SME explains how discounts are
recorded. The model already carries `discount_amount`, `has_discount` and `discounted_orders`, so
an answer becomes a rule change, not a redesign.

---

## 12. Known limitations

| Limitation | Effect | Production option |
|---|---|---|
| Rows **deleted** in SQL Server are not detected | Incremental extract sees new and changed rows only, so a deleted order stays in silver | Change data capture (SQL Server CDC) |
| Options extracted through their parent order | Options added to an order more than 3 days after it was placed would be missed | Add a timestamp to the options table at the source, or widen the lookback |
