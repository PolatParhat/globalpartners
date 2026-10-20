"""Helpers for writing Iceberg tables"""
from pyspark.sql import DataFrame

def merge_into(df: DataFrame, target: str, keys: list[str]) -> None:
  """MERGE row into Iceberg table: insert new keys, update rows whose _row_hash changed.
  The Table is created from the DataFrame's columns on first use.
  """
  spark = df.sparkSession
  if not spark.catalog.tableExists(target):
    df.limit(0).writeTo(target).using("iceberg").create()
  df.createOrReplaceTempView("merge_source")
  on = " AND ".join(f"t.{k} = s.{k}" for k in keys)
  spark.sql(f"""MERGE INTO {target} t USING merge_source s ON {on}
                WHEN MATCHED AND t._row_hash <> s._row_hash Then UPDATE SET *
                WHEN NOT MATCHED THEN INSERT *""")
  