"""Simulate the shops: copy one business day's orders from seed.* into the live dbo.* tables.

Calls the seed.replay_days procedure (sql/03). Locally the DAG can also call it with sqlcmd;
on AWS this job does it through JDBC.
"""
import argparse
from datetime import date

from globalpartners.common.config import load_environment
from globalpartners.common.job_args import parse_job_args
from globalpartners.common.spark import build_spark
from globalpartners.common.sqlserver import execute


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, type=date.fromisoformat, help="business day, YYYY-MM-DD")
    parser.add_argument("--to-date", type=date.fromisoformat, help="last day of a range (default: --date)")
    args = parse_job_args(parser)

    env = load_environment()
    spark = build_spark("replay-day", env)
    spark.sparkContext.setLogLevel("ERROR")
    to_date = args.to_date or args.date
    [rows] = execute(spark, env["source_db"], [f"EXEC seed.replay_days '{args.date}', '{to_date}'"])
    from_date, until, orders, lines, options = rows[0]
    print(f"replayed {from_date} → {until}: {orders} orders, {lines} lines, {options} options added")
    spark.stop()


if __name__ == "__main__":
    main()
