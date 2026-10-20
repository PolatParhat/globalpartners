"""Small column helpers shared by the silver transformations."""
from pyspark.sql import Column, DataFrame, Window
from pyspark.sql import functions as F


def clean_text(col: str) -> Column:
    """Trim spaces; an empty string becomes NULL."""
    trimmed = F.trim(F.col(col))
    return F.when(trimmed == "", None).otherwise(trimmed)


def collapse_spaces(col: str) -> Column:
    """Trim, collapse repeated spaces (and line breaks) into one space; empty becomes NULL."""
    collapsed = F.trim(F.regexp_replace(F.col(col), r"\s+", " "))
    return F.when(collapsed == "", None).otherwise(collapsed)


def row_hash(cols: list[str]) -> Column:
    """SHA-256 fingerprint of the business columns; NULLs are hashed as a marker."""
    return F.sha2(F.concat_ws("||", *[F.coalesce(F.col(c).cast("string"), F.lit("<null>")) for c in cols]), 256)


def failed_rules(checks: list[tuple[Column, str]]) -> Column:
    """Array of the reasons whose condition is true for this row (empty array = row is valid)."""
    return F.array_compact(F.array(*[F.when(condition, F.lit(reason)) for condition, reason in checks]))


def keep_newest(df: DataFrame, keys: list[str]) -> DataFrame:
    """One row per key: the most recently ingested copy (the lookback re-reads rows)."""
    newest_first = Window.partitionBy(*keys).orderBy(F.col("_ingested_at").desc())
    return df.withColumn("_rn", F.row_number().over(newest_first)).where("_rn = 1").drop("_rn") 