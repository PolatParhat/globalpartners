"""bronze.order_item_options → silver.order_item_options (spec: Step3_Data_Model.md, section 4)."""
from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F

from globalpartners.transformations.cleaning import collapse_spaces, clean_text, failed_rules, keep_newest, row_hash

IDENTITY = ["order_id", "lineitem_id", "option_group_name", "option_name", "option_price"]
HASHED_COLUMNS = IDENTITY + ["option_quantity"]


def transform(bronze: DataFrame, silver_lines: DataFrame) -> tuple[DataFrame, DataFrame]:
    """Return (valid rows for silver, broken rows for quarantine).

    silver_lines: the order_id/lineitem_id keys of silver.order_items (an option needs its parent line).
    """
    original = F.to_json(F.struct(*[c for c in bronze.columns if not c.startswith("_")]))
    df = bronze.select(
        clean_text("order_id").alias("order_id"),
        clean_text("lineitem_id").alias("lineitem_id"),
        collapse_spaces("option_group_name").alias("option_group_name"),
        collapse_spaces("option_name").alias("option_name"),
        "option_price", "option_quantity", "_batch_id", "_ingested_at",
        original.alias("_record"),
    )
    parents = silver_lines.select("order_id", "lineitem_id").distinct().withColumn("_has_parent", F.lit(True))
    df = df.join(parents, ["order_id", "lineitem_id"], "left")

    reasons = failed_rules([
        (F.col("order_id").isNull(), "missing order_id"),
        (F.col("lineitem_id").isNull(), "missing lineitem_id"),
        (F.col("option_group_name").isNull(), "missing option_group_name"),
        (F.col("option_name").isNull(), "missing option_name"),
        (F.col("option_price").isNull(), "missing option_price"),
        (F.col("option_quantity").isNull() | (F.col("option_quantity") < 1), "bad option_quantity"),
        (F.col("_has_parent").isNull(), "parent line not found"),
    ])
    df = df.withColumn("_reasons", reasons)

    bad = df.where(F.size("_reasons") > 0).select(
        F.lit("order_item_options").alias("source_table"),
        F.concat_ws("|", F.coalesce("order_id", F.lit("")), F.coalesce("lineitem_id", F.lit(""))).alias("record_key"),
        F.col("_record").alias("record"),
        F.concat_ws("; ", "_reasons").alias("reasons"),
        "_batch_id",
    )

    copies = Window.partitionBy("_batch_id", *IDENTITY).orderBy("option_quantity")
    group = Window.partitionBy("_batch_id", *IDENTITY)
    good = (df.where(F.size("_reasons") == 0)
            .withColumn("option_seq", F.row_number().over(copies))
            .withColumn("is_repeated_option", F.count(F.lit(1)).over(group) > 1)
            .withColumn("option_key", F.sha2(F.concat_ws("||", *[F.col(c).cast("string") for c in IDENTITY + ["option_seq"]]), 256))
            .withColumn("option_name_key", F.lower("option_name"))
            .withColumn("is_discount", F.col("option_price") < 0)
            .withColumn("_row_hash", row_hash(HASHED_COLUMNS))
            .withColumn("_silver_updated_at", F.current_timestamp()))
    good = keep_newest(good, ["option_key"]).select(
        "order_id", "lineitem_id", "option_group_name", "option_name", "option_name_key",
        "option_price", "option_quantity", "option_seq", "option_key", "is_discount", "is_repeated_option",
        "_batch_id", "_ingested_at", "_row_hash", "_silver_updated_at",
    )
    return good, bad