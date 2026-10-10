# GlobalPartners Pipeline: Step 2 Initial Data Analysis

**Prepared by:** Polat
**Date:** 2026-10-04
**Step:** 2 of 7, Initial data analysis
**Status:** Analysis complete; remaining SME questions tracked in the Step 3 solution design (section 12)
**Last updated:** 2026-10-10 (findings 34 and 35 added; SME answers to Q1, Q2, Q4, Q6, Q11 recorded)
**Notebook:** `scripts/step2/data_analysis.ipynb`

---

## 1. Summary

The three source files were profiled column by column, their relationships were
tested, and the revenue formula was derived from the data itself.

Key results:

- **The revenue definition in the requirements doc does not match the data.**
  `item_price` is the line total (price × quantity), not the unit price. Following
  the doc would inflate revenue on all 13,650 multi-quantity line items.
- **Working revenue formula:** `item_price + Σ(option_price × item_quantity)`.
- **Test data was mixed into production data:** 826 rows come from the
  `Alltown Fresh - DEVELOPMENT` app. The SME confirmed these are test data and
  they are excluded from all metrics.
- **Discounts cannot be found as documented:** the doc says discounts are negative
  `option_price` values, but none exist.
- **Analysis scope is 2023 only** (SME confirmed), matching `date_dim` coverage.
  The in-scope population is 52,015 orders from 10,513 customers at 20 locations,
  $746,223.86 in revenue (section 6).
- **Two more issues found during Step 3 design:** pasted admin URLs corrupt
  `item_category` in 96 in-scope rows (always reversible), and 18.2 % of in-scope
  customers switch loyalty status over time, so loyalty is not a fixed customer
  attribute (findings 34, 35).
- **Most outliers fall outside 2023.** Bulk lines, repeated options, $0 items and
  the Neighborhood Perks app barely occur in the in-scope data, so several SME
  questions have little effect on the metrics (section 6.2).

## 2. Scope

| Item | Value |
|---|---|
| Analysis period | 2023 only (SME confirmed) |
| Data loading approach | All years loaded into raw and cleaned layers; 2023 filter applied at the metrics layer |
| Profiling basis | Full files (all years); 2023 population measured in section 6 |
| Test data | `Alltown Fresh - DEVELOPMENT` rows excluded from metrics (SME confirmed); flagged, not deleted |
| Business time zone | `America/New_York` (working assumption, SME Q10) |

## 3. Dataset profile

| Measure | Value |
|---|---|
| Line items | 203,519 |
| Orders | 131,328 (avg 1.55 line items per order; max 61) |
| Identified customers | 20,174 |
| Locations (`restaurant_id`) | 28 |
| Ordering apps | 3 |
| Item categories / item names | 46 / 432 |
| Option rows | 193,017 |
| Currency | USD only |

### Column observations

| Column | Observation |
|---|---|
| `app_name` | `Alltown Fresh` (201,423), `Alltown Neighborhood Perks` (1,270), `Alltown Fresh - DEVELOPMENT` (826) |
| `is_loyalty`, `is_weekend`, `is_holiday` | Stored as strings `"TRUE"` / `"FALSE"`; pipeline must convert to boolean |
| `printed_card_number` | Blank in exactly the 157,435 non-loyalty rows; zero exceptions (crosstab) |
| `lineitem_id` | Unique across the entire file |
| `creation_time_utc` | One timestamp per order (131,328 distinct, same as `order_id`) |
| `item_price` | Median $8.00, middle 50% $5.89–$10.00; max $5,000; 156 rows at $0; none negative |
| `item_quantity` | 75% of rows are 1; max 500; 1 row at 0 |
| `option_quantity` | Always 1 |
| `option_price` | 16 distinct values ($0.00–$8.00); none negative |
| `item_name` | Inconsistent casing and spelling (e.g. `ALLTOWN FRESH HOT COFFEE`, `SARSAPARILA SODA`) |

## 4. Table relationships

```
order_items (1 row = 1 line item)
    │  order_id + lineitem_id   (left join; 1 line item → 0..n options)
    ▼
order_item_options (1 row = 1 option on a line item)

order_items
    │  date(creation_time_utc) = date_key   (time zone to be confirmed)
    ▼
date_dim (1 row = 1 calendar day, 2023)
```

| Relationship | Result |
|---|---|
| `order_id + lineitem_id` unique in `order_items` | ✅ 0 duplicates |
| Options with no matching line item (orphans) | ⚠️ 28 rows (15 line items; their orders are absent from `order_items`) |
| Line items with options | 102,697 of 203,519 (50%) |
| Orders with options | 78,600 of 131,328 (60%) |
| 2023 order dates present in `date_dim` | ✅ All 365 days; no gaps |

Because half the line items have no options, options must be **left-joined** to
line items, or those items disappear from revenue.

## 5. Revenue formula analysis

### 5.1 `item_price` is the line total, not the unit price

The requirements doc describes `item_price` as the unit price. The data shows
otherwise.

**Evidence 1: the largest lines.** Dividing `item_price` by quantity gives a
realistic menu price every time:

| Item | item_price | qty | price ÷ qty |
|---|---|---|---|
| Korean Kimchi | $5,000.00 | 500 | $10.00 |
| Meet Your Matcha - 12oz | $3,500.00 | 500 | $7.00 |
| Chili Chicken Bowl | $3,567.00 | 300 | $11.89 |
| B.L.A.T | $2,967.00 | 300 | $9.89 |

**Evidence 2: a test across all multi-quantity rows.** Each item's typical unit
price was taken as its median price on quantity-1 lines. Each multi-quantity line
was then checked against both interpretations:

| Interpretation | Matching rows (of 13,650) |
|---|---|
| `item_price` = unit price (per doc) | **0** |
| `item_price` = line total | **5,972** |
| Neither (within $0.01) | 7,678 |

**Evidence 3: the "neither" rows.** For the 7,662 non-matching rows that have a
reference price, the ratio of implied unit price to reference price has a
**median of 0.98** (middle 50%: 0.83–1.15). That's normal price variation across
locations and years. If `item_price` were a unit price, these ratios would cluster
near 0.5 or lower.

**Conclusion:** line revenue uses `item_price` as-is, and is never multiplied by
quantity.

### 5.2 Options are unit prices, recorded once per line

- `option_quantity` is always 1.
- Options are recorded once per line regardless of quantity. For example, 7,090
  options on quantity-2 lines were recorded once, and only 8 twice.
- `option_price` has only 16 menu-like values. If prices were scaled by quantity,
  values such as $1.20 (0.60 × 2) would appear; none do.

Whether a customer is charged `option_price` once per line or once per unit can't
be determined from the data. The difference is small:

| Option revenue interpretation | Amount |
|---|---|
| Once per line | $85,245.14 |
| × `item_quantity` | $97,700.79 |
| **Difference** | **$12,455.65 (0.67% of total revenue)** |

**Working assumption:** options are charged × `item_quantity`, pending SME
confirmation.

### 5.3 Working formula

```
line revenue = item_price + Σ (option_price × item_quantity)
```

Total across all years, before exclusions: $1,876,434.32. This includes test data
and years outside scope and is not a reportable figure. The in-scope figure is in
section 6.

## 6. The 2023 population

### 6.1 Volume

The business day is defined in `America/New_York` (working assumption, SME Q10).
Only 1 line item changes year between UTC and Eastern time, so the choice has
almost no effect on 2023 totals.

| Population | Line items | Orders | Customers | Guest lines | Locations | Revenue |
|---|---|---|---|---|---|---|
| All years | 203,519 | 131,328 | 20,174 | 17,808 | 28 | $1,876,434.32 |
| 2023 | 80,665 | 52,641 | 10,604 | 6,395 | 21 | $752,776.30 |
| **2023, test data excluded (in scope)** | **79,965** | **52,015** | **10,513** | **6,132** | **20** | **$746,223.86** |

Excluding test data removes one location: `restaurant_id`
`6050e76361e498ca740bba6f` is used only by the DEVELOPMENT app.

Orders per year (Eastern time): 2020: 8,186 · 2021: 26,790 · 2022: 37,490 ·
**2023: 52,641** · 2024: 6,221.

### 6.2 Open findings in the in-scope population

| # | Finding | All years | In scope (2023, excl. test) |
|---|---|---|---|
| 6 | Guest lines (blank `user_id`) | 17,808 (8.75%) | 6,132 (7.7%) |
| 8 | Malformed row | 1 | 0 (row is from 2021) |
| 9 | Repeated identical options on qty-1 lines | 594 groups | 0 |
| 13 | `Alltown Neighborhood Perks` rows | 1,270 | 4 |
| 17 | Rows from the two heaviest `user_id`s | 4,992 | 1,136 (1,090 from one account) |
| 24 | Lines with quantity ≥ 100 | 9 | 0 (max quantity 27, max line $269.73) |
| 25 | $0 menu items | 156 | 1 |
| 27 | Item names with casing variants | 36 | 2 (122 names → 120) |
| 29 | Orphan options | 28 | 0 (orders from Feb 2024) |
| 34 | `item_category` corrupted by a pasted admin URL | 98 | 96 (70 `BBQ Plates`, 26 `Drip Coffee`) |
| 35 | Customers with both loyalty and non-loyalty orders | | 1,913 of 10,512 customers (18.2 %); 1,808 joined later |

Questions 9 and 12 have no 2023 rows and were not asked. Questions 4, 6 and 11 have
since been answered (section 9).

## 7. Data quality findings

### Resolved

| # | Finding | Resolution |
|---|---|---|
| 7 | Blank `printed_card_number` in 157,435 rows | Exactly matches non-loyalty rows; valid, not missing |
| 11 | Orders span 2020-04-21 → 2024-02-21; `date_dim` covers 2023 | SME confirmed 2023-only scope |
| 12 | 826 rows from `Alltown Fresh - DEVELOPMENT` (741 orders, 115 users, $7,221.54) | SME confirmed test data; excluded from metrics, flagged in cleaned data |
| 28 | `item_price` documented as unit price | Data shows line total (section 5.1); SME confirmed (Q2) |
| 6 | `user_id` blank in 17,808 rows (6,132 in scope) | SME confirmed (Q4): excluded from customer metrics, kept in sales and location totals |
| 13 | `Alltown Neighborhood Perks` app | SME confirmed (Q6): included |
| 17 | Two `user_id`s with 2,400+ line items | SME confirmed (Q11): `5ece77fe902ad501337b23fd` is a faulty account, the only one; excluded from customer metrics. The other account is a normal customer in 2023 |
| 9, 24 | Repeated identical options; lines with quantity 300–500 | No rows in 2023; not asked. The pipeline keeps and flags them |
| 8 / 26, 29 | Malformed row; orphan options | Quarantined by the pipeline (Step 3 design) |
| 27, 33 | Inconsistent item-name casing and spacing | Normalised in the cleaned layer (Step 3 design) |
| 34 | `item_category` corrupted by pasted admin URLs (96 rows in scope), e.g. `Drip Chttps://www.opendining.net/...#offee` | Removing the URL fragment always gives an existing category; repaired and flagged in the cleaned layer (notebook section 11) |
| 35 | Loyalty status changes per customer: 1,913 of 10,512 in-scope customers (18.2 %) have both loyalty and non-loyalty orders; 1,808 started without loyalty; up to 9 switches | Loyalty is kept on every order and recorded as of each day in the data model (notebook section 11) |

### Open

| # | Finding | Impact |
|---|---|---|
| 23 | No negative `option_price` values exist | Discount analysis has no data as documented (SME Q7) |
| 25 | $0 menu item (1 line in scope) | Possibly a comp, reward or discount (SME Q8) |

## 8. Key columns

### Grain

| Entity | Identified by |
|---|---|
| Line item | `order_id + lineitem_id` |
| Order | `order_id` |
| Customer | `user_id` |
| Location | `restaurant_id` |
| Day | `date_key` |

### Join keys

| Join | Keys | Type |
|---|---|---|
| order_items → order_item_options | `order_id`, `lineitem_id` | Left |
| order_items → date_dim | date of `creation_time_utc` = `date_key` | Left |

### Columns for insights

| Business question (Step 5) | Columns |
|---|---|
| CLV, RFM, churn | `user_id`, `creation_time_utc`, `item_price`, `option_price`, `item_quantity` |
| Loyalty program impact | `is_loyalty`, `printed_card_number` |
| Location performance | `restaurant_id` |
| Sales trends, seasonality | `creation_time_utc`, `date_dim.is_weekend`, `is_holiday`, `holiday_name` |
| Product analysis | `item_category`, `item_name` |
| Discounts | `option_price` (per doc; no negatives found), $0 `item_price` (candidate) |
| Data filtering | `app_name` (exclude `Alltown Fresh - DEVELOPMENT`) |

## 9. Questions for SME

Remaining questions, with 2023 figures, are tracked in
[Step 3 solution design, section 12](../03_architecture/Step3_Solution_Design.md).

1. ~~Is `restaurant_id` the `location_id` referenced in Step 5?~~ **Answered 2026-10-10: yes.**
2. ~~The data shows `item_price` is the line total, contradicting the doc's "unit
   price." Please confirm.~~ **Answered 2026-10-10: line total.**
3. Is `option_price` charged × `item_quantity` (current assumption) or once per
   line? 2023 impact: $2,739.90 (0.37 % of revenue).
4. ~~Should orders without a `user_id` be excluded from customer metrics
   (CLV, RFM, churn) while still counting toward sales and location revenue?~~
   **Answered 2026-10-10: yes.**
5. ~~Should `Alltown Fresh - DEVELOPMENT` orders (826 rows) be excluded as test data?~~
   **Answered 2026-10-04: yes, exclude from metrics.**
6. ~~What is the `Alltown Neighborhood Perks` app, and should it be included?~~
   **Answered 2026-10-10: include.**
7. No negative `option_price` values exist. How are discounts represented?
8. Is the $0 menu item (1 line in 2023) a comp, reward, or discount?
9. ~~Are repeated identical options on one line item intentional extras or
   duplicate errors?~~ **Not asked: no cases in 2023.**
10. Timestamps are UTC with no location time zone. Which time zone defines the
    business day for daily metrics, `date_dim` joins, and the 2023 boundary?
11. ~~Are the two `user_id`s with 2,400+ line items real customers?~~
    **Answered: `5ece77fe…` is a faulty account, the only one; excluded from customer metrics.**
12. ~~Are lines with quantities of 300–500 legitimate orders (catering, bulk)?~~
    **Not asked: none in 2023 (max quantity 27).**

## 10. Decisions

| Decision | Reason |
|---|---|
| Analysis scope is 2023 only | SME confirmed; matches `date_dim` |
| Load all years; filter to 2023 at the metrics layer | Data stays available if scope changes |
| Line revenue = `item_price` (not × quantity) | Section 5.1 |
| Options charged × `item_quantity` (assumption) | Section 5.2; 0.67% impact |
| Left-join options to line items | 50% of line items have no options |
| Convert `"TRUE"`/`"FALSE"` strings to boolean | Required for correct filtering and aggregation |
| Exclude `Alltown Fresh - DEVELOPMENT` rows from metrics; flag as `is_test_data` in cleaned data | SME confirmed test data (Q5) |
| Business day in `America/New_York` (assumption) | Pending SME Q10; 1 row affected vs UTC |
| Guests excluded from customer metrics, kept in sales | SME confirmed (Q4) |
| `Alltown Neighborhood Perks` included | SME confirmed (Q6) |
| Account `5ece77fe902ad501337b23fd` excluded from customer metrics | SME confirmed faulty account (Q11) |
| Repair `item_category` by removing the URL fragment; flag repaired rows | Finding 34: always gives an existing category |
| Loyalty recorded per order and per day, not per customer | Finding 35 |

## 11. Next steps

- Step 3 design is with the SME for approval; remaining questions are in its section 12
- SME answers so far are applied in `config/business_rules.yaml`
