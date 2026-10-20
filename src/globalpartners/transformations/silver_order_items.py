"""bronze.order_items → silver.order_items (spec: docs/03_architecture/Step3_Data_Model.md, section 3)."""
from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from globalpartners.transformations.cleaning import (clean_text, collapse_spaces, failed_rules,
                                                     keep_newest, row_hash)

KEYS = ["order_id", "lineitem_id"]
URL_FRAGMENT = r"https?://\S*?#"   # pasted admin link inside a category (finding 34)
TEXT_COLUMNS = ["order_id", "lineitem_id", "restaurant_id", "app_name", "user_id",
                "printed_card_number", "currency"]
HASHED_COLUMNS = TEXT_COLUMNS + ["item_category", "item_name", "order_ts_utc", "is_loyalty",
                                 "item_price", "item_quantity"]


def transform(bronze: DataFrame, rules: dict) -> tuple[DataFrame, DataFrame]:
    """Return (valid rows for silver, broken rows for quarantine)."""
    original = F.to_json(F.struct(*[c for c in bronze.columns if not c.startswith("_")]))
    df = bronze.select(
        *[clean_text(c).alias(c) for c in TEXT_COLUMNS],
        F.col("creation_time_utc").alias("order_ts_utc"),
        "is_loyalty", "item_price", "item_quantity",
        clean_text("item_category").alias("item_category_raw"),
        collapse_spaces("item_name").alias("item_name"),
        "_batch_id", "_ingested_at",
        original.alias("_record"),
    )

    reasons = failed_rules([
        (F.col("order_id").isNull(), "missing order_id"),
        (F.col("lineitem_id").isNull(), "missing lineitem_id"),
        (F.col("restaurant_id").isNull(), "missing restaurant_id"),
        (F.col("order_ts_utc").isNull(), "missing creation_time_utc"),
        (F.col("item_price").isNull() | (F.col("item_price") < 0), "bad item_price"),
        (F.col("item_quantity").isNull() | (F.col("item_quantity") < 1), "bad item_quantity"),
        (F.col("is_loyalty").isNull(), "missing is_loyalty"),
        (F.coalesce(F.col("currency"), F.lit("")) != "USD", "unsupported currency"),
    ])
    df = df.withColumn("_reasons", reasons)

    bad = df.where(F.size("_reasons") > 0).select(
        F.lit("order_items").alias("source_table"),
        F.concat_ws("|", F.coalesce("order_id", F.lit("")), F.coalesce("lineitem_id", F.lit(""))).alias("record_key"),
        F.col("_record").alias("record"),
        F.concat_ws("; ", "_reasons").alias("reasons"),
        "_batch_id",
    )

    business_tz = rules["reporting_scope"]["business_timezone"]
    category = F.trim(F.regexp_replace("item_category_raw", URL_FRAGMENT, ""))
    good = (df.where(F.size("_reasons") == 0)
            .withColumn("order_ts_local", F.to_timestamp_ntz(F.from_utc_timestamp("order_ts_utc", business_tz)))
            .withColumn("business_date", F.to_date("order_ts_local"))
            .withColumn("order_hour_local", F.hour("order_ts_local"))
            .withColumn("item_category", category)
            .withColumn("is_category_repaired", F.coalesce(category != F.col("item_category_raw"), F.lit(False)))
            .withColumn("item_name_key", F.lower("item_name"))
            .withColumn("is_guest", F.col("user_id").isNull())
            .withColumn("is_test_data",
                        F.coalesce(F.col("app_name").isin(rules["test_data"]["excluded_apps"]), F.lit(False)))
            .withColumn("is_non_customer_account",
                        F.coalesce(F.col("user_id").isin(rules["customers"]["non_customer_ids"]), F.lit(False)))
            .withColumn("_row_hash", row_hash(HASHED_COLUMNS))
            .withColumn("_silver_updated_at", F.current_timestamp()))
    good = keep_newest(good, KEYS).select(
        "order_id", "lineitem_id", "restaurant_id", "app_name", "user_id", "printed_card_number",
        "is_loyalty", "currency", "order_ts_utc", "order_ts_local", "business_date", "order_hour_local",
        "item_category", "item_name", "item_name_key", "item_price", "item_quantity",
        "is_guest", "is_test_data", "is_non_customer_account", "is_category_repaired",
        "_batch_id", "_ingested_at", "_row_hash", "_silver_updated_at",
    )
    return good, bad