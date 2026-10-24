"""bronze → silver options: orphans, copy numbering, stable keys."""
from datetime import datetime
from decimal import Decimal

from globalpartners.transformations import silver_order_item_options

BRONZE = ("order_id string, lineitem_id string, option_group_name string, option_name string, "
          "option_price decimal(10,2), option_quantity int, _batch_id string, _ingested_at timestamp, "
          "_source_table string")


def option(order_id="o1", lineitem_id="l1", name="Oat Milk", price="0.75", batch="b1"):
    return (order_id, lineitem_id, "Milk", name, Decimal(price), 1, batch, datetime(2023, 1, 2), "order_item_options")


def run(spark, *rows):
    parents = spark.createDataFrame([("o1", "l1")], "order_id string, lineitem_id string")
    good, bad = silver_order_item_options.transform(spark.createDataFrame(list(rows), BRONZE), parents)
    return good.collect(), bad.collect()


def test_option_without_parent_line_is_quarantined(spark):
    # finding 29: orphan options
    good, bad = run(spark, option(order_id="o9"))
    assert good == [] and bad[0].reasons == "parent line not found"


def test_identical_copies_are_numbered_and_flagged(spark):
    good, _ = run(spark, option(), option(), option(name="Extra Shot", price="1.00"))
    oat = sorted((r for r in good if r.option_name == "Oat Milk"), key=lambda r: r.option_seq)
    assert [r.option_seq for r in oat] == [1, 2]
    assert oat[0].option_key != oat[1].option_key
    assert all(r.is_repeated_option for r in oat)
    assert [r.is_repeated_option for r in good if r.option_name == "Extra Shot"] == [False]


def test_option_key_is_the_same_when_reread_in_a_later_batch(spark):
    first, _ = run(spark, option(batch="b1"))
    again, _ = run(spark, option(batch="b2"))
    assert first[0].option_key == again[0].option_key
