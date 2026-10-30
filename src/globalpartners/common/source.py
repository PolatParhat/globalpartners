"""Read from the source database (SQL Server) as the read-only pipeline login."""
from pyspark.sql import DataFrame, SparkSession

from globalpartners.common.credentials import login
from globalpartners.common.spark import jdbc_url


def read_source(spark: SparkSession, db: dict, query: str) -> DataFrame:
    """Run a query on SQL Server as etl_reader; the query itself runs inside SQL Server."""
    user, password = login(db)
    return (spark.read.format("jdbc")
            .option("url", jdbc_url(db))
            .option("user", user)
            .option("password", password)
            .option("query", query)
            .load())