"""Column helpers in transformations/cleaning.py."""
from datetime import datetime

from pyspark.sql import functions as F

from globalpartners.transformations.cleaning import (clean_text, collapse_spaces, failed_rules,
                                                     keep_newest, row_hash)


def test_clean_text_trims_and_blank_becomes_null(spark):
    df = spark.createDataFrame([("  abc  ",), ("   ",), ("",)], "v string")
    assert [r.v for r in df.select(clean_text("v").alias("v")).collect()] == ["abc", None, None]


def test_collapse_spaces_joins_line_breaks(spark):
    df = spark.createDataFrame([("MANDARIN CARDAMOM\nJUICE",), ("  Iced   Latte ",)], "v string")
    assert [r.v for r in df.select(collapse_spaces("v").alias("v")).collect()] == \
        ["MANDARIN CARDAMOM JUICE", "Iced Latte"]


def test_row_hash_tells_null_from_empty_and_is_repeatable(spark):
    df = spark.createDataFrame([("a", None), ("a", ""), ("a", None)], "x string, y string")
    hashes = [r.h for r in df.select(row_hash(["x", "y"]).alias("h")).collect()]
    assert hashes[0] != hashes[1]          # NULL and "" are different values
    assert hashes[0] == hashes[2]          # same values → same fingerprint
    assert len(hashes[0]) == 64            # SHA-256 in hex


def test_failed_rules_lists_only_true_reasons(spark):
    df = spark.createDataFrame([(-1, None), (5, "x")], "price int, name string")
    reasons = failed_rules([(F.col("price") < 0, "bad price"), (F.col("name").isNull(), "missing name")])
    assert [r.r for r in df.select(reasons.alias("r")).collect()] == [["bad price", "missing name"], []]


def test_keep_newest_keeps_latest_ingested_copy(spark):
    df = spark.createDataFrame([("k1", "old", datetime(2023, 1, 1)), ("k1", "new", datetime(2023, 1, 2)),
                                ("k2", "only", datetime(2023, 1, 1))],
                               "key string, v string, _ingested_at timestamp")
    rows = {r.key: r.v for r in keep_newest(df, ["key"]).collect()}
    assert rows == {"k1": "new", "k2": "only"}
