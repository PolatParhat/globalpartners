"""customer_daily_snapshot, piece by piece."""
from datetime import date
from decimal import Decimal

from globalpartners.metrics import customer_snapshot as snap

ORDERS = ("order_id string, customer_id string, business_date date, order_revenue decimal(12,2), "
          "is_guest boolean, is_non_customer_account boolean, is_test_data boolean")


def d(day: int) -> date:
    return date(2023, 1, day)


def orders_df(spark):
    return spark.createDataFrame([
        # u1 orders on day 1 (two orders) and day 4
        ("o1", "u1", d(1), Decimal("10.00"), False, False, False),
        ("o2", "u1", d(1), Decimal("5.50"), False, False, False),
        ("o3", "u1", d(4), Decimal("4.00"), False, False, False),
        # u2 starts on day 3
        ("o4", "u2", d(3), Decimal("7.00"), False, False, False),
        # not customers: a guest, the faulty account, test data
        ("o5", "GUEST", d(2), Decimal("3.00"), True, False, False),
        ("o6", "bad", d(2), Decimal("9.00"), False, True, False),
        ("o7", "tester", d(2), Decimal("1.00"), False, False, True),
    ], ORDERS)


def test_calendar_is_dense_from_first_order_to_last_loaded_day(spark, rules):
    rows = snap.customer_calendar(orders_df(spark), rules).collect()
    by_customer = {}
    for r in rows:
        by_customer.setdefault(r.customer_id, {})[r.snapshot_date] = r
    assert set(by_customer) == {"u1", "u2"}                      # guest, faulty account and test data are out
    assert sorted(by_customer["u1"]) == [d(1), d(2), d(3), d(4)]  # days 2 and 3 have no order but are kept
    assert sorted(by_customer["u2"]) == [d(3), d(4)]              # starts at its own first order


def test_days_without_orders_are_zero_and_order_days_are_summed(spark, rules):
    rows = {(r.customer_id, r.snapshot_date): r for r in snap.customer_calendar(orders_df(spark), rules).collect()}
    first = rows[("u1", d(1))]
    assert first.orders_on_day == 2 and first.revenue_on_day == Decimal("15.50")
    empty = rows[("u1", d(2))]
    assert empty.orders_on_day == 0 and empty.revenue_on_day == Decimal("0.00")
    assert empty.first_order_date == d(1)


def test_last_loaded_day_comes_from_all_sales_including_guests(spark, rules):
    only_guest_later = orders_df(spark).union(spark.createDataFrame(
        [("o8", "GUEST", d(6), Decimal("2.00"), True, False, False)], ORDERS))
    days = [r.snapshot_date for r in snap.customer_calendar(only_guest_later, rules).where("customer_id = 'u2'").collect()]
    assert max(days) == d(6)                                      # the data is loaded until day 6
