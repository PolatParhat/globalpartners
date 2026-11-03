# Stage B9: metrics (CLV snapshot, RFM, churn, sales, locations)

**Goal:** the daily-evolving CLV table and the metric tables the dashboard reads. Prerequisites: A7 (windows), B8.

## The tables

| Table | Grain | Purpose |
|---|---|---|
| `customer_daily_snapshot` | customer × day, from first order to last loaded day, **including days without orders** | CLV to date, tier, RFM, segment, churn status, loyalty |
| `sales_daily` | day | orders, revenue, customers |
| `sales_daily_category` | day × category | revenue by category |
| `location_summary` | restaurant | orders, revenue, customers, repeat customers |

## Customer snapshot: build in this order (each a pure function)

1. `customer_orders`: orders that count for customers (in dates, no test app, no faulty account, no guests).
2. `customer_calendar`: the dense list of days per customer with that day's orders and revenue.
3. `add_totals`: running orders and revenue (= **CLV**), recency (days since last order), average order value (window `sum` over rows unbounded preceding → current).
4. `add_loyalty`: loyalty flag of the latest order up to that day.
5. `add_windows`: last 90 and last 30 days orders/revenue (the calendar is dense, so "last N days" is the last N rows).
6. `add_clv_tier`: `cume_dist` of CLV among that day's customers: High above 0.80, Low at or below 0.20, otherwise Medium.
7. `add_rfm`: R, F, M scores from **fixed bands** in `business_rules.yaml`; segment by first matching rule: VIP, New, Churn Risk, else Regular. Why fixed bands: more than 80 % of customers have 0 or 1 orders in 90 days, so equal-sized groups are impossible and bands must mean the same on every day.
8. `add_churn`: active ≤ 45 days since last order, at risk 46 to 90, lapsed over 90.

Tests first: a customer with a known timeline (the design document shows one: 8 May New/active at $12.99; 25 June Churn Risk/at risk; 26 June VIP at $34.97; 31 Dec Churn Risk again).

## Check (full year)

| Figure | Expected |
|---|---|
| snapshot rows | 2,283,740 |
| customers | 10,512 |
| Σ `revenue_to_date` at the last day (CLV) | $673,614.04 |
| CLV tiers at 31 Dec | High 2,103 · Medium 6,604 · Low 1,805 |
| RFM segments at 31 Dec | Churn Risk 7,693 · Regular 1,661 · VIP 755 · New 403 |
| churn status at 31 Dec | active 2,409 · at risk 1,553 · lapsed 6,550 |
| `sales_daily` revenue | $746,223.86 |
| locations | 20 |

(Locally you can load the whole year with `scripts/build_demo_lake.py`, or replay it in chunks.)

## Compare with the real project

`metrics/customer_snapshot.py`, `sales.py`, `location.py`, `jobs/gold_metrics.py`, `tests/test_customer_snapshot.py`, `test_sales.py`, `test_location.py`.

## Done when

Your numbers equal the table above and you can explain every window in the snapshot.
