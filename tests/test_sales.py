"""gold sales aggregates: scope, splits, and the tie-out between the two tables."""
from datetime import date
from decimal import Decimal

from globalpartners.metrics import sales

ORDERS = ("order_id string, business_date date, order_hour_local int, restaurant_id string, "
          "is_loyalty boolean, is_guest boolean, has_discount boolean, is_test_data boolean, "
          "item_quantity int, order_revenue decimal(12,2)")
LINES = ("order_id string, lineitem_id string, business_date date, order_hour_local int, restaurant_id string, "
         "item_key string, item_quantity int, line_revenue decimal(12,2), is_test_data boolean")
ITEMS = "item_key string, item_category string"

D1, D2 = date(2023, 1, 2), date(2023, 1, 3)


def orders_df(spark):
    return spark.createDataFrame([
        # two orders in the same day / restaurant / hour: they land in one row
        ("o1", D1, 9, "r1", True,  False, False, False, 3, Decimal("11.50")),
        ("o2", D1, 9, "r1", False, True,  True,  False, 1, Decimal("3.50")),
        # a different hour, and a different day
        ("o3", D1, 10, "r1", False, False, False, False, 2, Decimal("6.00")),
        ("o4", D2, 9, "r1", True,  False, False, False, 1, Decimal("4.00")),
        # excluded: test data, and a date outside 2023
        ("o5", D1, 9, "r1", False, False, False, True, 1, Decimal("99.00")),
        ("o6", date(2022, 12, 31), 9, "r1", False, False, False, False, 1, Decimal("50.00")),
    ], ORDERS)


def lines_df(spark):
    return spark.createDataFrame([
        # o1 has items from two categories: Drinks and Bakery
        ("o1", "l1", D1, 9, "r1", "latte", 2, Decimal("8.00"), False),
        ("o1", "l2", D1, 9, "r1", "muffin", 1, Decimal("3.50"), False),
        ("o2", "l3", D1, 9, "r1", "muffin", 1, Decimal("3.50"), False),
        ("o3", "l4", D1, 10, "r1", "latte", 2, Decimal("6.00"), False),
        ("o4", "l5", D2, 9, "r1", "muffin", 1, Decimal("4.00"), False),
        ("o5", "l6", D1, 9, "r1", "latte", 1, Decimal("99.00"), True),
        ("o6", "l7", date(2022, 12, 31), 9, "r1", "latte", 1, Decimal("50.00"), False),
    ], LINES)


def items_df(spark):
    return spark.createDataFrame([("latte", "Drinks"), ("muffin", "Bakery")], ITEMS)


def test_sales_daily_groups_orders_and_splits(spark, rules):
    rows = {(r.business_date, r.order_hour_local): r for r in sales.sales_daily(orders_df(spark), rules).collect()}
    assert len(rows) == 3                                        # test data and 2022 are out
    busy = rows[(D1, 9)]
    assert busy.orders == 2 and busy.revenue == Decimal("15.00") and busy.item_quantity == 4
    assert busy.loyalty_orders == 1 and busy.loyalty_revenue == Decimal("11.50")
    assert busy.guest_orders == 1 and busy.discounted_orders == 1
    assert rows[(D1, 10)].loyalty_orders == 0 and rows[(D1, 10)].loyalty_revenue == Decimal("0.00")


def test_sales_daily_category_has_lines_not_orders(spark, rules):
    rows = {(r.business_date, r.item_category): r
            for r in sales.sales_daily_category(lines_df(spark), items_df(spark), rules).collect()}
    assert len(rows) == 3                                        # (D1, Drinks), (D1, Bakery), (D2, Bakery); the hour is not a key
    drinks, bakery = rows[(D1, "Drinks")], rows[(D1, "Bakery")]
    assert drinks.revenue == Decimal("14.00") and drinks.item_quantity == 4 and drinks.line_count == 2
    assert bakery.revenue == Decimal("7.00") and bakery.line_count == 2
    assert "orders" not in sales.sales_daily_category(lines_df(spark), items_df(spark), rules).columns


def test_both_tables_add_up_to_the_same_revenue(spark, rules):
    daily = sales.sales_daily(orders_df(spark), rules).agg({"revenue": "sum"}).first()[0]
    by_category = sales.sales_daily_category(lines_df(spark), items_df(spark), rules).agg({"revenue": "sum"}).first()[0]
    assert daily == by_category == Decimal("25.00")
