"""Run SQL statements on SQL Server through Spark's JDBC driver (no sqlcmd needed, works on AWS Glue)."""
import re

from pyspark.sql import SparkSession

from globalpartners.common.credentials import login
from globalpartners.common.spark import jdbc_url


def split_batches(script: str) -> list[str]:
    """Split a T-SQL script on its GO lines, like sqlcmd does."""
    return [b.strip() for b in re.split(r"^\s*GO\s*$", script, flags=re.MULTILINE | re.IGNORECASE) if b.strip()]


def execute(spark: SparkSession, db: dict, batches: list[str], database: str | None = None,
            admin: bool = True) -> list[list[tuple]]:
    """Run batches in order on one connection; return the rows of each batch's last result set."""
    user, password = login(db, admin=admin)
    jvm = spark.sparkContext._jvm
    jvm.java.lang.Class.forName("com.microsoft.sqlserver.jdbc.SQLServerDriver")
    connection = jvm.java.sql.DriverManager.getConnection(jdbc_url(db, database=database), user, password)
    results = []
    try:
        for batch in batches:
            statement = connection.createStatement()
            has_rows, rows = statement.execute(batch), []
            while True:
                if has_rows:
                    result = statement.getResultSet()
                    columns = result.getMetaData().getColumnCount()
                    rows = []
                    while result.next():
                        rows.append(tuple(result.getString(i) for i in range(1, columns + 1)))
                elif statement.getUpdateCount() == -1:
                    break
                has_rows = statement.getMoreResults()
            statement.close()
            results.append(rows)
    finally:
        connection.close()
    return results
