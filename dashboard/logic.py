"""Calculations behind the six pages: pure pandas functions, no Streamlit, no database.

The queries (queries.py) return sums and counts. Everything that is a ratio (average order value, share,
repeat rate) is calculated here, after summing, so it is right for whatever slice the user selected.
"""
from datetime import date

import pandas as pd

# 2023 US holidays and retail events (the data covers 2023 only). Shown as markers on the sales charts.
HOLIDAYS_2023 = {
    date(2023, 1, 1): "New Year's Day",
    date(2023, 1, 16): "MLK Day",
    date(2023, 2, 12): "Super Bowl",
    date(2023, 2, 14): "Valentine's Day",
    date(2023, 2, 20): "Presidents' Day",
    date(2023, 4, 9): "Easter",
    date(2023, 5, 14): "Mother's Day",
    date(2023, 5, 29): "Memorial Day",
    date(2023, 6, 19): "Juneteenth",
    date(2023, 7, 4): "Independence Day",
    date(2023, 9, 4): "Labor Day",
    date(2023, 10, 9): "Columbus Day",
    date(2023, 10, 31): "Halloween",
    date(2023, 11, 11): "Veterans Day",
    date(2023, 11, 23): "Thanksgiving",
    date(2023, 11, 24): "Black Friday",
    date(2023, 12, 24): "Christmas Eve",
    date(2023, 12, 25): "Christmas Day",
    date(2023, 12, 31): "New Year's Eve",
}

# What each segment means. The rules themselves live in config/business_rules.yaml (rfm.segments).
SEGMENT_MEANING = {
    "VIP": "Ordered within the last 30 days, 3 or more times in the last 90 days, and spent $30 or more in those 90 days "
           "(R, F and M scores all 4 or 5).",
    "New": "Ordered within the last 30 days, first order less than 90 days ago, and at most 1 order in the last 90 days.",
    "Regular": "Everyone in between: still buying, but not (yet) a VIP.",
    "Churn Risk": "No order for more than 45 days and at most 1 order in the last 90 days.",
}
SEGMENT_ORDER = ["VIP", "Regular", "New", "Churn Risk"]
CHURN_ORDER = ["active", "at_risk", "lapsed"]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def safe_ratio(numerator, denominator):
    """numerator / denominator, NaN where the denominator is 0 (works on numbers and on pandas columns)."""
    if isinstance(denominator, pd.Series):
        return numerator / denominator.where(denominator != 0)
    return numerator / denominator if denominator else float("nan")


def short_id(restaurant_id: str) -> str:
    """Restaurants have no names in the source, only ids (SME-confirmed data limitation). The last 6 characters
    differ between restaurants (the first 8 are a timestamp and look alike)."""
    return f"…{restaurant_id[-6:]}"


# ================================================================ customers: segments, loyalty, churn
def segment_summary(cube: pd.DataFrame) -> pd.DataFrame:
    """One row per RFM segment: customers, share, CLV, last-90-day activity."""
    g = cube.groupby("rfm_segment", as_index=False).agg(
        customers=("customers", "sum"), clv=("clv", "sum"), orders=("orders", "sum"),
        revenue_90d=("revenue_90d", "sum"), orders_90d=("orders_90d", "sum"))
    g["share_of_customers"] = safe_ratio(g["customers"], g["customers"].sum())
    g["share_of_clv"] = safe_ratio(g["clv"], g["clv"].sum())
    g["avg_clv"] = safe_ratio(g["clv"], g["customers"])
    g["orders_90d_per_customer"] = safe_ratio(g["orders_90d"], g["customers"])
    g["avg_order_value"] = safe_ratio(g["clv"], g["orders"])
    g["order"] = g["rfm_segment"].map({s: i for i, s in enumerate(SEGMENT_ORDER)}).fillna(len(SEGMENT_ORDER))
    return g.sort_values("order").drop(columns="order").reset_index(drop=True)


def rfm_grid(cube: pd.DataFrame, rows: str = "r_score", columns: str = "f_score") -> pd.DataFrame:
    """Customers per pair of RFM scores (1 to 5 each), as a 5 x 5 table; scores nobody has are 0."""
    grid = cube.pivot_table(index=rows, columns=columns, values="customers", aggfunc="sum", fill_value=0)
    return grid.reindex(index=range(5, 0, -1), columns=range(1, 6), fill_value=0)


def tier_summary(cube: pd.DataFrame) -> pd.DataFrame:
    """Customers and CLV per CLV tier (High = top 20 %, Low = bottom 20 %)."""
    g = cube.groupby("clv_tier", as_index=False).agg(customers=("customers", "sum"), clv=("clv", "sum"))
    g["share_of_clv"] = safe_ratio(g["clv"], g["clv"].sum())
    order = {"High": 0, "Medium": 1, "Low": 2}
    return g.sort_values("clv_tier", key=lambda s: s.map(order)).reset_index(drop=True)


def segments_over_time(series: pd.DataFrame) -> pd.DataFrame:
    """Customers per day and segment, as a wide table (one column per segment) for an area chart."""
    wide = series.groupby(["snapshot_date", "rfm_segment"])["customers"].sum().unstack(fill_value=0)
    return wide[[s for s in SEGMENT_ORDER if s in wide.columns]]


def loyalty_comparison(cube: pd.DataFrame) -> pd.DataFrame:
    """Loyalty members vs non-members: CLV, average order value, repeat purchase rate."""
    g = cube.groupby("is_loyalty_as_of", as_index=False).agg(
        customers=("customers", "sum"), clv=("clv", "sum"), orders=("orders", "sum"),
        repeat_customers=("repeat_customers", "sum"), revenue_90d=("revenue_90d", "sum"),
        orders_90d=("orders_90d", "sum"))
    g["group"] = g["is_loyalty_as_of"].map({True: "Loyalty member", False: "Not a member"})
    g["avg_clv"] = safe_ratio(g["clv"], g["customers"])
    g["avg_order_value"] = safe_ratio(g["clv"], g["orders"])
    g["orders_per_customer"] = safe_ratio(g["orders"], g["customers"])
    g["repeat_rate"] = safe_ratio(g["repeat_customers"], g["customers"])
    g["revenue_90d_per_customer"] = safe_ratio(g["revenue_90d"], g["customers"])
    return g.sort_values("is_loyalty_as_of", ascending=False).reset_index(drop=True)


def band_risk(bands: pd.DataFrame, dimension: str, order: list[str] | None = None) -> pd.DataFrame:
    """For each band of `dimension` (order_band, gap_band or trend_band): customers per churn status and the
    share that is not active (at risk or lapsed). A band with a higher share goes with a higher churn risk."""
    wide = bands.pivot_table(index=dimension, columns="churn_status", values="customers", aggfunc="sum", fill_value=0)
    for status in CHURN_ORDER:
        if status not in wide.columns:
            wide[status] = 0
    wide = wide[CHURN_ORDER]
    wide["customers"] = wide.sum(axis=1)
    wide["not_active_share"] = safe_ratio(wide["at_risk"] + wide["lapsed"], wide["customers"])
    wide["lapsed_share"] = safe_ratio(wide["lapsed"], wide["customers"])
    if order:
        wide = wide.reindex([band for band in order if band in wide.index])
    return wide.reset_index()


ORDER_BANDS = ["1 order", "2-3 orders", "4-9 orders", "10+ orders"]
GAP_BANDS = ["every 2 weeks or faster", "every 2-4 weeks", "every 1-2 months", "less often", "one order only"]
TREND_BANDS = ["flat or up", "down less than 50%", "down 50% or more", "no spend in the 30 days before"]


def churn_totals(bands: pd.DataFrame) -> pd.DataFrame:
    """Customers and the lifetime value they hold, per churn status."""
    g = bands.groupby("churn_status", as_index=False).agg(customers=("customers", "sum"), clv=("clv", "sum"))
    g["share"] = safe_ratio(g["customers"], g["customers"].sum())
    g["order"] = g["churn_status"].map({s: i for i, s in enumerate(CHURN_ORDER)})
    return g.sort_values("order").drop(columns="order").reset_index(drop=True)


def at_risk_alerts(customers: pd.DataFrame, min_days: int, min_clv: float) -> pd.DataFrame:
    """Threshold alert: at-risk customers silent for at least `min_days` with at least `min_clv` lifetime value."""
    hit = customers[(customers["days_since_last_order"] >= min_days) & (customers["revenue_to_date"] >= min_clv)]
    return hit.sort_values("revenue_to_date", ascending=False).reset_index(drop=True)


# ================================================================ sales: trends, seasonality, locations
def select_sales(daily: pd.DataFrame, start: date, end: date, locations: list[str] | None = None) -> pd.DataFrame:
    """Rows between two dates (inclusive), for the chosen restaurants (None = all)."""
    mask = (daily["business_date"] >= pd.Timestamp(start)) & (daily["business_date"] <= pd.Timestamp(end))
    if locations:
        mask &= daily["restaurant_id"].isin(locations)
    return daily[mask]


def sales_by_period(daily: pd.DataFrame, freq: str) -> pd.DataFrame:
    """Orders, revenue and average order value per day ('D'), week ('W', starting Monday) or month ('M')."""
    period = daily["business_date"].dt.to_period({"D": "D", "W": "W-SUN", "M": "M"}[freq]).dt.start_time
    g = daily.assign(period=period).groupby("period", as_index=False).agg(
        orders=("orders", "sum"), revenue=("revenue", "sum"), item_quantity=("item_quantity", "sum"))
    g["avg_order_value"] = safe_ratio(g["revenue"], g["orders"])
    return g


def weekday_profile(daily: pd.DataFrame) -> pd.DataFrame:
    """Average revenue and orders on each weekday (total divided by the number of such days with sales)."""
    per_day = daily.groupby("business_date", as_index=False).agg(orders=("orders", "sum"), revenue=("revenue", "sum"))
    per_day["weekday"] = per_day["business_date"].dt.day_name()
    g = per_day.groupby("weekday").agg(avg_revenue=("revenue", "mean"), avg_orders=("orders", "mean"), days=("revenue", "size"))
    return g.reindex([d for d in WEEKDAYS if d in g.index]).reset_index()


def hour_profile(daily: pd.DataFrame) -> pd.DataFrame:
    """Orders and revenue by hour of the (New York) business day, all selected days added up."""
    return (daily.groupby("order_hour_local", as_index=False)
                 .agg(orders=("orders", "sum"), revenue=("revenue", "sum"))
                 .sort_values("order_hour_local").reset_index(drop=True))


def weekday_hour_heatmap(daily: pd.DataFrame) -> pd.DataFrame:
    """Orders per weekday (rows) and hour (columns): when the restaurants are busy."""
    frame = daily.assign(weekday=daily["business_date"].dt.day_name())
    grid = frame.pivot_table(index="weekday", columns="order_hour_local", values="orders", aggfunc="sum", fill_value=0)
    return grid.reindex([d for d in WEEKDAYS if d in grid.index])


def holiday_effect(daily: pd.DataFrame, holidays: dict[date, str] | None = None, weeks: int = 4) -> pd.DataFrame:
    """Revenue on each holiday against a normal day: the median revenue of the same weekday in the `weeks`
    weeks before and after (holidays themselves left out). `vs_normal` is a fraction (0.25 = 25 % above normal)."""
    holidays = HOLIDAYS_2023 if holidays is None else holidays
    per_day = daily.groupby("business_date")["revenue"].sum()
    holiday_stamps = {pd.Timestamp(d) for d in holidays}
    rows = []
    for holiday, name in sorted(holidays.items()):
        stamp = pd.Timestamp(holiday)
        if stamp not in per_day.index:
            continue
        neighbours = [stamp + pd.Timedelta(weeks=k) for k in range(-weeks, weeks + 1) if k != 0]
        normal = [per_day[n] for n in neighbours if n in per_day.index and n not in holiday_stamps]
        baseline = float(pd.Series(normal).median()) if normal else float("nan")
        revenue = float(per_day[stamp])
        rows.append({"date": stamp, "holiday": name, "weekday": stamp.day_name(), "revenue": revenue,
                     "normal_revenue": baseline, "vs_normal": safe_ratio(revenue - baseline, baseline)})
    return pd.DataFrame(rows, columns=["date", "holiday", "weekday", "revenue", "normal_revenue", "vs_normal"])


def category_totals(category: pd.DataFrame) -> pd.DataFrame:
    """Revenue and units per menu category, with the share of revenue, biggest first."""
    named = category.assign(item_category=category["item_category"].fillna("(no category)"))   # groupby would drop empty ones
    g = named.groupby("item_category", as_index=False).agg(
        revenue=("revenue", "sum"), item_quantity=("item_quantity", "sum"))
    g["share"] = safe_ratio(g["revenue"], g["revenue"].sum())
    return g.sort_values("revenue", ascending=False).reset_index(drop=True)


def category_by_month(category: pd.DataFrame, top: int = 6) -> pd.DataFrame:
    """Monthly revenue of the `top` biggest categories (everything else added up as 'Other')."""
    totals = category_totals(category)
    keep = set(totals["item_category"].head(top))
    frame = category.assign(
        item_category=category["item_category"].fillna("(no category)").where(lambda s: s.isin(keep), "Other"),
        month=category["business_date"].dt.to_period("M").dt.start_time)
    return frame.groupby(["month", "item_category"], as_index=False)["revenue"].sum()


def location_table(daily: pd.DataFrame, summary: pd.DataFrame) -> pd.DataFrame:
    """One row per restaurant for the selected days, with customer retention from gold.location_summary.

    Revenue, orders and order size follow the selected dates. Customers and repeat customers are whole-year
    figures (a customer's repeat orders cannot be split by date range), so the repeat rate is whole-year too."""
    g = daily.groupby("restaurant_id", as_index=False).agg(
        orders=("orders", "sum"), revenue=("revenue", "sum"), item_quantity=("item_quantity", "sum"),
        days_open=("business_date", "nunique"))
    g["avg_order_value"] = safe_ratio(g["revenue"], g["orders"])
    g["orders_per_day"] = safe_ratio(g["orders"], g["days_open"])
    g["share_of_revenue"] = safe_ratio(g["revenue"], g["revenue"].sum())
    retention = summary[["restaurant_id", "customers", "repeat_customers"]].copy()
    retention["repeat_rate"] = safe_ratio(retention["repeat_customers"], retention["customers"])
    g = g.merge(retention, on="restaurant_id", how="left")
    g["rank"] = g["revenue"].rank(ascending=False, method="min").astype(int)
    g["label"] = g["restaurant_id"].map(short_id)
    return g.sort_values("rank").reset_index(drop=True)


def location_insights(table: pd.DataFrame, min_customers: int = 30) -> list[str]:
    """Plain-language findings from the location table (restaurants with few customers are left out of the retention ranking)."""
    if table.empty:
        return []
    top, bottom = table.iloc[0], table.iloc[-1]
    notes = [f"**Highest revenue:** {top['label']} with ${top['revenue']:,.0f} ({top['share_of_revenue']:.0%} of the total) "
             f"and {top['orders_per_day']:.1f} orders per day."]
    if len(table) > 1:
        notes.append(f"**Lowest revenue:** {bottom['label']} with ${bottom['revenue']:,.0f} "
                     f"({bottom['share_of_revenue']:.1%} of the total): a candidate for a closer look or targeted promotion.")
    biggest_orders = table.loc[table["avg_order_value"].idxmax()]
    notes.append(f"**Largest average order:** {biggest_orders['label']} at ${biggest_orders['avg_order_value']:.2f}.")
    known = table[table["customers"].fillna(0) >= min_customers]
    if not known.empty and known["repeat_rate"].notna().any():
        best = known.loc[known["repeat_rate"].idxmax()]
        worst = known.loc[known["repeat_rate"].idxmin()]
        notes.append(f"**Best customer retention:** {best['label']}, where {best['repeat_rate']:.0%} of customers ordered again "
                     f"(lowest: {worst['label']} at {worst['repeat_rate']:.0%}).")
    return notes


def loyalty_trend(daily: pd.DataFrame) -> pd.DataFrame:
    """Monthly share of orders and revenue that comes from loyalty members."""
    frame = daily.assign(month=daily["business_date"].dt.to_period("M").dt.start_time)
    g = frame.groupby("month", as_index=False).agg(
        orders=("orders", "sum"), revenue=("revenue", "sum"),
        loyalty_orders=("loyalty_orders", "sum"), loyalty_revenue=("loyalty_revenue", "sum"))
    g["loyalty_order_share"] = safe_ratio(g["loyalty_orders"], g["orders"])
    g["loyalty_revenue_share"] = safe_ratio(g["loyalty_revenue"], g["revenue"])
    return g


# ================================================================ discounts (page 6)
def discount_summary(daily: pd.DataFrame) -> dict:
    """Orders and revenue split by whether the order carried a discount (a negative option price).

    The source data has no discounts at all (SME-confirmed data limitation, 2026-10-14), so today
    `discounted_orders` is 0; the page is ready for the day the rule finds some."""
    orders, revenue = int(daily["orders"].sum()), float(daily["revenue"].sum())
    discounted = int(daily["discounted_orders"].sum())
    return {"orders": orders, "revenue": revenue, "discounted_orders": discounted,
            "full_price_orders": orders - discounted,
            "discounted_share": safe_ratio(discounted, orders),
            "avg_order_value": safe_ratio(revenue, orders)}
