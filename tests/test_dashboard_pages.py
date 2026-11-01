"""The six pages and the app shell, run headless with Streamlit's AppTest against synthetic tables.

No Spark, no AWS: data._execute is replaced by a function that answers each query with a small table of the right shape.
"""
from datetime import date
from pathlib import Path

import pandas as pd
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from dashboard import data

TIMEOUT = 60


def frame(columns, rows):
    return pd.DataFrame(rows, columns=columns)


RANGE = frame(["first_day", "last_day"], [(pd.Timestamp("2023-01-01"), pd.Timestamp("2023-03-31"))])

CUBE = frame(["rfm_segment", "clv_tier", "churn_status", "is_loyalty_as_of", "r_score", "f_score", "m_score", "customers", "clv",
              "orders", "revenue_90d", "orders_90d", "repeat_customers"], [
    ("VIP", "High", "active", True, 5, 5, 5, 10, 1000.0, 100, 500.0, 50, 10),
    ("VIP", "High", "active", False, 4, 4, 4, 10, 800.0, 80, 400.0, 40, 9),
    ("New", "Low", "active", False, 5, 1, 1, 15, 150.0, 15, 150.0, 15, 0),
    ("Regular", "Medium", "active", True, 3, 3, 3, 40, 800.0, 100, 300.0, 80, 20),
    ("Churn Risk", "Low", "lapsed", False, 1, 1, 1, 50, 200.0, 50, 0.0, 0, 5)])

BANDS = frame(["churn_status", "order_band", "gap_band", "trend_band", "customers", "clv"], [
    ("active", "1 order", "one order only", "no spend in the 30 days before", 20, 100.0),
    ("lapsed", "1 order", "one order only", "no spend in the 30 days before", 60, 300.0),
    ("at_risk", "2-3 orders", "every 1-2 months", "down 50% or more", 30, 400.0),
    ("active", "10+ orders", "every 2 weeks or faster", "flat or up", 40, 2000.0)])

AT_RISK = frame(["customer_id", "days_since_last_order", "orders_to_date", "revenue_to_date", "avg_days_between_orders",
                 "spend_change_pct_30d", "rfm_segment", "clv_tier", "is_loyalty_as_of"], [
    ("c1", 70, 5, 200.0, 20.0, -100.0, "Churn Risk", "High", True),
    ("c2", 50, 2, 20.0, None, None, "Churn Risk", "Low", False)])

SERIES = frame(["snapshot_date", "rfm_segment", "churn_status", "customers", "clv"], [
    (pd.Timestamp("2023-01-01"), "VIP", "active", 5, 100.0), (pd.Timestamp("2023-01-01"), "Regular", "active", 9, 100.0),
    (pd.Timestamp("2023-03-31"), "VIP", "active", 20, 1800.0), (pd.Timestamp("2023-03-31"), "Churn Risk", "lapsed", 50, 200.0)])

DAYS = pd.date_range("2023-01-01", "2023-03-31", freq="D")
SALES = frame(["business_date", "restaurant_id", "order_hour_local", "orders", "revenue", "item_quantity", "loyalty_orders",
               "loyalty_revenue", "guest_orders", "discounted_orders"],
              [(d, r, h, 3, 30.0 + h, 6, 1, 10.0, 1, 0) for d in DAYS for r in ("aaaaaa111111", "bbbbbb222222") for h in (9, 12)])
CATEGORY = frame(["business_date", "restaurant_id", "item_category", "revenue", "item_quantity", "line_count"],
                 [(d, "aaaaaa111111", c, 20.0, 4, 4) for d in DAYS for c in ("Drinks", "Bakery", None)])
LOCATIONS = frame(["restaurant_id", "orders", "revenue", "customers", "repeat_customers"],
                  [("aaaaaa111111", 360, 4000.0, 100, 30), ("bbbbbb222222", 360, 4000.0, 80, 10)])


def answer(sql: str) -> pd.DataFrame:
    if "MIN(snapshot_date)" in sql:
        return RANGE
    if "order_band" in sql:
        return BANDS
    if "churn_status = 'at_risk'" in sql:
        return AT_RISK
    if "GROUP BY snapshot_date" in sql:
        return SERIES
    if "customer_daily_snapshot" in sql:
        return CUBE
    if "sales_daily_category" in sql:
        return CATEGORY
    if "location_summary" in sql:
        return LOCATIONS
    if "sales_daily" in sql:
        return SALES
    raise AssertionError(f"unexpected query: {sql}")


@pytest.fixture(autouse=True)
def fake_lake(monkeypatch):
    st.cache_data.clear()
    monkeypatch.setattr(data, "_execute", answer)
    yield
    st.cache_data.clear()


def run_page(module: str) -> AppTest:
    app = AppTest.from_string(f"from dashboard.views import {module}\n{module}.render()", default_timeout=TIMEOUT).run()
    assert not app.exception, [e.value for e in app.exception]
    return app


def metric_values(app: AppTest) -> dict:
    return {m.label: m.value for m in app.metric}


@pytest.mark.parametrize("module", ["segmentation", "churn", "sales", "loyalty", "locations", "discounts"])
def test_every_page_renders_without_error(module):
    app = run_page(module)
    assert app.title and len(app.subheader) >= 1


def test_segmentation_shows_totals_for_the_chosen_day():
    values = metric_values(run_page("segmentation"))
    assert values["Customers"] == "125" and values["Lifetime value (CLV)"] == "$2,950"
    assert values["VIP customers"] == "20"


def test_churn_page_counts_the_statuses_and_filters_the_alert_list():
    app = run_page("churn")
    values = metric_values(app)
    assert values["Active"] == "60" and values["Lapsed"] == "60" and values["At risk"] == "30"
    assert values["Customers to contact"] == "1"                 # default thresholds: 60 days and $50: only c1
    app.slider[0].set_value(46).run()
    app.slider[1].set_value(0).run()
    assert metric_values(app)["Customers to contact"] == "2"


def test_sales_page_totals_and_filters():
    app = run_page("sales")
    assert metric_values(app)["Orders"] == f"{len(SALES) * 3:,}"
    app.multiselect[0].set_value(["aaaaaa111111"]).run()
    assert not app.exception and metric_values(app)["Orders"] == f"{len(SALES) // 2 * 3:,}"
    app.radio[0].set_value("Daily").run()                          # the Daily view adds the holiday markers
    assert not app.exception


def test_loyalty_page_compares_members_with_non_members():
    values = metric_values(run_page("loyalty"))
    assert values["Loyalty members"] == "50" and values["Repeat rate, member"] == "60%"


def test_loyalty_page_explains_when_only_one_group_exists(monkeypatch):
    only_members = CUBE[CUBE["is_loyalty_as_of"]]
    monkeypatch.setattr(data, "_execute", lambda sql: only_members if "customer_daily_snapshot" in sql and "MIN(" not in sql else answer(sql))
    app = run_page("loyalty")
    assert any("nothing to compare" in w.value for w in app.warning)


def test_locations_page_ranks_and_flags_the_retention_scope():
    app = run_page("locations")
    assert metric_values(app)["Restaurants with sales"] == "2"
    assert any("whole-year" in c.value for c in app.caption)


def test_discount_page_states_the_data_limitation_when_there_are_no_discounts():
    app = run_page("discounts")
    assert metric_values(app)["Orders with a discount"] == "0"
    assert any("no discounts in the source data" in i.value for i in app.info)


def test_discount_page_shows_the_split_when_discounts_exist(monkeypatch):
    with_discounts = SALES.assign(discounted_orders=1)
    monkeypatch.setattr(data, "_execute", lambda sql: with_discounts if "FROM sales_daily" in sql and "category" not in sql else answer(sql))
    app = run_page("discounts")
    assert not any("no discounts in the source data" in i.value for i in app.info)


@pytest.mark.parametrize("module", ["segmentation", "churn"])
def test_customer_pages_warn_when_the_day_has_no_customers(monkeypatch, module):
    monkeypatch.setattr(data, "_execute", lambda sql: answer(sql).iloc[0:0] if "MIN(" not in sql else RANGE)
    app = run_page(module)
    assert any("No customers" in w.value for w in app.warning)


def test_the_app_explains_a_missing_pipeline_run_instead_of_showing_a_stack_trace(monkeypatch):
    def no_tables(sql):
        raise RuntimeError("Athena query FAILED: TABLE_NOT_FOUND: gold.customer_daily_snapshot does not exist")
    monkeypatch.setattr(data, "_execute", no_tables)
    app = AppTest.from_file(str(Path(__file__).resolve().parent.parent / "dashboard" / "app.py"), default_timeout=TIMEOUT).run()
    assert not app.exception                                              # handled: no raw trace on the page
    assert any("could not read the gold tables" in e.value for e in app.error)
    assert any("TABLE_NOT_FOUND" in c.value for c in app.code)


def test_the_app_shell_has_six_pages_and_the_as_of_picker():
    app = AppTest.from_file(str(Path(__file__).resolve().parent.parent / "dashboard" / "app.py"), default_timeout=TIMEOUT).run()
    assert not app.exception, [e.value for e in app.exception]
    assert app.sidebar.date_input[0].value == date(2023, 3, 31)       # defaults to the last loaded day
    assert app.title[0].value == "Customer segmentation"               # the default page
