"""Page 3: sales trends and seasonality."""
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard import data, logic, queries, ui

CATEGORY_PALETTE = [ui.BLUE, ui.ORANGE, ui.AQUA, ui.YELLOW, "#e87ba4", "#008300"]     # fixed order, then grey "Other"
FREQUENCY = {"Daily": "D", "Weekly": "W", "Monthly": "M"}


def render() -> None:
    ui.page_header("Sales trends and seasonality",
                   "What are the weekly and monthly sales trends, when do holidays spike, and how does it differ by category and location?")
    daily = data.query(queries.SALES_DAILY)
    category = data.query(queries.SALES_CATEGORY)
    if daily.empty:
        st.warning("No sales loaded yet.")
        return

    first, last = daily["business_date"].min().date(), daily["business_date"].max().date()
    f1, f2, f3 = st.columns([2, 3, 1])
    dates = f1.date_input("Dates", value=(first, last), min_value=first, max_value=last)
    if len(dates) != 2:
        st.info("Pick an end date.")
        return
    order_of_revenue = daily.groupby("restaurant_id")["revenue"].sum().sort_values(ascending=False).index.tolist()
    chosen = f2.multiselect("Restaurants (empty = all)", order_of_revenue, format_func=logic.short_id)
    frequency = FREQUENCY[f3.radio("View", list(FREQUENCY), index=1)]

    start, end = dates
    picked = logic.select_sales(daily, start, end, chosen)
    picked_category = logic.select_sales(category, start, end, chosen)
    if picked.empty:
        st.warning("No sales for this selection.")
        return

    revenue, orders = picked["revenue"].sum(), picked["orders"].sum()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Revenue", ui.money(revenue))
    c2.metric("Orders", ui.number(orders))
    c3.metric("Average order", ui.money(logic.safe_ratio(revenue, orders), cents=True))
    c4.metric("Days with sales", ui.number(picked["business_date"].nunique()))

    st.subheader("Revenue over time")
    series = logic.sales_by_period(picked, frequency)
    fig = px.line(series, x="period", y="revenue", color_discrete_sequence=[ui.BLUE])
    fig.update_traces(line_width=2, hovertemplate="%{x|%d %b %Y}<br>$%{y:,.0f}<extra></extra>")
    if frequency == "D":
        marks = logic.holiday_effect(picked)
        fig.add_trace(go.Scatter(x=marks["date"], y=marks["revenue"], mode="markers", name="Holiday",
                                 marker=dict(size=9, color=ui.ORANGE, line=dict(width=2, color="white")),
                                 customdata=marks["holiday"],
                                 hovertemplate="%{customdata}<br>%{x|%d %b %Y}: $%{y:,.0f}<extra></extra>"))
    ui.show(fig, y_title="Revenue ($)", legend=frequency == "D")
    if frequency != "D":
        st.caption("Holiday markers appear in the Daily view; the table below lists every holiday.")
    with st.expander("Table view"):
        ui.table(series, period=st.column_config.DateColumn("Period start"),
                 orders=st.column_config.NumberColumn("Orders", format="localized"),
                 revenue=st.column_config.NumberColumn("Revenue", format="dollar"),
                 item_quantity=st.column_config.NumberColumn("Items", format="localized"),
                 avg_order_value=st.column_config.NumberColumn("Average order", format="dollar"))

    st.subheader("Holidays and special days")
    st.caption("Revenue on the day against a normal day: the median of the same weekday in the 4 weeks before and after "
               "(all restaurants selected above).")
    effect = logic.holiday_effect(picked)
    if effect.empty:
        st.caption("No holiday falls in the selected dates.")
    else:
        ui.table(effect,
                 date=st.column_config.DateColumn("Date"), holiday="Holiday", weekday="Weekday",
                 revenue=st.column_config.NumberColumn("Revenue", format="dollar"),
                 normal_revenue=st.column_config.NumberColumn("Normal day", format="dollar"),
                 vs_normal=st.column_config.NumberColumn("Difference", format="percent"))

    st.subheader("When customers order")
    left, right = st.columns(2)
    with left:
        weekday = logic.weekday_profile(picked)
        fig = px.bar(weekday, x="weekday", y="avg_revenue", color_discrete_sequence=[ui.BLUE], labels={"weekday": ""})
        fig.update_traces(hovertemplate="%{x}: $%{y:,.0f} on an average day<extra></extra>")
        st.caption("Average revenue per day of the week")
        ui.show(fig, legend=False, height=300, y_title="Revenue per day ($)")
    with right:
        hours = logic.hour_profile(picked)
        fig = px.bar(hours, x="order_hour_local", y="orders", color_discrete_sequence=[ui.BLUE],
                     labels={"order_hour_local": "Hour of the day (New York)"})
        fig.update_traces(hovertemplate="%{x}:00: %{y:,} orders<extra></extra>")
        st.caption("Orders by hour of the day")
        ui.show(fig, legend=False, height=300, y_title="Orders")
    grid = logic.weekday_hour_heatmap(picked)
    heat = go.Figure(go.Heatmap(z=grid.values, x=[f"{h}:00" for h in grid.columns], y=list(grid.index),
                                colorscale=ui.SEQUENTIAL_BLUE, showscale=False,
                                hovertemplate="%{y} %{x}: %{z:,} orders<extra></extra>"))
    heat.update_yaxes(autorange="reversed")
    st.caption("Busiest times: orders by weekday and hour")
    ui.show(heat, height=300, legend=False)

    st.subheader("By product category")
    if picked_category.empty:
        st.caption("No category data for this selection.")
        return
    totals = logic.category_totals(picked_category)
    whole_year = logic.category_totals(category)["item_category"].tolist()
    colors = {name: CATEGORY_PALETTE[i] for i, name in enumerate(whole_year[:len(CATEGORY_PALETTE)])}
    colors["Other"] = "#a8a7a0"
    left, right = st.columns([2, 3])
    with left:
        fig = px.bar(totals.head(10).iloc[::-1], x="revenue", y="item_category", orientation="h",
                     color_discrete_sequence=[ui.BLUE], labels={"item_category": ""})
        fig.update_traces(hovertemplate="%{y}: $%{x:,.0f}<extra></extra>")
        st.caption("Revenue by category (top 10)")
        ui.show(fig, legend=False, height=340, x_title="Revenue ($)")
    with right:
        monthly = logic.category_by_month(picked_category, top=len(CATEGORY_PALETTE))
        fig = px.bar(monthly, x="month", y="revenue", color="item_category", color_discrete_map=colors)
        fig.update_traces(hovertemplate="%{fullData.name}: $%{y:,.0f}<extra></extra>", marker_line=dict(width=1, color="white"))
        st.caption("Monthly revenue of the biggest categories")
        ui.show(fig, height=340, y_title="Revenue ($)")
    with st.expander("Table view"):
        ui.table(totals, item_category="Category",
                 revenue=st.column_config.NumberColumn("Revenue", format="dollar"),
                 item_quantity=st.column_config.NumberColumn("Units", format="localized"),
                 share=st.column_config.NumberColumn("Share", format="percent"))
