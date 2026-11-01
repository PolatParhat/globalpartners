"""location_summary: orders and revenue use sales scope, customer counts use customer rules."""
from datetime import date
from decimal import Decimal

from globalpartners.metrics import location

ORDERS = ("order_id string, customer_id string, business_date date, restaurant_id string, order_revenue decimal(12,2), "
          "is_guest boolean, is_non_customer_account boolean, is_test_data boolean")
D = date(2023, 3, 1)


def order(order_id, customer, restaurant, revenue, guest=False, faulty=False, test=False, when=D):
    return (order_id, customer, when, restaurant, Decimal(str(revenue)), guest, faulty, test)


def summary(spark, rules, *orders):
    df = location.location_summary(spark.createDataFrame(list(orders), ORDERS), rules)
    return {r.restaurant_id: r for r in df.collect()}


def test_orders_and_revenue_keep_guests_and_the_faulty_account(spark, rules):
    rows = summary(spark, rules,
                   order("o1", "u1", "r1", 10), order("o2", "GUEST", "r1", 5, guest=True),
                   order("o3", "bad", "r1", 7, faulty=True))
    assert rows["r1"].orders == 3 and rows["r1"].revenue == Decimal("22.00")


def test_customers_exclude_guests_and_the_faulty_account(spark, rules):
    rows = summary(spark, rules,
                   order("o1", "u1", "r1", 10), order("o2", "GUEST", "r1", 5, guest=True),
                   order("o3", "bad", "r1", 7, faulty=True))
    assert rows["r1"].customers == 1 and rows["r1"].repeat_customers == 0


def test_repeat_customer_has_two_orders_at_the_same_restaurant(spark, rules):
    rows = summary(spark, rules,
                   order("o1", "u1", "r1", 10), order("o2", "u1", "r1", 4),          # repeat at r1
                   order("o3", "u2", "r1", 6),                                       # one order at r1
                   order("o4", "u2", "r2", 6))                                       # one order at r2: not a repeat anywhere
    assert rows["r1"].customers == 2 and rows["r1"].repeat_customers == 1
    assert rows["r2"].customers == 1 and rows["r2"].repeat_customers == 0


def test_a_restaurant_with_only_guest_orders_has_zero_customers(spark, rules):
    rows = summary(spark, rules, order("o1", "GUEST", "r3", 5, guest=True))
    assert rows["r3"].orders == 1 and rows["r3"].customers == 0 and rows["r3"].repeat_customers == 0


def test_test_data_and_dates_outside_2023_are_out(spark, rules):
    rows = summary(spark, rules,
                   order("o1", "u1", "r1", 10), order("o2", "u1", "r1", 99, test=True),
                   order("o3", "u1", "r1", 50, when=date(2022, 12, 31)))
    assert rows["r1"].orders == 1 and rows["r1"].revenue == Decimal("10.00") and rows["r1"].repeat_customers == 0
