"""All SQL the dashboard runs, in one place.

The SQL is deliberately plain (SELECT, WHERE, GROUP BY, SUM, COUNT, CASE) so the same text runs on both
engines: Spark SQL on the local Iceberg lake and Amazon Athena in AWS. Tables are written WITHOUT a database
name (`FROM sales_daily`): both engines are pointed at the gold database first (see data.py).

Every query returns SUMS and COUNTS, never ratios. pandas (logic.py) calculates averages and shares after
summing, so any slice the user picks (a segment, a location, a date range) stays correct.
"""
from datetime import date


def day(d: date) -> str:
    """A SQL date literal. Only a real `date` is accepted: isoformat() cannot carry SQL text."""
    if not isinstance(d, date):
        raise TypeError(f"expected a date, got {type(d).__name__}")
    return f"DATE '{d.isoformat()}'"


# ---------------------------------------------------------------- sales (pages 3, 5, 6)
SALES_DAILY = """
SELECT business_date, restaurant_id, order_hour_local,
       orders, revenue, item_quantity, loyalty_orders, loyalty_revenue, guest_orders, discounted_orders
FROM sales_daily
"""

SALES_CATEGORY = """
SELECT business_date, restaurant_id, item_category, revenue, item_quantity, line_count
FROM sales_daily_category
"""

LOCATION_SUMMARY = """
SELECT restaurant_id, orders, revenue, customers, repeat_customers
FROM location_summary
"""

# ---------------------------------------------------------------- customers (pages 1, 2, 4)
SNAPSHOT_RANGE = """
SELECT MIN(snapshot_date) AS first_day, MAX(snapshot_date) AS last_day
FROM customer_daily_snapshot
"""


def customer_cube(as_of: date) -> str:
    """Customers on one day, counted per combination of the attributes the pages slice by."""
    return f"""
SELECT rfm_segment, clv_tier, churn_status, is_loyalty_as_of, r_score, f_score, m_score,
       COUNT(*)                                      AS customers,
       SUM(revenue_to_date)                          AS clv,
       SUM(orders_to_date)                           AS orders,
       SUM(revenue_last_90d)                         AS revenue_90d,
       SUM(orders_last_90d)                          AS orders_90d,
       SUM(CASE WHEN is_repeat_customer THEN 1 ELSE 0 END) AS repeat_customers
FROM customer_daily_snapshot
WHERE snapshot_date = {day(as_of)}
GROUP BY rfm_segment, clv_tier, churn_status, is_loyalty_as_of, r_score, f_score, m_score
"""


def churn_bands(as_of: date) -> str:
    """Customers on one day by churn status and three behaviour bands (what goes with a higher churn risk)."""
    return f"""
SELECT churn_status,
       CASE WHEN orders_to_date = 1 THEN '1 order'
            WHEN orders_to_date <= 3 THEN '2-3 orders'
            WHEN orders_to_date <= 9 THEN '4-9 orders'
            ELSE '10+ orders' END AS order_band,
       CASE WHEN avg_days_between_orders IS NULL THEN 'one order only'
            WHEN avg_days_between_orders <= 14 THEN 'every 2 weeks or faster'
            WHEN avg_days_between_orders <= 30 THEN 'every 2-4 weeks'
            WHEN avg_days_between_orders <= 60 THEN 'every 1-2 months'
            ELSE 'less often' END AS gap_band,
       CASE WHEN spend_change_pct_30d IS NULL THEN 'no spend in the 30 days before'
            WHEN spend_change_pct_30d <= -50 THEN 'down 50% or more'
            WHEN spend_change_pct_30d < 0 THEN 'down less than 50%'
            ELSE 'flat or up' END AS trend_band,
       COUNT(*)             AS customers,
       SUM(revenue_to_date) AS clv
FROM customer_daily_snapshot
WHERE snapshot_date = {day(as_of)}
GROUP BY churn_status,
         CASE WHEN orders_to_date = 1 THEN '1 order'
              WHEN orders_to_date <= 3 THEN '2-3 orders'
              WHEN orders_to_date <= 9 THEN '4-9 orders'
              ELSE '10+ orders' END,
         CASE WHEN avg_days_between_orders IS NULL THEN 'one order only'
              WHEN avg_days_between_orders <= 14 THEN 'every 2 weeks or faster'
              WHEN avg_days_between_orders <= 30 THEN 'every 2-4 weeks'
              WHEN avg_days_between_orders <= 60 THEN 'every 1-2 months'
              ELSE 'less often' END,
         CASE WHEN spend_change_pct_30d IS NULL THEN 'no spend in the 30 days before'
              WHEN spend_change_pct_30d <= -50 THEN 'down 50% or more'
              WHEN spend_change_pct_30d < 0 THEN 'down less than 50%'
              ELSE 'flat or up' END
"""


def at_risk_customers(as_of: date, limit: int = 500) -> str:
    """The customers worth a re-engagement message: at risk, biggest lifetime value first."""
    return f"""
SELECT customer_id, days_since_last_order, orders_to_date, revenue_to_date,
       avg_days_between_orders, spend_change_pct_30d, rfm_segment, clv_tier, is_loyalty_as_of
FROM customer_daily_snapshot
WHERE snapshot_date = {day(as_of)} AND churn_status = 'at_risk'
ORDER BY revenue_to_date DESC
LIMIT {int(limit)}
"""


SEGMENTS_OVER_TIME = """
SELECT snapshot_date, rfm_segment, churn_status,
       COUNT(*)             AS customers,
       SUM(revenue_to_date) AS clv
FROM customer_daily_snapshot
GROUP BY snapshot_date, rfm_segment, churn_status
"""
