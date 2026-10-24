"""silver → gold: revenue formula, guests, order totals, calendar."""
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal

from globalpartners.transformations import gold_dimensions as dims
from globalpartners.transformations import gold_facts as facts

LINES = ("order_id string, lineitem_id string, restaurant_id string, app_name string, user_id string, "
         "is_loyalty boolean, business_date date, order_hour_local int, order_ts_local timestamp, "
         "item_category string, item_name_key string, item_price decimal(10,2), item_quantity int, "
         "is_guest boolean, is_test_data boolean, is_non_customer_account boolean")
OPTIONS = "order_id string, lineitem_id string, option_price decimal(10,2), option_seq int"
DATES = "date date, iso_week int, is_holiday boolean, holiday_name string"


def lines_df(spark):
    day, ts = date(2023, 1, 2), datetime(2023, 1, 2, 9, 0)
    return spark.createDataFrame([
        # order o1 (customer u1): 2 × latte, line total $8.00, with one $0.75 option
        ("o1", "l1", "r1", "app", "u1", True, day, 9, ts, "Drip Coffee", "iced latte", Decimal("8.00"), 2, False, False, False),
        ("o1", "l2", "r1", "app", "u1", True, day, 9, ts, "Bakery", "muffin", Decimal("3.50"), 1, False, False, False),
        # order o2: guest, no options
        ("o2", "l3", "r1", "app", None, False, day, 10, ts, "Bakery", "muffin", Decimal("3.50"), 1, True, False, False),
    ], LINES)


def options_df(spark):
    return spark.createDataFrame([("o1", "l1", Decimal("0.75"), 1)], OPTIONS)


def test_line_revenue_is_item_price_plus_option_price_times_quantity(spark, rules):
    rows = {r.lineitem_id: r for r in facts.fact_order_line(lines_df(spark), options_df(spark), rules).collect()}
    assert rows["l1"].option_revenue == Decimal("1.50")        # $0.75 × 2 units (assumption Q3)
    assert rows["l1"].line_revenue == Decimal("9.50")          # item_price is the line total (Q2)
    assert rows["l2"].option_count == 0 and rows["l2"].line_revenue == Decimal("3.50")


def test_option_once_per_line_switch(spark, rules):
    once = deepcopy(rules)
    once["revenue"]["option_price_times_item_quantity"] = False
    rows = {r.lineitem_id: r for r in facts.fact_order_line(lines_df(spark), options_df(spark), once).collect()}
    assert rows["l1"].line_revenue == Decimal("8.75")


def test_guest_lines_get_the_guest_customer(spark, rules):
    rows = {r.lineitem_id: r for r in facts.fact_order_line(lines_df(spark), options_df(spark), rules).collect()}
    assert rows["l3"].customer_id == dims.GUEST and rows["l1"].customer_id == "u1"


def test_order_totals_equal_the_sum_of_their_lines(spark, rules):
    fact_lines = facts.fact_order_line(lines_df(spark), options_df(spark), rules)
    orders = {r.order_id: r for r in facts.fact_order(fact_lines, lines_df(spark)).collect()}
    assert orders["o1"].line_count == 2 and orders["o1"].order_revenue == Decimal("13.00")
    assert orders["o2"].order_revenue == Decimal("3.50") and orders["o2"].is_guest is True


def test_dim_customer_has_one_guest_row(spark):
    customers = dims.dim_customer(lines_df(spark)).collect()
    assert sorted(r.customer_id for r in customers) == [dims.GUEST, "u1"]


def test_dim_date_iso_year_of_first_january(spark, rules):
    calendar = spark.createDataFrame([(date(2023, 1, 1), 52, False, None)], DATES)
    days = {r.date: r for r in dims.dim_date(spark, lines_df(spark), calendar, rules).collect()}
    assert len(days) == 365
    assert days[date(2023, 1, 1)].iso_year == 2022 and days[date(2023, 1, 1)].iso_week == 52


def test_dim_date_works_before_the_first_order(spark, rules):
    # regression: an empty first run crashed with DATE'None-01-01' (Step 4.7)
    calendar = spark.createDataFrame([(date(2023, 1, 1), 52, False, None)], DATES)
    no_lines = lines_df(spark).limit(0)
    assert dims.dim_date(spark, no_lines, calendar, rules).count() == 365
