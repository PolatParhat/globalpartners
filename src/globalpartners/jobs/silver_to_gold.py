"""Step 4.5: silver → gold (star schema).

Facts: only the orders a batch added or changed in silver are rebuilt and MERGEd ("affected orders").
Dimensions: rebuilt in full every run (they are small).
"""
import argparse

from pyspark.sql import functions as F

from globalpartners.common.config import load_business_rules, load_environment
from globalpartners.common.run_log import logged_run
from globalpartners.common.spark import build_spark
from globalpartners.common.tables import merge_into
from globalpartners.transformations import gold_dimensions as dims
from globalpartners.transformations import gold_facts as facts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-id", help="batch whose silver changes to apply (default: the latest one in bronze)")
    args = parser.parse_args()

    env = load_environment()
    rules = load_business_rules()
    spark = build_spark("silver-to-gold", env)
    spark.sparkContext.setLogLevel("ERROR")
    lake = env["catalog"]["name"]
    spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {lake}.gold")

    batch_id = args.batch_id or (spark.table(f"{lake}.bronze.order_items")
                                 .orderBy(F.col("_ingested_at").desc()).select("_batch_id").first()[0])
    lines = spark.table(f"{lake}.silver.order_items")
    options = spark.table(f"{lake}.silver.order_item_options")
    print(f"batch {batch_id}")

    with logged_run(spark, lake, "silver_to_gold", batch_id) as run:
        # Facts: orders whose lines or options this batch inserted or changed in silver
        affected = (lines.where(F.col("_batch_id") == batch_id).select("order_id")
                    .union(options.where(F.col("_batch_id") == batch_id).select("order_id"))
                    .distinct())
        affected_lines = lines.join(affected, "order_id", "left_semi")
        affected_options = options.join(affected, "order_id", "left_semi")
        fact_lines = facts.fact_order_line(affected_lines, affected_options, rules).cache()
        merge_into(fact_lines, f"{lake}.gold.fact_order_line", facts.LINE_KEYS)
        fact_orders = facts.fact_order(fact_lines, affected_lines)
        merge_into(fact_orders, f"{lake}.gold.fact_order", facts.ORDER_KEYS)
        run["rows_in"], run["rows_out"] = affected.count(), fact_lines.count()
        print(f"affected orders: {run['rows_in']:,} | fact_order_line rows merged: {run['rows_out']:,}")

        # Dimensions: rebuilt from all of silver
        built = {
            "dim_customer": dims.dim_customer(lines),
            "dim_location": dims.dim_location(lines),
            "dim_item": dims.dim_item(lines),
            "dim_app": dims.dim_app(lines, rules),
            "dim_date": dims.dim_date(spark, lines, spark.table(f"{lake}.silver.date_dim"), rules),
        }
        for name, df in built.items():
            df.writeTo(f"{lake}.gold.{name}").using("iceberg").createOrReplace()
            print(f"gold.{name}: {spark.table(f'{lake}.gold.{name}').count():,} rows")
    spark.stop()


if __name__ == "__main__":
    main()