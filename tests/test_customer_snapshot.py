"""customer_daily_snapshot: calendar, totals, windows, tiers, RFM, churn, loyalty."""
from datetime import date, datetime, timedelta
from decimal import Decimal

from globalpartners.metrics import customer_snapshot as snap

ORDERS = ("order_id string, customer_id string, business_date date, order_ts_local timestamp, order_revenue decimal(12,2), "
          "is_loyalty boolean, is_guest boolean, is_non_customer_account boolean, is_test_data boolean")
START = date(2023, 1, 1)


def day(n: int) -> date:
    """Day 0 = 1 Jan 2023."""
    return START + timedelta(days=n)


def order(order_id, customer, n, revenue, loyalty=False, guest=False, faulty=False, test=False):
    when = datetime.combine(day(n), datetime.min.time()).replace(hour=12)
    return (order_id, customer, day(n), when, Decimal(str(revenue)), loyalty, guest, faulty, test)


def build(spark, *orders, last_day=None):
    """fact_order rows; last_day adds a guest order so the data is 'loaded' until then."""
    rows = list(orders)
    if last_day is not None:
        rows.append(order("end", "GUEST", last_day, 1, guest=True))
    return spark.createDataFrame(rows, ORDERS)


def snapshot(spark, rules, *orders, last_day=None):
    df = snap.customer_daily_snapshot(build(spark, *orders, last_day=last_day), rules, "run-1")
    return {(r.customer_id, r.snapshot_date): r for r in df.collect()}


# ---------------------------------------------------------------- calendar
def test_calendar_is_dense_and_excludes_non_customers(spark, rules):
    orders = build(spark, order("o1", "u1", 0, 10), order("o2", "u1", 3, 4), order("o3", "u2", 2, 7),
                   order("g", "GUEST", 1, 3, guest=True), order("f", "bad", 1, 9, faulty=True),
                   order("t", "tester", 1, 1, test=True))
    rows = snap.customer_calendar(orders, rules).collect()
    days = {}
    for r in rows:
        days.setdefault(r.customer_id, []).append(r.snapshot_date)
    assert set(days) == {"u1", "u2"}                       # guest, faulty account and test data are out
    assert sorted(days["u1"]) == [day(0), day(1), day(2), day(3)]
    assert sorted(days["u2"]) == [day(2), day(3)]          # starts at its own first order, ends at the last loaded day


def test_days_without_orders_are_zero_and_order_days_are_summed(spark, rules):
    rows = {(r.customer_id, r.snapshot_date): r for r in snap.customer_calendar(
        build(spark, order("o1", "u1", 0, 10), order("o2", "u1", 0, 5.5), order("o3", "u1", 3, 4)), rules).collect()}
    assert rows[("u1", day(0))].orders_on_day == 2 and rows[("u1", day(0))].revenue_on_day == Decimal("15.50")
    assert rows[("u1", day(1))].orders_on_day == 0 and rows[("u1", day(1))].revenue_on_day == Decimal("0.00")


def test_last_loaded_day_comes_from_all_sales_including_guests(spark, rules):
    rows = snapshot(spark, rules, order("o1", "u1", 0, 10), last_day=5)
    assert max(d for (_, d) in rows) == day(5)


# ---------------------------------------------------------------- totals
def test_totals_clv_recency_and_gaps(spark, rules):
    rows = snapshot(spark, rules, order("o1", "u1", 0, 10), order("o2", "u1", 0, 5.5), order("o3", "u1", 3, 4))
    first, gap, last = rows[("u1", day(0))], rows[("u1", day(2))], rows[("u1", day(3))]
    assert first.orders_to_date == 2 and first.revenue_to_date == Decimal("15.50")
    assert first.is_repeat_customer and first.days_since_last_order == 0 and first.avg_days_between_orders is None
    assert gap.revenue_to_date == Decimal("15.50") and gap.days_since_last_order == 2   # CLV does not move on empty days
    assert last.orders_to_date == 3 and last.revenue_to_date == Decimal("19.50")
    assert last.avg_order_value_to_date == Decimal("6.50")
    assert last.avg_days_between_orders == Decimal("3.00")                               # order days 0 and 3
    assert last.days_since_first_order == 3


# ---------------------------------------------------------------- windows
def test_90_day_window_is_the_last_90_days_including_today(spark, rules):
    rows = snapshot(spark, rules, order("o1", "u1", 0, 10), last_day=95)
    assert rows[("u1", day(89))].orders_last_90d == 1 and rows[("u1", day(89))].revenue_last_90d == Decimal("10.00")
    assert rows[("u1", day(90))].orders_last_90d == 0 and rows[("u1", day(90))].revenue_last_90d == Decimal("0.00")


def test_spend_trend_compares_the_last_30_days_with_the_30_before(spark, rules):
    rows = snapshot(spark, rules, order("o1", "u1", 0, 10), order("o2", "u1", 19, 20), last_day=40)
    r = rows[("u1", day(40))]
    assert r.revenue_last_30d == Decimal("20.00") and r.revenue_prev_30d == Decimal("10.00")
    assert r.spend_change_pct_30d == Decimal("100.00")
    assert rows[("u1", day(19))].spend_change_pct_30d is None          # nothing before: no percentage


# ---------------------------------------------------------------- tiers
def test_clv_tiers_use_cume_dist_and_ties_share_a_tier(spark, rules):
    orders = [order(f"o{i}", f"u{i}", 0, amount) for i, amount in enumerate([1, 2, 3, 3, 4, 5, 6, 7, 8, 9])]
    rows = snapshot(spark, rules, *orders)
    tiers = {c: rows[(c, day(0))].clv_tier for (c, _) in rows}
    # 10 customers: cume_dist 0.1 ... 1.0, the two $3 customers share 0.4
    assert tiers["u0"] == "Low" and tiers["u1"] == "Low"               # 0.1, 0.2 (<= 0.2)
    assert tiers["u2"] == tiers["u3"] == "Medium"                      # tie at $3
    assert tiers["u7"] == "Medium"                                     # 0.8 is not above 0.8
    assert tiers["u8"] == tiers["u9"] == "High"


# ---------------------------------------------------------------- RFM and churn
def test_new_customer_then_churn_risk_then_lapsed(spark, rules):
    rows = snapshot(spark, rules, order("o1", "u1", 0, 12.99), last_day=100)
    new, risk, lapsed = rows[("u1", day(0))], rows[("u1", day(46))], rows[("u1", day(91))]
    assert (new.r_score, new.f_score, new.m_score) == (5, 2, 2) and new.rfm_segment == "New"
    assert new.churn_status == "active"
    assert rows[("u1", day(45))].churn_status == "active" and risk.churn_status == "at_risk"
    assert risk.r_score == 2 and risk.rfm_segment == "Churn Risk"
    assert rows[("u1", day(90))].churn_status == "at_risk" and lapsed.churn_status == "lapsed"
    assert lapsed.r_score == 1 and lapsed.f_score == 1 and lapsed.m_score == 1


def test_vip_needs_recent_frequent_high_spend(spark, rules):
    rows = snapshot(spark, rules, order("a", "v", 0, 20), order("b", "v", 1, 20), order("c", "v", 2, 30))
    r = rows[("v", day(2))]
    assert (r.r_score, r.f_score, r.m_score) == (5, 4, 5) and r.rfm_segment == "VIP"      # 3 orders, $70


# ---------------------------------------------------------------- loyalty
def test_loyalty_flag_is_the_latest_orders_flag_as_of_each_day(spark, rules):
    rows = snapshot(spark, rules, order("a", "u1", 0, 5, loyalty=True), order("b", "u1", 2, 5, loyalty=False))
    assert rows[("u1", day(0))].is_loyalty_as_of is True
    assert rows[("u1", day(1))].is_loyalty_as_of is True               # no order that day: keeps the earlier flag
    assert rows[("u1", day(2))].is_loyalty_as_of is False
