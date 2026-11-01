"""Gold sales aggregates (spec: Step3_Data_Model.md, section 10).

Two tables, both sums only (ratios such as average order value are calculated after summing):

- sales_daily           business_date x restaurant_id x order_hour_local, from fact_order.
                        Has order counts, because one order is one row in fact_order.
- sales_daily_category  business_date x restaurant_id x item_category, from fact_order_line.
                        No order counts: an order with items from two categories would be counted twice.

Scope: the reporting years from config, test data excluded. Guests and the non-customer account
stay in (their sales are real).
"""
from pyspark.sql import DataFrame
from pyspark.sql import functions as F

DAILY_KEYS = ["business_date", "restaurant_id", "order_hour_local"]
CATEGORY_KEYS = ["business_date", "restaurant_id", "item_category"]


def in_sales_scope(df: DataFrame, rules: dict) -> DataFrame:
    """Rows inside the reporting dates and not test data."""
    scope = rules["reporting_scope"]
    return (df.where(~F.col("is_test_data"))
              .where(F.col("business_date").between(F.lit(scope["start_date"]), F.lit(scope["end_date"]))))


def _count_if(condition) -> F.Column:
    return F.sum(F.when(condition, 1).otherwise(0)).cast("long")


def sales_daily(fact_order: DataFrame, rules: dict) -> DataFrame:
    """One row per day x restaurant x hour: orders, revenue and the loyalty / guest / discount splits."""
    return (in_sales_scope(fact_order, rules)
            .groupBy(*DAILY_KEYS)
            .agg(F.count(F.lit(1)).alias("orders"),
                 F.sum("order_revenue").cast("decimal(14,2)").alias("revenue"),
                 F.sum("item_quantity").cast("long").alias("item_quantity"),
                 _count_if(F.col("is_loyalty")).alias("loyalty_orders"),
                 F.sum(F.when(F.col("is_loyalty"), F.col("order_revenue")).otherwise(0))
                  .cast("decimal(14,2)").alias("loyalty_revenue"),
                 _count_if(F.col("is_guest")).alias("guest_orders"),
                 _count_if(F.col("has_discount")).alias("discounted_orders"),
                 # discount_amount is <= 0 (negative option prices); revenue is already net of it,
                 # so gross revenue (before discounts) = revenue - discount_amount
                 F.sum("discount_amount").cast("decimal(14,2)").alias("discount_amount"),
                 F.sum(F.when(F.col("has_discount"), F.col("order_revenue")).otherwise(0))
                  .cast("decimal(14,2)").alias("discounted_revenue")))


def sales_daily_category(fact_order_line: DataFrame, dim_item: DataFrame, rules: dict) -> DataFrame:
    """One row per day x restaurant x item category: revenue, units and line count (no order count)."""
    categories = dim_item.select("item_key", "item_category")
    return (in_sales_scope(fact_order_line, rules)
            .join(categories, "item_key", "left")
            .groupBy(*CATEGORY_KEYS)
            .agg(F.sum("line_revenue").cast("decimal(14,2)").alias("revenue"),
                 F.sum("item_quantity").cast("long").alias("item_quantity"),
                 F.count(F.lit(1)).alias("line_count")))
