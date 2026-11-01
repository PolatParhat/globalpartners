"""Build a full-year DEMO lake for developing the dashboard. Touches no database and not your real lake.

Why: the real local lake holds 3 replayed days, which cannot show seasonality, rankings or churn.
This script runs the same transformations as the pipeline on the whole raw seed (2023) in memory and
writes only the four gold metric tables, as Iceberg tables, into a separate folder (default: lake_demo/).

    docker compose exec spark spark-submit scripts/build_demo_lake.py

Then start the dashboard against it:  DASHBOARD_WAREHOUSE=/home/hadoop/workspace/lake_demo
(see docker-compose.yml, service `dashboard`, and README "Dashboard").
"""
import argparse

from pyspark.sql import functions as F

from globalpartners.common.config import load_business_rules
from globalpartners.common.spark import build_spark
from globalpartners.jobs.load_seed import TIMESTAMP_FORMAT, read_csv, to_bool
from globalpartners.metrics import customer_snapshot, location, sales
from globalpartners.transformations import gold_dimensions as dims
from globalpartners.transformations import gold_facts as facts
from globalpartners.transformations import silver_order_item_options, silver_order_items

LAKE = "lake"                                     # the catalog name the dashboard queries use


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", default="/home/hadoop/workspace/data/raw", help="folder with the seed CSVs")
    parser.add_argument("--out", default="/home/hadoop/workspace/lake_demo", help="demo lake folder (created)")
    args = parser.parse_args()

    rules = load_business_rules()
    env = {"catalog": {"name": LAKE, "type": "hadoop", "warehouse": args.out}}
    spark = build_spark("build-demo-lake", env)
    spark.sparkContext.setLogLevel("ERROR")
    spark.conf.set("spark.sql.shuffle.partitions", "8")

    items = read_csv(spark, args.raw, "order_items").select(
        "app_name", "restaurant_id", F.to_timestamp("creation_time_utc", TIMESTAMP_FORMAT).alias("creation_time_utc"),
        "order_id", "user_id", "printed_card_number", to_bool("is_loyalty").alias("is_loyalty"),
        "currency", "lineitem_id", "item_category", "item_name",
        F.col("item_price").cast("decimal(10,2)").alias("item_price"),
        F.col("item_quantity").cast("int").alias("item_quantity"),
    ).withColumn("_batch_id", F.lit("demo")).withColumn("_ingested_at", F.current_timestamp())
    options = read_csv(spark, args.raw, "order_item_options").select(
        "order_id", "lineitem_id", "option_group_name", "option_name",
        F.col("option_price").cast("decimal(10,2)").alias("option_price"),
        F.col("option_quantity").cast("int").alias("option_quantity"),
    ).withColumn("_batch_id", F.lit("demo")).withColumn("_ingested_at", F.current_timestamp())

    lines, _ = silver_order_items.transform(items, rules)
    opts, _ = silver_order_item_options.transform(options, lines)
    lines, opts = lines.cache(), opts.cache()
    fact_lines = facts.fact_order_line(lines, opts, rules).cache()
    fact_orders = facts.fact_order(fact_lines, lines).cache()
    dim_item = dims.dim_item(lines)

    spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {LAKE}.gold")
    tables = {
        "sales_daily": sales.sales_daily(fact_orders, rules),
        "sales_daily_category": sales.sales_daily_category(fact_lines, dim_item, rules),
        "location_summary": location.location_summary(fact_orders, rules),
        "customer_daily_snapshot": customer_snapshot.customer_daily_snapshot(fact_orders, rules, "demo"),
    }
    for name, df in tables.items():
        writer = df.writeTo(f"{LAKE}.gold.{name}").using("iceberg")
        if name == "customer_daily_snapshot":
            writer = writer.partitionedBy(F.months("snapshot_date"))
        writer.createOrReplace()
        print(f"{LAKE}.gold.{name}: {spark.table(f'{LAKE}.gold.{name}').count():,} rows")
    spark.stop()


if __name__ == "__main__":
    main()
