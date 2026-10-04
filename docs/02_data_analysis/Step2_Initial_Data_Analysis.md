# GlobalPartners Pipeline: Step 2 Initial Data Analysis

**Prepared by:** Polat
**Date:** 2026-10-04
**Step:** 2 of 7, Initial data analysis
**Status:** Analysis complete; SME confirmation needed on open questions
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
- **Test data is mixed into production data:** 826 rows come from the
  `Alltown Fresh - DEVELOPMENT` app.
- **Discounts cannot be found as documented:** the doc says discounts are negative
  `option_price` values, but none exist.
- **Analysis scope is 2023 only** (SME confirmed), matching `date_dim` coverage.

## 2. Scope

| Item | Value |
|---|---|
| Analysis period | 2023 only (SME confirmed) |
| Data loading approach | All years loaded into raw and cleaned layers; 2023 filter applied at the metrics layer |
| Profiling basis | Full files (all years); 2023 volume to be measured separately |

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
| Options with no matching line item (orphans) | ⚠️ 28 rows |
| Line items with options | 102,712 of 203,519 (50%) |
| Orders with options | 78,614 of 131,328 (60%) |

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

Approximate total across all years, before exclusions: $1.86M. This includes test
data and outliers and is not a reportable figure.

## 6. Data quality findings

### Resolved

| # | Finding | Resolution |
|---|---|---|
| 7 | Blank `printed_card_number` in 157,435 rows | Exactly matches non-loyalty rows; valid, not missing |
| 11 | Orders span 2020-04-21 → 2024-02-21; `date_dim` covers 2023 | SME confirmed 2023-only scope |
| 28 | `item_price` documented as unit price | Data shows line total (section 5.1) |

### Open

| # | Finding | Impact |
|---|---|---|
| 6 | `user_id` blank in 17,808 rows (8.7%) | Can't be attributed to a customer for CLV, RFM, or churn |
| 8 / 26 | 1 malformed row: blank `lineitem_id`, `item_category`, `item_name`, and quantity 0 | Quarantine |
| 9 | Identical options repeated on one line item (594 option groups on quantity-1 lines; 305 repeated 5+ times) | Intentional extras vs. duplicate errors; affects option revenue |
| 12 | 826 rows from `Alltown Fresh - DEVELOPMENT` | Test data inflates revenue and customer counts |
| 13 | `Alltown Neighborhood Perks` app, 1,270 rows | Purpose unknown |
| 17 | Two `user_id`s with 2,400+ line items each | Likely non-customer accounts (store, kiosk, employee); would distort CLV |
| 23 | No negative `option_price` values exist | Discount analysis has no data as documented |
| 24 | Lines with quantities of 300–500 (e.g. $5,000 Korean Kimchi) | Not test data; possibly catering or bulk orders; large CLV effect |
| 25 | 156 regular menu items priced $0 | Possibly how comps, rewards, or discounts are recorded |
| 27 | Inconsistent `item_name` casing and spelling | Normalize before grouping by item |
| 29 | 28 orphan options | Can't be tied to an item or customer; quarantine |

## 7. Key columns

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
| Data filtering | `app_name` (exclude test data) |

## 8. Questions for SME

1. Is `restaurant_id` the `location_id` referenced in Step 5?
2. The data shows `item_price` is the line total, contradicting the doc's "unit
   price." Please confirm.
3. Is `option_price` charged × `item_quantity` (current assumption) or once per
   line? Impact: $12,455.65 (0.67% of revenue).
4. Should the 17,808 orders without a `user_id` be excluded from customer metrics
   (CLV, RFM, churn) while still counting toward sales and location revenue?
5. Should `Alltown Fresh - DEVELOPMENT` orders (826 rows) be excluded as test data?
6. What is the `Alltown Neighborhood Perks` app, and should it be included?
7. No negative `option_price` values exist. How are discounts represented?
8. Are the 156 $0 menu items comps, rewards, or discounts?
9. Are repeated identical options on one line item intentional extras or
   duplicate errors?
10. Timestamps are UTC with no location time zone. Which time zone defines the
    business day for daily metrics, `date_dim` joins, and the 2023 boundary?
11. Are the two `user_id`s with 2,400+ line items real customers?
12. Are lines with quantities of 300–500 legitimate orders (catering, bulk)?

## 9. Decisions

| Decision | Reason |
|---|---|
| Analysis scope is 2023 only | SME confirmed; matches `date_dim` |
| Load all years; filter to 2023 at the metrics layer | Data stays available if scope changes |
| Line revenue = `item_price` (not × quantity) | Section 5.1 |
| Options charged × `item_quantity` (assumption) | Section 5.2; 0.67% impact |
| Left-join options to line items | 50% of line items have no options |
| Convert `"TRUE"`/`"FALSE"` strings to boolean | Required for correct filtering and aggregation |

## 10. Next steps

- Measure 2023 order volume and recompute key counts for the 2023 population
- Incorporate SME answers into the Step 3 data model and pipeline design
