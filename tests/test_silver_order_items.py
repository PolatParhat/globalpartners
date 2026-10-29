"""bronze → silver order lines: validation, repairs, business date, flags, dedup."""
from datetime import datetime, timezone
from decimal import Decimal

from globalpartners.transformations import silver_order_items

BRONZE = ("app_name string, restaurant_id string, creation_time_utc timestamp, order_id string, user_id string, "
          "printed_card_number string, is_loyalty boolean, currency string, lineitem_id string, item_category string, "
          "item_name string, item_price decimal(10,2), item_quantity int, "
          "_batch_id string, _ingested_at timestamp, _source_table string")
UTC = timezone.utc                     # explicit: a naive datetime would use the computer's time zone
INGESTED = datetime(2023, 1, 2, 7, 0, tzinfo=UTC)


def line(**changes):
    """One valid bronze line; keyword arguments override single columns."""
    row = dict(app_name="Alltown Fresh", restaurant_id="r1", creation_time_utc=datetime(2023, 1, 1, 15, 0, tzinfo=UTC),
               order_id="o1", user_id="u1", printed_card_number=None, is_loyalty=False, currency="USD",
               lineitem_id="l1", item_category="Drip Coffee", item_name="Iced Latte",
               item_price=Decimal("4.39"), item_quantity=1,
               _batch_id="b1", _ingested_at=INGESTED, _source_table="order_items")
    row.update(changes)
    return tuple(row.values())


def run(spark, rules, *rows):
    good, bad = silver_order_items.transform(spark.createDataFrame(list(rows), BRONZE), rules)
    return good.collect(), bad.collect()


def test_valid_line_reaches_silver(spark, rules):
    good, bad = run(spark, rules, line())
    assert len(good) == 1 and bad == []
    assert good[0].item_name_key == "iced latte" and good[0].is_guest is False


def test_malformed_line_is_quarantined_with_reasons(spark, rules):
    # finding 8: blank lineitem_id, quantity 0
    good, bad = run(spark, rules, line(lineitem_id=" ", item_quantity=0))
    assert good == []
    assert bad[0].reasons == "missing lineitem_id; bad item_quantity"
    assert bad[0].record_key == "o1|"


def test_category_url_fragment_is_removed_and_flagged(spark, rules):
    # finding 34
    good, _ = run(spark, rules, line(item_category="Drip Chttps://www.opendining.net/admin#offee"))
    assert good[0].item_category == "Drip Coffee" and good[0].is_category_repaired is True


def test_business_date_uses_new_york_time(spark, rules):
    # 03:30 UTC on 1 Jan is still 31 Dec in New York
    good, _ = run(spark, rules, line(creation_time_utc=datetime(2023, 1, 1, 3, 30, tzinfo=UTC)))
    assert str(good[0].business_date) == "2022-12-31" and good[0].order_hour_local == 22


def test_guest_test_app_and_non_customer_flags(spark, rules):
    faulty = rules["customers"]["non_customer_ids"][0]
    test_app = rules["test_data"]["excluded_apps"][0]
    good, _ = run(spark, rules,
                  line(lineitem_id="guest", user_id=None),
                  line(lineitem_id="test", app_name=test_app),
                  line(lineitem_id="faulty", user_id=faulty))
    flags = {r.lineitem_id: (r.is_guest, r.is_test_data, r.is_non_customer_account) for r in good}
    assert flags == {"guest": (True, False, False), "test": (False, True, False), "faulty": (False, False, True)}


def test_lookback_reread_keeps_newest_copy(spark, rules):
    good, _ = run(spark, rules,
                  line(item_price=Decimal("4.39")),
                  line(item_price=Decimal("5.00"), _ingested_at=datetime(2023, 1, 3, 7, 0, tzinfo=UTC)))
    assert len(good) == 1 and good[0].item_price == Decimal("5.00")

def test_negative_price_is_quarantined(spark, rules):
    good, bad = run(spark, rules, line(item_price=Decimal("-1.00")))
    assert good == []
    assert bad[0].reasons == "bad item_price"