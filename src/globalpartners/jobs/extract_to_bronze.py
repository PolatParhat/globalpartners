"""Step 4.3: extract from SQL Server into the bronze layer.

- order_items: rows created after (watermark - lookback days); everything on the first run
- order_item_options: the options of those orders (options have no timestamp of their own)
- date_dim: the whole table every run
Rows are appended to lake.bronze.* as received, with audit columns. The watermark in
lake.ops.watermarks moves forward only after every table has been written.
"""

import argparse
import os
from datetime import datetime, timedelta, timezone

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from globalpartners.common.config import load_business_rules, load_environment
from globalpartners.common.spark import build_spark, jdbc_url

WATERMARKS = "ops.watermarks"

def read_source(spark: SparkSession, db: dict, query: str) -> DataFrame:
  """Run a query on SQL Server as the read-only pipeline login."""
  return (
    spark.read.format("jdbc")
      .option("url", jdbc_url(db))
      .option("user", os.environ[db["reader_user_env"]])
      .option("password", os.environ[db["reader_password_env"]])
      .option("query", query)
      .load()
  )


def get_watermark(spark: SparkSession, catalog: str, source_table: str) -> datetime | None:
  """Newest creation_time_utc already loaded for a source table, or None on the first run."""
  spark.sql(f"""CREATE TABLE IF NOT EXISTS {catalog}.{WATERMARKS} (
              source_table STRING, last_loaded_ts TIMESTAMP, batch_id STRING, updated_at TIMESTAMP)
            USING iceberg""")
  row = (spark.table(f"{catalog}.{WATERMARKS}")
         .where(F.col("source_table") == source_table)
         .select("last_loaded_ts").first())
  return row["last_loaded_ts"] if row else None

def append_bronze(df: DataFrame, catalog: str, source_table: str, batch_id: str) -> int:
    """Append rows to lake.bronze.<source_table> with audit columns; create the table on first use."""  
    target = f"{catalog}.bronze.{source_table}"
    rows = (df.withColumn("_batch_id", F.lit(batch_id))
            .withColumn("_ingested_at", F.current_timestamp())
            .withColumn("_source_table", F.lit(f"dbo.{source_table}")))
    if not df.sparkSession.catalog.tableExists(target):
      rows.limit(0).writeTo(target).using("iceberg").create()
    rows.writeTo(target).append()
    return rows.count()  

def set_watermark(spark: SparkSession, catalog: str, source_table: str, ts: datetime, batch_id: str) -> None:
  """Insert or update the watermark row for a source table."""
  spark.createDataFrame([(source_table, ts, batch_id)], "source_table string, last_loaded_ts timestamp, batch_id string") \
      .withColumn("updated_at", F.current_timestamp()).createOrReplaceTempView("new_watermark")
  spark.sql(f"""MERGE INTO {catalog}.{WATERMARKS} t USING new_watermark s
            ON t.source_table = s.source_table
            WHEN MATCHED THEN UPDATE SET *
            WHEN NOT MATCHED THEN INSERT *""")


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument("--batch-id", default=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
  batch_id = parser.parse_args().batch_id
  print(batch_id)
  
  env = load_environment()
  print(env)
  rules = load_business_rules()
  spark = build_spark("extract-to-bronze", env)
  spark.sparkContext.setLogLevel("ERROR")
  catalog, db = env["catalog"]["name"], env["source_db"]
  spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {catalog}.bronze")
  spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {catalog}.ops")
  
  watermark = get_watermark(spark, catalog, "order_items")
  if watermark is None:
    where, window = "", "first run: everything"
  else:
    window_start = watermark - timedelta(days=rules["extract"]["lookback_days"])
    where = f"WHERE creation_time_utc > '{window_start:%Y-%m-%d %H:%M:%S.%f}'"
    window  = f"after {window_start} (watermark {watermark} minus {rules['extract']['lookback_days']}) days"
  print(f"batch {batch_id} | window: {window}")
  
  items = read_source(spark, db, f"SELECT * FROM dbo.order_items {where}").cache()
  options = read_source(spark, db, f"""SELECT o.* FROM dbo.order_item_options AS o
                                         {"" if not where else f"WHERE o.order_id IN (SELECT order_id FROM dbo.order_items {where})"}""")
  dates = read_source(spark, db, "SELECT * FROM dbo.date_dim")
  
  for df, name in [(items, "order_items"), (options, "order_item_options"),(dates, "date_dim")]:
    print(f"bronze.{name}: +{append_bronze(df, catalog, name, batch_id):,} rows")
  
  newest = items.agg(F.max("creation_time_utc")).first()[0]
  if newest is not None and (watermark is None or newest > watermark):
    set_watermark(spark, catalog, "order_items", newest, batch_id)
    print(f"watermark moved to {newest}")
  else:
    print("no newer orders; watermark unchanged")
  spark.stop()
  
    
  

if __name__ == "__main__":
  main()