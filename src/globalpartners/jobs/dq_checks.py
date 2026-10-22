"""Step 4.6: data-quality checks after a load.

Writes every result to lake.ops.dq_results and fails (exit code 1) if any check FAILs, so the
scheduler stops the run and alerts instead of publishing wrong numbers.
"""
import argparse
from datetime import datetime, timezone

from pyspark.sql import functions as F

from globalpartners.common.config import load_business_rules, load_environment
from globalpartners.common.run_log import logged_run
from globalpartners.common.spark import build_spark
from globalpartners.quality.checks import run_checks

COLUMNS = "run_id string, check_name string, status string, observed string, expected string, details string, checked_at timestamp"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-id", help="batch to check (default: the latest one in bronze)")
    args = parser.parse_args()

    env = load_environment()
    rules = load_business_rules()
    spark = build_spark("dq-checks", env)
    spark.sparkContext.setLogLevel("ERROR")
    lake = env["catalog"]["name"]
    table = f"{lake}.ops.dq_results"
    batch_id = args.batch_id or (spark.table(f"{lake}.bronze.order_items")
                                 .orderBy(F.col("_ingested_at").desc()).select("_batch_id").first()[0])

    with logged_run(spark, lake, "dq_checks", batch_id) as run:
        results = run_checks(spark, lake, env["source_db"], batch_id, rules)
        now = datetime.now(timezone.utc)
        rows = [(batch_id, r["check_name"], r["status"], r["observed"], r["expected"], r["details"], now) for r in results]

        spark.sql(f"CREATE TABLE IF NOT EXISTS {table} ({COLUMNS}) USING iceberg")
        spark.sql(f"DELETE FROM {table} WHERE run_id = '{batch_id}'")      # re-running a batch replaces its results
        spark.createDataFrame(rows, COLUMNS).writeTo(table).append()

        for r in results:
            print(f"{r['status']:<5} {r['check_name']:<40} observed {r['observed']:<26} expected {r['expected']}")
        failed = [r["check_name"] for r in results if r["status"] == "FAIL"]
        run["rows_in"], run["rows_out"] = len(results), len(results) - len(failed)
        if failed:
            raise RuntimeError(f"{len(failed)} data-quality check(s) failed: {', '.join(failed)}")
    spark.stop()


if __name__ == "__main__":
    main()