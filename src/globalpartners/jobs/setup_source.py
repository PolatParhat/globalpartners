"""Create the source database: run sql/01–03 (database + read-only login, tables, replay procedure).

Locally the same scripts can be run with sqlcmd; on AWS there is no sqlcmd, so this job runs them
through JDBC as the admin login.

WARNING: not safe to repeat on a database that holds data. Scripts 01 and 03 check before they create,
but script 02 DROPs and recreates dbo.order_items, dbo.order_item_options, dbo.date_dim, seed.order_items and
seed.order_item_options, which empties them. Run this job once on a new database (up.sh does). To restore
after a wipe: load_seed, then replay_day for the days that were loaded.
"""
import argparse

from globalpartners.common.config import load_environment, project_file
from globalpartners.common.credentials import login
from globalpartners.common.job_args import parse_job_args
from globalpartners.common.spark import build_spark
from globalpartners.common.sqlserver import execute, split_batches

SCRIPTS = ["sql/01_create_database.sql", "sql/02_create_tables.sql", "sql/03_replay_procedure.sql"]


def main() -> None:
    parse_job_args(argparse.ArgumentParser())
    env = load_environment()
    spark = build_spark("setup-source", env)
    spark.sparkContext.setLogLevel("ERROR")
    db = env["source_db"]
    _, etl_password = login(db)                       # the read-only login's password, set by script 01
    for script in SCRIPTS:
        sql = project_file(script).read_text().replace("$(ETL_PASSWORD)", etl_password)
        batches = split_batches(sql)
        execute(spark, db, batches, database="master")
        print(f"{script}: {len(batches)} batches run")
    spark.stop()


if __name__ == "__main__":
    main()
