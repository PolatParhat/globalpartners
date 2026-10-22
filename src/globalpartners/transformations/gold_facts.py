"""silver → gold facts (spec: Step3_Data_Model.md, section 8)."""
from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from globalpartners.transformations.cleaning import row_hash
from globalpartners.transformations.gold_dimensions import GUEST, item_key

LINE_KEYS = ["order_id", "lineitem_id"]
ORDER_KEYS = ["order_id"]


def fact_order_line(lines: DataFrame, options: DataFrame, rules: dict) -> DataFrame:
    """One row per order line, with line revenue = item_price + option revenue."""
    if rules["revenue"]["repeated_options"] == "count_once":
        options = options.where(F.col("option_seq") == 1)        # identical copies counted once
    per_line = options.groupBy(*LINE_KEYS).agg(
        F.count(F.lit(1)).alias("option_count"),
        F.sum("option_price").alias("option_price_sum"),
        F.sum(F.when(F.col("option_price") < 0, F.col("option_price")).otherwise(0)).alias("discount_price_sum"),
    )
    per_unit = rules["revenue"]["option_price_times_item_quantity"]
    multiplier = F.col("item_quantity") if per_unit else F.lit(1)

    df = (lines.join(per_line, LINE_KEYS, "left")
          .withColumn("option_count", F.coalesce("option_count", F.lit(0)))
          .withColumn("option_revenue", (F.coalesce("option_price_sum", F.lit(0)) * multiplier).cast("decimal(12,2)"))
          .withColumn("discount_amount", (F.coalesce("discount_price_sum", F.lit(0)) * multiplier).cast("decimal(12,2)"))
          .withColumn("item_revenue", F.col("item_price").cast("decimal(12,2)"))
          .withColumn("line_revenue", (F.col("item_revenue") + F.col("option_revenue")).cast("decimal(12,2)"))
          .withColumn("has_discount", F.col("discount_amount") < 0)
          .withColumn("customer_id", F.coalesce("user_id", F.lit(GUEST)))
          .withColumn("item_key", item_key()))
    columns = ["order_id", "lineitem_id", "business_date", "order_hour_local", "customer_id", "restaurant_id",
               "app_name", "item_key", "is_loyalty", "item_quantity", "item_revenue", "option_count",
               "option_revenue", "discount_amount", "line_revenue", "has_discount",
               "is_test_data", "is_guest", "is_non_customer_account"]
    return (df.select(*columns)
            .withColumn("_row_hash", row_hash(columns))
            .withColumn("_gold_updated_at", F.current_timestamp()))


def fact_order(fact_lines: DataFrame, lines: DataFrame) -> DataFrame:
    """One row per order, summed from its lines. Order-level fields are identical on every line."""
    order_time = lines.groupBy("order_id").agg(F.min("order_ts_local").alias("order_ts_local"))
    df = (fact_lines.groupBy("order_id")
          .agg(F.first("business_date").alias("business_date"),
               F.first("order_hour_local").alias("order_hour_local"),
               F.first("customer_id").alias("customer_id"),
               F.first("restaurant_id").alias("restaurant_id"),
               F.first("app_name").alias("app_name"),
               F.first("is_loyalty").alias("is_loyalty"),
               F.count(F.lit(1)).alias("line_count"),
               F.sum("item_quantity").alias("item_quantity"),
               F.sum("line_revenue").cast("decimal(12,2)").alias("order_revenue"),
               F.sum("discount_amount").cast("decimal(12,2)").alias("discount_amount"),
               F.max(F.col("is_test_data").cast("int")).cast("boolean").alias("is_test_data"),
               F.max(F.col("is_guest").cast("int")).cast("boolean").alias("is_guest"),
               F.max(F.col("is_non_customer_account").cast("int")).cast("boolean").alias("is_non_customer_account"))
          .withColumn("has_discount", F.col("discount_amount") < 0)
          .join(order_time, "order_id"))
    columns = ["order_id", "business_date", "order_ts_local", "order_hour_local", "customer_id", "restaurant_id",
               "app_name", "is_loyalty", "line_count", "item_quantity", "order_revenue", "discount_amount",
               "has_discount", "is_test_data", "is_guest", "is_non_customer_account"]
    return (df.select(*columns)
            .withColumn("_row_hash", row_hash(columns))
            .withColumn("_gold_updated_at", F.current_timestamp()))