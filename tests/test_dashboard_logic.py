"""Dashboard calculations (dashboard/logic.py): plain pandas, no Spark, no Streamlit."""
from datetime import date

import pandas as pd
import pytest

from dashboard import logic


def cube(rows):
    """rfm_segment, clv_tier, churn_status, is_loyalty, r, f, m, customers, clv, orders, rev90, orders90, repeat"""
    cols = ["rfm_segment", "clv_tier", "churn_status", "is_loyalty_as_of", "r_score", "f_score", "m_score",
            "customers", "clv", "orders", "revenue_90d", "orders_90d", "repeat_customers"]
    return pd.DataFrame(rows, columns=cols)


CUBE = cube([
    ("VIP", "High", "active", True, 5, 5, 5, 10, 1000.0, 100, 500.0, 50, 10),
    ("VIP", "High", "active", False, 4, 4, 4, 10, 800.0, 80, 400.0, 40, 9),
    ("Regular", "Medium", "active", True, 3, 3, 3, 40, 800.0, 100, 300.0, 80, 20),
    ("Churn Risk", "Low", "lapsed", False, 1, 1, 1, 50, 200.0, 50, 0.0, 0, 5),
])


# ---------------------------------------------------------------- customers
def test_segment_summary_adds_up_and_orders_the_segments():
    s = logic.segment_summary(CUBE).set_index("rfm_segment")
    assert list(s.index) == ["VIP", "Regular", "Churn Risk"]            # fixed display order, missing segments skipped
    assert s.loc["VIP", "customers"] == 20 and s.loc["VIP", "clv"] == 1800.0
    assert s["share_of_customers"].sum() == pytest.approx(1.0) and s["share_of_clv"].sum() == pytest.approx(1.0)
    assert s.loc["VIP", "avg_clv"] == pytest.approx(90.0)               # 1800 / 20: a ratio of sums, not a mean of means
    assert s.loc["VIP", "avg_order_value"] == pytest.approx(10.0)       # 1800 / 180 orders


def test_rfm_grid_is_always_5_by_5_with_zeros_for_empty_cells():
    grid = logic.rfm_grid(CUBE)
    assert grid.shape == (5, 5) and list(grid.index) == [5, 4, 3, 2, 1] and list(grid.columns) == [1, 2, 3, 4, 5]
    assert grid.loc[5, 5] == 10 and grid.loc[3, 3] == 40 and grid.loc[2, 2] == 0
    assert grid.values.sum() == CUBE["customers"].sum()


def test_tiers_are_ordered_high_to_low():
    t = logic.tier_summary(CUBE)
    assert list(t["clv_tier"]) == ["High", "Medium", "Low"]
    assert t["share_of_clv"].sum() == pytest.approx(1.0)


def test_loyalty_comparison_uses_sums_for_ratios():
    c = logic.loyalty_comparison(CUBE).set_index("group")
    member, other = c.loc["Loyalty member"], c.loc["Not a member"]
    assert member["customers"] == 50 and member["avg_clv"] == pytest.approx(36.0)        # (1000 + 800) / 50
    assert other["customers"] == 60 and other["repeat_rate"] == pytest.approx(14 / 60)   # (9 + 5) / 60
    assert member["avg_order_value"] == pytest.approx(9.0)                                # 1800 / 200 orders


def test_segments_over_time_has_one_column_per_segment_in_display_order():
    series = pd.DataFrame({"snapshot_date": pd.to_datetime(["2023-01-01"] * 3 + ["2023-01-02"] * 2),
                           "rfm_segment": ["Churn Risk", "VIP", "VIP", "Churn Risk", "VIP"],
                           "customers": [5, 2, 1, 5, 4]})
    wide = logic.segments_over_time(series)
    assert list(wide.columns) == ["VIP", "Churn Risk"]
    assert wide.loc["2023-01-01", "VIP"] == 3                           # rows of the same day and segment are added


def test_band_risk_share_of_customers_who_are_not_active():
    bands = pd.DataFrame({"churn_status": ["active", "lapsed", "at_risk", "active"],
                          "order_band": ["1 order", "1 order", "1 order", "10+ orders"],
                          "customers": [10, 60, 30, 100]})
    risk = logic.band_risk(bands, "order_band", logic.ORDER_BANDS).set_index("order_band")
    assert list(risk.index) == ["1 order", "10+ orders"]               # the order given, empty bands skipped
    assert risk.loc["1 order", "customers"] == 100 and risk.loc["1 order", "not_active_share"] == pytest.approx(0.9)
    assert risk.loc["10+ orders", "not_active_share"] == 0 and risk.loc["10+ orders", "lapsed"] == 0   # missing status = 0


def test_churn_totals_follow_active_at_risk_lapsed_order():
    bands = pd.DataFrame({"churn_status": ["lapsed", "active", "at_risk"], "customers": [5, 3, 2], "clv": [50.0, 30.0, 20.0]})
    t = logic.churn_totals(bands)
    assert list(t["churn_status"]) == ["active", "at_risk", "lapsed"] and t["share"].sum() == pytest.approx(1.0)


def test_at_risk_alerts_apply_both_thresholds_and_sort_by_value():
    customers = pd.DataFrame({"customer_id": ["a", "b", "c", "d"], "days_since_last_order": [50, 80, 80, 60],
                              "revenue_to_date": [500.0, 90.0, 20.0, 300.0]})
    alerts = logic.at_risk_alerts(customers, min_days=60, min_clv=50.0)
    assert list(alerts["customer_id"]) == ["d", "b"]                    # a: too recent, c: too little value


# ---------------------------------------------------------------- sales
def daily(rows):
    df = pd.DataFrame(rows, columns=["business_date", "restaurant_id", "order_hour_local", "orders", "revenue", "item_quantity",
                                     "loyalty_orders", "loyalty_revenue", "guest_orders", "discounted_orders"])
    df["business_date"] = pd.to_datetime(df["business_date"])
    return df


SALES = daily([
    ("2023-01-02", "r1", 9, 4, 40.0, 8, 2, 20.0, 0, 0),     # Monday
    ("2023-01-02", "r2", 9, 1, 10.0, 1, 0, 0.0, 1, 0),
    ("2023-01-03", "r1", 12, 2, 30.0, 4, 1, 15.0, 0, 0),    # Tuesday
    ("2023-02-06", "r1", 12, 3, 60.0, 5, 3, 60.0, 0, 0),    # Monday, next month
])


def test_select_sales_by_dates_and_restaurants():
    both = logic.select_sales(SALES, date(2023, 1, 2), date(2023, 1, 3))
    assert len(both) == 3                                               # end date inclusive, February out
    only_r2 = logic.select_sales(SALES, date(2023, 1, 1), date(2023, 12, 31), ["r2"])
    assert list(only_r2["restaurant_id"]) == ["r2"]
    assert len(logic.select_sales(SALES, date(2023, 1, 1), date(2023, 12, 31), [])) == 4     # empty list = all


def test_sales_by_period_day_week_month():
    month = logic.sales_by_period(SALES, "M").set_index("period")
    assert month.loc[pd.Timestamp("2023-01-01"), "revenue"] == 80.0 and month.loc[pd.Timestamp("2023-02-01"), "orders"] == 3
    week = logic.sales_by_period(SALES, "W")
    assert list(week["period"].dt.day_name().unique()) == ["Monday"]    # weeks start on Monday
    assert week.iloc[0]["revenue"] == 80.0                              # Mon 2 Jan + Tue 3 Jan are the same week
    day = logic.sales_by_period(SALES, "D")
    assert len(day) == 3 and day.iloc[0]["avg_order_value"] == pytest.approx(10.0)    # 50 / 5 orders


def test_weekday_profile_averages_per_day_not_per_row():
    p = logic.weekday_profile(SALES).set_index("weekday")
    assert list(p.index) == ["Monday", "Tuesday"]
    assert p.loc["Monday", "days"] == 2 and p.loc["Monday", "avg_revenue"] == pytest.approx((50.0 + 60.0) / 2)


def test_hour_profile_and_heatmap():
    hours = logic.hour_profile(SALES).set_index("order_hour_local")
    assert hours.loc[9, "orders"] == 5 and hours.loc[12, "orders"] == 5
    grid = logic.weekday_hour_heatmap(SALES)
    assert grid.loc["Monday", 9] == 5 and grid.loc["Tuesday", 12] == 2 and grid.loc["Monday", 12] == 3


def test_holiday_effect_compares_with_the_median_of_normal_same_weekdays():
    days = pd.date_range("2023-06-05", periods=9 * 7, freq="D")                # 9 weeks, starting on a Monday
    frame = daily([(d.strftime("%Y-%m-%d"), "r1", 12, 1, 100.0, 1, 0, 0.0, 0, 0) for d in days])
    holiday = date(2023, 7, 3)                                                  # a Monday
    frame.loc[frame["business_date"] == pd.Timestamp(holiday), "revenue"] = 150.0
    out = logic.holiday_effect(frame, {holiday: "Test Day", date(2023, 7, 10): "Other holiday"})
    row = out[out["holiday"] == "Test Day"].iloc[0]
    assert row["normal_revenue"] == 100.0 and row["vs_normal"] == pytest.approx(0.5)
    # the other holiday is not used as a "normal" Monday for this one, and is itself not a normal day
    assert len(out) == 2


def test_holiday_effect_skips_days_without_sales():
    assert logic.holiday_effect(SALES, {date(2023, 7, 4): "No sales here"}).empty


def test_category_totals_and_monthly_grouping():
    category = pd.DataFrame({"business_date": pd.to_datetime(["2023-01-02", "2023-01-02", "2023-02-02", "2023-02-02"]),
                             "restaurant_id": ["r1"] * 4, "item_category": ["Drinks", "Bakery", "Drinks", None],
                             "revenue": [50.0, 20.0, 40.0, 10.0], "item_quantity": [5, 2, 4, 1], "line_count": [5, 2, 4, 1]})
    totals = logic.category_totals(category)
    assert list(totals["item_category"]) == ["Drinks", "Bakery", "(no category)"] and totals["share"].sum() == pytest.approx(1.0)
    monthly = logic.category_by_month(category, top=1)
    assert set(monthly["item_category"]) == {"Drinks", "Other"}         # everything outside the top 1 folds into "Other"
    assert monthly.groupby("item_category")["revenue"].sum()["Other"] == 30.0


def test_location_table_ranks_by_revenue_and_adds_retention():
    summary = pd.DataFrame({"restaurant_id": ["r1", "r2"], "orders": [9, 1], "revenue": [130.0, 10.0],
                            "customers": [40, 5], "repeat_customers": [10, 0]})
    t = logic.location_table(SALES, summary).set_index("restaurant_id")
    assert t.loc["r1", "rank"] == 1 and t.loc["r2", "rank"] == 2
    assert t.loc["r1", "revenue"] == 130.0 and t.loc["r1", "orders"] == 9 and t.loc["r1", "days_open"] == 3
    assert t.loc["r1", "orders_per_day"] == pytest.approx(3.0) and t.loc["r1", "avg_order_value"] == pytest.approx(130 / 9)
    assert t.loc["r1", "repeat_rate"] == pytest.approx(0.25) and t.loc["r2", "repeat_rate"] == 0
    assert t["share_of_revenue"].sum() == pytest.approx(1.0)


def test_location_table_keeps_a_restaurant_missing_from_the_summary():
    t = logic.location_table(SALES, pd.DataFrame(columns=["restaurant_id", "orders", "revenue", "customers", "repeat_customers"]))
    assert len(t) == 2 and t["repeat_rate"].isna().all()


def test_location_insights_leave_out_restaurants_with_few_customers_from_the_retention_ranking():
    summary = pd.DataFrame({"restaurant_id": ["r1", "r2"], "orders": [9, 1], "revenue": [130.0, 10.0],
                            "customers": [40, 2], "repeat_customers": [10, 2]})        # r2: 100 % repeat, but only 2 customers
    notes = logic.location_insights(logic.location_table(SALES, summary))
    retention = [n for n in notes if "retention" in n][0]
    assert logic.short_id("r1") in retention and logic.short_id("r2") not in retention


def test_short_id_uses_the_end_of_the_id():
    assert logic.short_id("5fece84aadb0d51509c36f22") == "…c36f22"


def test_loyalty_trend_shares_by_month():
    t = logic.loyalty_trend(SALES).set_index("month")
    assert t.loc[pd.Timestamp("2023-01-01"), "loyalty_order_share"] == pytest.approx(3 / 7)      # (2 + 0 + 1) / (4 + 1 + 2)
    assert t.loc[pd.Timestamp("2023-02-01"), "loyalty_revenue_share"] == pytest.approx(1.0)


def test_discount_summary_with_no_discounts_in_the_data():
    s = logic.discount_summary(SALES)
    assert s["orders"] == 10 and s["discounted_orders"] == 0 and s["full_price_orders"] == 10 and s["discounted_share"] == 0


def test_safe_ratio_does_not_divide_by_zero():
    assert pd.isna(logic.safe_ratio(1, 0))
    out = logic.safe_ratio(pd.Series([1.0, 2.0]), pd.Series([0, 4]))
    assert pd.isna(out[0]) and out[1] == 0.5
