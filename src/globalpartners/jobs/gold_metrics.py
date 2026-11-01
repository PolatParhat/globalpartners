"""Step 5: gold metrics, rebuilt in full from the gold facts on every run.

    gold.sales_daily            date x restaurant x hour       (from fact_order)
    gold.sales_daily_category   date x restaurant x category   (from fact_order_line + dim_item)
    gold.customer_daily_snapshot  customer x day: CLV, tier, RFM, churn   (from fact_order)
    gold.location_summary       one row per restaurant: orders, revenue, customers, repeat customers (from fact_order)

Rebuilding is cheap at this size and lets late data correct past days (decision 2026-10-09).
"""
import argparse

from pyspark.sql import functions as F

from globalpartners.common.config import load_business_rules, load_environment
from globalpartners.common.job_args import parse_job_args
from globalpartners.common.run_log import logged_run
from globalpartners.common.spark import build_spark
from globalpartners.metrics import customer_snapshot, location, sales


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-id", help="run id to stamp on the snapshot (default: the latest batch in bronze)")
    args = parse_job_args(parser)

    env = load_environment()
    rules = load_business_rules()
    spark = build_spark("gold-metrics", env)
    spark.sparkContext.setLogLevel("ERROR")
    lake = env["catalog"]["name"]
    spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {lake}.gold")

    batch_id = args.batch_id or (spark.table(f"{lake}.bronze.order_items")
                                 .orderBy(F.col("_ingested_at").desc()).select("_batch_id").first()[0])
    print(f"batch {batch_id}")
    fact_order = spark.table(f"{lake}.gold.fact_order")
    fact_order_line = spark.table(f"{lake}.gold.fact_order_line")
    dim_item = spark.table(f"{lake}.gold.dim_item")

    with logged_run(spark, lake, "gold_metrics", batch_id) as run:
        daily = sales.sales_daily(fact_order, rules)
        daily.writeTo(f"{lake}.gold.sales_daily").using("iceberg").createOrReplace()
        by_category = sales.sales_daily_category(fact_order_line, dim_item, rules)
        by_category.writeTo(f"{lake}.gold.sales_daily_category").using("iceberg").createOrReplace()
        print(f"gold.sales_daily: {spark.table(f'{lake}.gold.sales_daily').count():,} rows | "
              f"gold.sales_daily_category: {spark.table(f'{lake}.gold.sales_daily_category').count():,} rows")

        by_location = location.location_summary(fact_order, rules)
        by_location.writeTo(f"{lake}.gold.location_summary").using("iceberg").createOrReplace()
        print(f"gold.location_summary: {spark.table(f'{lake}.gold.location_summary').count():,} rows")

        snapshot = customer_snapshot.customer_daily_snapshot(fact_order, rules, batch_id)
        (snapshot.writeTo(f"{lake}.gold.customer_daily_snapshot").using("iceberg")
                 .partitionedBy(F.months("snapshot_date")).createOrReplace())
        table = spark.table(f"{lake}.gold.customer_daily_snapshot")
        run["rows_in"], run["rows_out"] = fact_order.count(), table.count()
        print(f"gold.customer_daily_snapshot: {run['rows_out']:,} rows, "
              f"{table.select('customer_id').distinct().count():,} customers")
    spark.stop()


if __name__ == "__main__":
    main()
