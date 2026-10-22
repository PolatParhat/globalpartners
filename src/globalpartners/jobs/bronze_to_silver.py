"""Step 4.4: bronze → silver for one extract batch.

Reads the rows a batch delivered to bronze, cleans and validates them, MERGEs valid rows into
lake.silver.* and records broken rows in lake.silver.quarantine. Safe to run again for the same batch.
"""
import argparse

from pyspark.sql import functions as F

from globalpartners.common.config import load_business_rules, load_environment
from globalpartners.common.run_log import logged_run
from globalpartners.common.spark import build_spark
from globalpartners.common.tables import merge_into
from globalpartners.quality import quarantine
from globalpartners.transformations import silver_date_dim, silver_order_item_options, silver_order_items


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-id", help="extract batch to process (default: the latest one in bronze)")
    args = parser.parse_args()

    env = load_environment()
    rules = load_business_rules()
    spark = build_spark("bronze-to-silver", env)
    spark.sparkContext.setLogLevel("ERROR")
    lake = env["catalog"]["name"]
    spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {lake}.silver")
    quarantine_table = f"{lake}.silver.quarantine"

    batch_id = args.batch_id or (spark.table(f"{lake}.bronze.order_items")
                                 .orderBy(F.col("_ingested_at").desc()).select("_batch_id").first()[0])
    print(f"batch {batch_id}")

    def bronze(table: str):
        return spark.table(f"{lake}.bronze.{table}").where(F.col("_batch_id") == batch_id)

    with logged_run(spark, lake, "bronze_to_silver", batch_id) as run:
        # 1. order lines
        lines, bad_lines = silver_order_items.transform(bronze("order_items"), rules)
        merge_into(lines, f"{lake}.silver.order_items", silver_order_items.KEYS)
        quarantine.resolve(lines, "order_items", quarantine_table)
        bad_line_count = quarantine.record(bad_lines, quarantine_table)
        print(f"silver.order_items: {lines.count():,} valid | quarantined {bad_line_count}")

        # 2. options (after the lines: an option needs its parent line in silver)
        options, bad_options = silver_order_item_options.transform(
            bronze("order_item_options"), spark.table(f"{lake}.silver.order_items"))
        merge_into(options, f"{lake}.silver.order_item_options", ["option_key"])
        bad_option_count = quarantine.record(bad_options, quarantine_table)
        print(f"silver.order_item_options: {options.count():,} valid | quarantined {bad_option_count}")

        # 3. calendar
        dates, bad_dates = silver_date_dim.transform(bronze("date_dim"))
        merge_into(dates, f"{lake}.silver.date_dim", ["date"])
        bad_date_count = quarantine.record(bad_dates, quarantine_table)
        print(f"silver.date_dim: {dates.count():,} valid | quarantined {bad_date_count}")

        run["rows_in"] = bronze("order_items").count()
        run["rows_out"] = lines.count()
        run["rows_quarantined"] = bad_line_count + bad_option_count + bad_date_count
    spark.stop()


if __name__ == "__main__":
    main()