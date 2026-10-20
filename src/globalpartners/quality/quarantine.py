"""silver.quarantine: broken source rows, kept with their reasons (spec: Step3_Data_Model.md, section 6)."""
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F


def ensure_table(spark: SparkSession, table: str) -> None:
    spark.sql(f"""CREATE TABLE IF NOT EXISTS {table} (
                      source_table STRING, record_key STRING, record STRING, record_hash STRING, reasons STRING,
                      first_seen_batch_id STRING, last_seen_batch_id STRING,
                      first_seen_at TIMESTAMP, last_seen_at TIMESTAMP, times_seen INT, status STRING)
                  USING iceberg""")


def record(bad: DataFrame, table: str) -> int:
    """MERGE broken rows: a new row is inserted, a row seen again (new batch) gets times_seen + 1."""
    spark = bad.sparkSession
    ensure_table(spark, table)
    rows = (bad.withColumn("record_hash", F.sha2("record", 256))
               .dropDuplicates(["source_table", "record_hash"]))
    rows.createOrReplaceTempView("quarantine_source")
    spark.sql(f"""MERGE INTO {table} t USING quarantine_source s
                  ON t.source_table = s.source_table AND t.record_hash = s.record_hash
                  WHEN MATCHED AND t.last_seen_batch_id <> s._batch_id THEN UPDATE SET
                      t.last_seen_batch_id = s._batch_id, t.last_seen_at = current_timestamp(),
                      t.times_seen = t.times_seen + 1, t.reasons = s.reasons
                  WHEN NOT MATCHED THEN INSERT
                      (source_table, record_key, record, record_hash, reasons, first_seen_batch_id,
                       last_seen_batch_id, first_seen_at, last_seen_at, times_seen, status)
                      VALUES (s.source_table, s.record_key, s.record, s.record_hash, s.reasons, s._batch_id,
                              s._batch_id, current_timestamp(), current_timestamp(), 1, 'open')""")
    return rows.count()


def resolve(silver_keys: DataFrame, source_table: str, table: str) -> None:
    """Mark open quarantine rows as resolved when a valid row with the same key has reached silver."""
    spark = silver_keys.sparkSession
    ensure_table(spark, table)
    silver_keys.select(F.concat_ws("|", "order_id", "lineitem_id").alias("record_key")).distinct() \
               .createOrReplaceTempView("valid_keys")
    spark.sql(f"""MERGE INTO {table} t USING valid_keys s
                  ON t.record_key = s.record_key AND t.source_table = '{source_table}' AND t.status = 'open'
                  WHEN MATCHED THEN UPDATE SET t.status = 'resolved'""")