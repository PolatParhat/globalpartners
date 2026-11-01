"""Page 6: pricing and discount effectiveness."""
import plotly.express as px
import streamlit as st

from dashboard import data, logic, queries, ui


def render() -> None:
    ui.page_header("Pricing and discount effectiveness",
                   "How do discounts and promotions affect sales volume and net revenue?")
    daily = data.query(queries.SALES_DAILY)
    if daily.empty:
        st.warning("No sales loaded yet.")
        return

    summary = logic.discount_summary(daily)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Orders (2023)", ui.number(summary["orders"]))
    c2.metric("Revenue", ui.money(summary["revenue"]))
    c3.metric("Average order", ui.money(summary["avg_order_value"], cents=True))
    c4.metric("Orders with a discount", ui.number(summary["discounted_orders"]),
              ui.percent(summary["discounted_share"], 1) + " of orders", delta_color="off")

    if summary["discounted_orders"] == 0:
        ui.data_limitation(
            "**There are no discounts in the source data, so a discounted vs full-price comparison is empty.** "
            "The requirements detect a discount as an option with a negative price (`option_price < 0`); none of the "
            "orders in the data has one, and the source has no other discount field. The SME confirmed this on "
            "2026-10-14 as a data limitation. The pipeline already carries the discount fields "
            "(`has_discount`, `discount_amount`, `discounted_orders`), so when discount data exists only the "
            "detection rule changes.")
        st.subheader("What the revenue is made of today")
        st.caption("All revenue is full price. Average order value by month is the nearest indicator of pricing.")
    else:
        st.subheader("Discounted and full-price orders")
        split = [{"Orders": "Full price", "Count": summary["full_price_orders"]},
                 {"Orders": "With a discount", "Count": summary["discounted_orders"]}]
        fig = px.bar(split, x="Orders", y="Count", color="Orders",
                     color_discrete_map={"Full price": ui.BLUE, "With a discount": ui.ORANGE})
        ui.show(fig, legend=False, height=300, y_title="Orders")

    monthly = logic.sales_by_period(daily, "M")
    fig = px.line(monthly, x="period", y="avg_order_value", markers=True, color_discrete_sequence=[ui.BLUE])
    fig.update_traces(line_width=2, marker_size=8, hovertemplate="%{x|%b %Y}: $%{y:.2f} per order<extra></extra>")
    fig.update_yaxes(rangemode="tozero")
    ui.show(fig, legend=False, height=320, y_title="Average order value ($)", x_title="")
    with st.expander("Table view"):
        ui.table(monthly, period=st.column_config.DateColumn("Month"),
                 orders=st.column_config.NumberColumn("Orders", format="localized"),
                 revenue=st.column_config.NumberColumn("Revenue", format="dollar"),
                 item_quantity=st.column_config.NumberColumn("Items", format="localized"),
                 avg_order_value=st.column_config.NumberColumn("Average order", format="dollar"))
    st.caption("Profit cannot be calculated: the source has prices but no costs. Where discount data exists, the page compares gross "
               "revenue (before discounts) with net revenue (after).")
