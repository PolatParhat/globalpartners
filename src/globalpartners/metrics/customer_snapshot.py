"""gold.customer_daily_snapshot, built in small pure functions (spec: Step3_Data_Model.md, section 7).

Piece 1 (this file so far): the dense calendar, one row per customer per day with that day's orders and revenue.
"""
from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from globalpartners.metrics.sales import in_sales_scope


def customer_orders(fact_order: DataFrame, rules: dict) -> DataFrame:
    """Orders that count for customer metrics: in the reporting dates, no test data, no non-customer account, no guests."""
    orders = in_sales_scope(fact_order, rules).where(~F.col("is_non_customer_account"))
    if not rules["customers"]["guests_in_customer_metrics"]:
        orders = orders.where(~F.col("is_guest"))
    return orders


def customer_calendar(fact_order: DataFrame, rules: dict) -> DataFrame:
    """One row per customer per day, from their first order to the last loaded business day.

    Days without orders are kept (orders_on_day = 0, revenue_on_day = 0): recency, churn status and
    tiers change on those days too.
    """
    # The last loaded day is the same for every customer; it comes from all sales in scope (guests included).
    last_day = in_sales_scope(fact_order, rules).agg(F.max("business_date")).first()[0]

    orders = customer_orders(fact_order, rules)
    per_day = (orders.groupBy("customer_id", "business_date")
               .agg(F.count(F.lit(1)).alias("orders_on_day"),
                    F.sum("order_revenue").cast("decimal(14,2)").alias("revenue_on_day")))
    first_day = per_day.groupBy("customer_id").agg(F.min("business_date").alias("first_order_date"))

    days = (first_day
            .withColumn("snapshot_date", F.explode(F.sequence(F.col("first_order_date"), F.lit(last_day))))
            .select("snapshot_date", "customer_id", "first_order_date"))

    return (days.join(per_day.withColumnRenamed("business_date", "snapshot_date"),
                      ["snapshot_date", "customer_id"], "left")
            .withColumn("orders_on_day", F.coalesce("orders_on_day", F.lit(0)))
            .withColumn("revenue_on_day", F.coalesce("revenue_on_day", F.lit(0)).cast("decimal(14,2)")))
