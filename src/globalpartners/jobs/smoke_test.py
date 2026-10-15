"""Step 4.1 smoke test: config loads, Spark reads the raw CSV, reaches SQL Server, writes Iceberg."""
import os

from globalpartners.common.config import load_business_rules, load_environment, pipeline_env
from globalpartners.common.spark import build_spark, jdbc_url


def main() -> None:
    env = load_environment()
    rules = load_business_rules()
    spark = build_spark("smoke-test", env)
    spark.sparkContext.setLogLevel("ERROR")
    scope = rules["reporting_scope"]
    print(f"1. environment {pipeline_env()} | Spark {spark.version} | scope {scope['start_date']} → {scope['end_date']}")

    items = spark.read.csv(f"{env['raw_dir']}/order_items.csv", header=True, multiLine=True, escape='"')
    print(f"2. raw order_items rows: {items.count():,} (expected 203,519)")

    db = env["source_db"]
    row = (spark.read.format("jdbc")
           .option("url", jdbc_url(db, database="master"))      # the globalpartners database is created in 4.2
           .option("user", os.environ[db["user_env"]])
           .option("password", os.environ[db["password_env"]])
           .option("query", "SELECT @@VERSION AS version, CAST(encrypt_option AS varchar(5)) AS encrypted "
                            "FROM sys.dm_exec_connections WHERE session_id = @@SPID")
           .load().first())
    print(f"3. SQL Server: {row['version'].splitlines()[0].strip()} | encrypted connection: {row['encrypted']}")

    table = f"{env['catalog']['name']}.smoke.hello"
    spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {env['catalog']['name']}.smoke")
    spark.sql(f"CREATE OR REPLACE TABLE {table} (id INT, msg STRING) USING iceberg")
    spark.sql(f"INSERT INTO {table} VALUES (1, 'local foundation works')")
    print(f"4. Iceberg: {spark.table(table).first()['msg']}")
    spark.sql(f"DROP TABLE {table} PURGE")
    spark.stop()


if __name__ == "__main__":
    main()