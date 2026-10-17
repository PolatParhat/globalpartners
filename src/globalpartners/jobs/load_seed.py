"""Step 4.2: load the seed CSV files into SQL Server (seed.* tables and dbo.date_dim).

The CSV text is converted to typed columns here, once, with explicit formats.
Run after sql/01_create_database.sql and sql/02_create_tables.sql.
"""
import os

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from globalpartners.common.config import load_environment
from globalpartners.common.spark import build_spark, jdbc_url

TIMESTAMP_FORMAT = "yyyy-MM-dd'T'HH:mm:ss[.SSS]X"   # ISO 8601, 0-3 digit fraction, 'Z'
DATE_KEY_FORMAT = "dd-MM-yyyy"                      # date_dim is day-first


def read_csv(spark, raw_dir: str, name: str) -> DataFrame:
    """Read a raw CSV as strings with lowercase column names."""
    df = spark.read.csv(f"{raw_dir}/{name}.csv", header=True, multiLine=True, escape='"')
    return df.toDF(*[c.strip().lower() for c in df.columns])


def to_bool(col: str):
    """'TRUE' -> true, 'FALSE' -> false, anything else -> NULL."""
    return F.when(F.col(col) == "TRUE", True).when(F.col(col) == "FALSE", False)


def write_table(df: DataFrame, table: str, db: dict) -> None:
    """Replace the rows of an existing SQL Server table, keeping its column definitions."""
    (df.write.format("jdbc")
       .option("url", jdbc_url(db))
       .option("dbtable", table)
       .option("user", os.environ[db["user_env"]])
       .option("password", os.environ[db["password_env"]])
       .option("truncate", "true")          # empty the table instead of dropping it
       .option("batchsize", 10000)
       .mode("overwrite")
       .save())


def main() -> None:
    env = load_environment()
    spark = build_spark("load-seed", env)
    spark.sparkContext.setLogLevel("ERROR")
    raw, db = env["raw_dir"], env["source_db"]

    items = read_csv(spark, raw, "order_items").select(
        "app_name", "restaurant_id",
        F.to_timestamp("creation_time_utc", TIMESTAMP_FORMAT).alias("creation_time_utc"),
        "order_id", "user_id", "printed_card_number",
        to_bool("is_loyalty").alias("is_loyalty"),
        "currency", "lineitem_id", "item_category", "item_name",
        F.col("item_price").cast("decimal(10,2)").alias("item_price"),
        F.col("item_quantity").cast("int").alias("item_quantity"),
    )
    options = read_csv(spark, raw, "order_item_options").select(
        "order_id", "lineitem_id", "option_group_name", "option_name",
        F.col("option_price").cast("decimal(10,2)").alias("option_price"),
        F.col("option_quantity").cast("int").alias("option_quantity"),
    )
    dates = read_csv(spark, raw, "date_dim").select(
        F.to_date("date_key", DATE_KEY_FORMAT).alias("date_key"),
        F.col("year").cast("int").alias("year"),
        F.col("month").cast("int").alias("month"),
        F.col("week").cast("int").alias("week"),        "day_of_week",
        to_bool("is_weekend").alias("is_weekend"),
        to_bool("is_holiday").alias("is_holiday"),
        "holiday_name",
    )

    # Stop before writing anything if a value could not be converted
    bad_times = items.where(F.col("creation_time_utc").isNull()).count()
    bad_dates = dates.where(F.col("date_key").isNull()).count()
    if bad_times or bad_dates:
        raise ValueError(f"unparsed values: {bad_times} timestamps, {bad_dates} dates")

    for df, table in [(items, "seed.order_items"), (options, "seed.order_item_options"), (dates, "dbo.date_dim")]:
        write_table(df, table, db)
        print(f"{table}: {df.count():,} rows")
    spark.stop()


if __name__ == "__main__":
    main()