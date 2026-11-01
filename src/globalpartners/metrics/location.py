"""gold.location_summary: one row per restaurant for the whole reporting period (Step 6, location page).

    orders, revenue      all orders in sales scope (guests and the faulty account included, like sales_daily)
    customers            distinct known customers who ordered at this restaurant
    repeat_customers     of those, customers with 2 or more orders at this restaurant

Customer counts follow the customer rules (no guests, no faulty account), so they are smaller than the
order counts. The repeat rate (repeat_customers / customers) is calculated after summing, like every ratio
in the gold metrics. Customers are not additive across restaurants: one customer who ordered at two
restaurants is counted at both, so never add the `customers` column up.
"""
from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from globalpartners.metrics.customer_snapshot import customer_orders
from globalpartners.metrics.sales import in_sales_scope


def location_summary(fact_order: DataFrame, rules: dict) -> DataFrame:
    """One row per restaurant: orders, revenue, customers, repeat customers."""
    sales = (in_sales_scope(fact_order, rules)
             .groupBy("restaurant_id")
             .agg(F.count(F.lit(1)).alias("orders"),
                  F.sum("order_revenue").cast("decimal(14,2)").alias("revenue")))

    per_customer = customer_orders(fact_order, rules).groupBy("restaurant_id", "customer_id").agg(F.count(F.lit(1)).alias("n"))
    customers = per_customer.groupBy("restaurant_id").agg(
        F.count(F.lit(1)).cast("long").alias("customers"),
        F.sum(F.when(F.col("n") >= 2, 1).otherwise(0)).cast("long").alias("repeat_customers"))

    return (sales.join(customers, "restaurant_id", "left")
                 .withColumn("customers", F.coalesce("customers", F.lit(0)))
                 .withColumn("repeat_customers", F.coalesce("repeat_customers", F.lit(0))))
