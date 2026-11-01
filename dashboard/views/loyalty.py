"""Page 4: loyalty program impact."""
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard import data, logic, queries, ui


def render() -> None:
    ui.page_header("Loyalty program impact",
                   "How does loyalty membership affect customer spending and repeat orders?")
    as_of = ui.as_of_date()
    ui.as_of_note(as_of)
    cube = data.query(queries.customer_cube(as_of))
    compare = logic.loyalty_comparison(cube) if not cube.empty else None
    if compare is None or len(compare) < 2:
        st.warning("This day has customers from only one group, so there is nothing to compare. Pick a later date.")
        return

    member = compare[compare["group"] == "Loyalty member"].iloc[0]
    other = compare[compare["group"] == "Not a member"].iloc[0]

    def lift(a: float, b: float) -> str:
        return f"{logic.safe_ratio(a, b):.1f}× non-members" if b else ""

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Loyalty members", ui.number(member["customers"]),
              f"{ui.percent(logic.safe_ratio(member['customers'], compare['customers'].sum()))} of customers", delta_color="off")
    c2.metric("Avg CLV, member", ui.money(member["avg_clv"], cents=True), lift(member["avg_clv"], other["avg_clv"]), delta_color="off")
    c3.metric("Avg order value, member", ui.money(member["avg_order_value"], cents=True),
              lift(member["avg_order_value"], other["avg_order_value"]), delta_color="off")
    c4.metric("Repeat rate, member", ui.percent(member["repeat_rate"]),
              f"vs {ui.percent(other['repeat_rate'])} non-members", delta_color="off")

    st.subheader("Members compared with non-members")
    measures = [("avg_clv", "Average CLV ($)", ".2f"), ("avg_order_value", "Average order value ($)", ".2f"),
                ("repeat_rate", "Repeat purchase rate", ".0%"), ("orders_per_customer", "Orders per customer", ".1f")]
    cols = st.columns(len(measures))
    for col, (column, title, fmt) in zip(cols, measures):
        with col:
            st.caption(title)
            fig = px.bar(compare, x="group", y=column, color="group", color_discrete_map=ui.GROUP_COLORS,
                         text_auto=fmt, labels={"group": ""})
            fig.update_traces(hovertemplate="%{x}: %{y:" + fmt + "}<extra></extra>")
            ui.show(fig, legend=False, height=280)
    ui.table(compare[["group", "customers", "avg_clv", "avg_order_value", "orders_per_customer", "repeat_rate",
                      "revenue_90d_per_customer"]],
             group="Group", customers=st.column_config.NumberColumn("Customers", format="localized"),
             avg_clv=st.column_config.NumberColumn("Avg CLV", format="dollar"),
             avg_order_value=st.column_config.NumberColumn("Avg order", format="dollar"),
             orders_per_customer=st.column_config.NumberColumn("Orders / customer", format="%.2f"),
             repeat_rate=st.column_config.NumberColumn("Repeat rate", format="percent"),
             revenue_90d_per_customer=st.column_config.NumberColumn("Spend, last 90 days", format="dollar"))
    st.caption("Repeat rate = customers with 2 or more orders ÷ customers. CLV and orders are totals up to the chosen day. "
               "A customer counts as a member if their latest order up to that day was a loyalty order.")
    ui.data_limitation("This shows an association, not a proof of cause: customers who join a loyalty program may "
                       "already be the more engaged ones. To measure the program's own effect, compare the same "
                       "customers before and after they joined.")

    st.subheader("Share of sales from loyalty members")
    trend = logic.loyalty_trend(data.query(queries.SALES_DAILY))
    long = trend.melt("month", ["loyalty_order_share", "loyalty_revenue_share"], "measure", "share")
    long["measure"] = long["measure"].map({"loyalty_order_share": "Share of orders", "loyalty_revenue_share": "Share of revenue"})
    fig = px.line(long, x="month", y="share", color="measure",
                  color_discrete_map={"Share of orders": ui.BLUE, "Share of revenue": ui.ORANGE}, markers=True)
    fig.update_traces(line_width=2, marker_size=8, hovertemplate="%{x|%b %Y}: %{y:.1%}<extra>%{fullData.name}</extra>")
    fig.update_yaxes(tickformat=".0%", rangemode="tozero")
    ui.show(fig, y_title="Loyalty share of all sales", x_title="")
