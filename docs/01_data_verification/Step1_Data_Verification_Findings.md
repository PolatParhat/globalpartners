# GlobalPartners Pipeline: Step 1 Data Verification Findings

**Prepared by:** Polat
**Date:** 2026-10-01
**Step:** 1 of 7, Download and verify source files
**Status:** Complete, with open questions for SME review

---

## 1. Summary

All three source files were downloaded and checked with an automated integrity
script (`scripts/step1/verify_raw_file.py`). Both order files contain exactly the
row counts stated in the requirements document, all numeric and date values parse
correctly, and the documented join key is unique.

Five data quality issues remain open, and four questions need an SME decision
before the Step 3 architecture design. The most significant is a **date coverage
gap**: orders span roughly four years (2020-04-21 to 2024-02-21), while the
date dimension covers 2023 only.

## 2. Verification approach

Each file was checked for:

| Check | Purpose |
|---|---|
| SHA-256 checksum | Prove the raw file is unchanged throughout the project |
| Row count vs. requirements doc | Confirm the file is complete |
| Column names vs. documented schema | Detect schema drift |
| Blank values per column | Locate missing data |
| Fully duplicate rows | Detect export or extraction errors |
| Duplicate keys | Confirm join keys are unique |
| Numeric and date parsing | Detect malformed values |
| Date range | Confirm related datasets cover the same period |

Raw files are treated as immutable. All values are read as text so nothing is
silently converted, and any corrections are applied downstream, never to the
source files. Full results are saved in `data/raw/integrity_report.json`.

## 3. Source file baseline

| File | Rows | Expected | Size (bytes) | SHA-256 |
|---|---|---|---|---|
| order_items.csv | 203,519 | 203,519 ✅ | 37,894,585 | `03c8bf5030093e649b4f1d8da152e95dda6fbfb53d0978e1a367ff8621651d63` |
| order_item_options.csv | 193,017 | 193,017 ✅ | 17,604,850 | `9bd8a388b48d09e00bfef16dbe84b9953d8b59ce416d1af46614626573d0f64d` |
| date_dim.csv | 365 | Not stated | 15,901 | `4168f66d142e8263ee5ed4e223399d62eb7e7eea4c5b5f19f8dbc9c1bf9a1ea1` |

## 4. Check results

| Check | order_items | order_item_options | date_dim |
|---|---|---|---|
| Row count | ✅ Pass | ✅ Pass | n/a |
| Schema | ✅ Pass* | ✅ Pass* | ✅ Pass |
| Numeric parsing | ✅ 0 failures | ✅ 0 failures | ✅ 0 failures |
| Date parsing | ✅ 0 failures | n/a | ✅ 0 failures |
| Duplicate keys | ✅ 0 | No key defined | ✅ 0 |
| Fully duplicate rows | ✅ 0 | ⚠️ 2,299 | ✅ 0 |

\* After normalizing column names to lowercase (see finding 1).

## 5. Findings

### Resolved

| # | File | Finding | Resolution |
|---|---|---|---|
| 1 | order_items, order_item_options | Column headers are uppercase; the requirements doc shows lowercase | Column names normalized to lowercase on read, the convention for the whole pipeline |
| 2 | order_items | `creation_time_utc` mixes ISO 8601 timestamps with and without milliseconds (187 rows without) | Parsed with an explicit ISO 8601 format that accepts both |
| 3 | date_dim | `date_key` uses DD-MM-YYYY. Automatic parsing read it as MM-DD-YYYY, failing 221 dates and silently swapping the other 144 | Parsed with an explicit `DD-MM-YYYY` format; all 365 dates now correct |
| 4 | order_items | `order_id + lineitem_id` is unique across all rows | Confirmed as the join key to `order_item_options` |

### Open

| # | File | Finding | Impact |
|---|---|---|---|
| 5 | order_items | **Date coverage gap:** orders span 2020-04-21 to 2024-02-21; date_dim covers 2023-01-01 to 2023-12-31 only | Orders outside 2023 have no calendar attributes (weekend, holiday). The number of affected orders will be measured in Step 2. |
| 6 | order_items | `user_id` blank in 17,808 rows (8.7%), likely guest orders | These orders can't be attributed to a customer for CLV, RFM, or churn |
| 7 | order_items | `printed_card_number` blank in 157,435 rows (77%) | Likely expected for non-loyalty orders; to be verified against `is_loyalty` in Step 2 |
| 8 | order_items | 1 row blank in `lineitem_id`, `item_category`, and `item_name` | Likely a malformed row; to be inspected and possibly quarantined |
| 9 | order_item_options | 2,299 fully duplicate rows, and no documented unique key | Each duplicate is either a genuine repeated option or an extraction error. Dropping or keeping them changes revenue. |

### Expected

| # | File | Finding |
|---|---|---|
| 10 | date_dim | `holiday_name` blank in 353 rows, leaving 12 named holidays, consistent with non-holiday days |

## 6. Questions for SME

1. **Date coverage:** Orders run from 2020-04-21 to 2024-02-21, but `date_dim`
   covers 2023 only. Should the date dimension be extended to cover all order
   dates, or should analysis be limited to 2023?
2. **Location field:** Step 5 references `location_id`, which isn't in the data.
   Is `restaurant_id` the intended field?
3. **Revenue formula:** Is `option_price × option_quantity` charged once per line
   item, or once per unit of `item_quantity`?
4. **Guest orders:** Should the 17,808 orders without a `user_id` be excluded from
   customer metrics (CLV, RFM, churn) while still counting toward sales and
   location revenue?

## 7. Next steps (Step 2)

- Count the orders outside the 2023 date range
- Verify `printed_card_number` blanks against `is_loyalty`
- Inspect the malformed row and the 2,299 duplicate option rows
- Map table relationships and confirm the revenue formula against the data
