"""Read from the source database (SQL Server) as the read-only pipeline login."""
import os

from pyspark.sql import DataFrame, SparkSession

from globalpartners.common.spark import jdbc_url


def read_source(spark: SparkSession, db: dict, query: str) -> DataFrame:
    """Run a query on SQL Server as etl_reader; the query itself runs inside SQL Server."""
    return (spark.read.format("jdbc")
            .option("url", jdbc_url(db))
            .option("user", os.environ[db["reader_user_env"]])
            .option("password", os.environ[db["reader_password_env"]])
            .option("query", query)
            .load())