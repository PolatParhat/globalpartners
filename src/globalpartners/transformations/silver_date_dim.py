"""bronze.date_dim → silver.date_dim (spec: Step3_Data_Model.md, section 5)."""
from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from globalpartners.transformations.cleaning import clean_text, failed_rules, keep_newest, row_hash

HASHED_COLUMNS = ["date", "year", "month", "iso_week", "day_of_week", "is_weekend", "is_holiday", "holiday_name"]


def transform(bronze: DataFrame) -> tuple[DataFrame, DataFrame]:
    """Return (valid rows for silver, broken rows for quarantine)."""
    original = F.to_json(F.struct(*[c for c in bronze.columns if not c.startswith("_")]))
    df = bronze.select(
        F.col("date_key").alias("date"),
        "year", "month",
        F.col("week").alias("iso_week"),            # the source week is the ISO 8601 week
        clean_text("day_of_week").alias("day_of_week"),
        "is_weekend", "is_holiday",
        clean_text("holiday_name").alias("holiday_name"),
        "_batch_id", "_ingested_at",
        original.alias("_record"),
    )
    df = df.withColumn("_reasons", failed_rules([(F.col("date").isNull(), "missing date_key")]))

    bad = df.where(F.size("_reasons") > 0).select(
        F.lit("date_dim").alias("source_table"),
        F.lit(None).cast("string").alias("record_key"),
        F.col("_record").alias("record"),
        F.concat_ws("; ", "_reasons").alias("reasons"),
        "_batch_id",
    )
    good = (df.where(F.size("_reasons") == 0).drop("_reasons", "_record")
            .withColumn("_row_hash", row_hash(HASHED_COLUMNS))
            .withColumn("_silver_updated_at", F.current_timestamp()))
    return keep_newest(good, ["date"]), bad