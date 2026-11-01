"""Page 1: customer segmentation (RFM)."""
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard import data, logic, queries, ui


def render() -> None:
    ui.page_header("Customer segmentation",
                   "What distinct customer segments emerge when customers are grouped by recency, frequency, spend and loyalty?")
    as_of = ui.as_of_date()
    ui.as_of_note(as_of)
    cube = data.query(queries.customer_cube(as_of))
    if cube.empty:
        st.warning("No customers on this day. Pick a later date in the sidebar.")
        return

    segments = logic.segment_summary(cube)
    by_name = segments.set_index("rfm_segment")
    total_customers, total_clv = segments["customers"].sum(), segments["clv"].sum()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Customers", ui.number(total_customers))
    c2.metric("Lifetime value (CLV)", ui.money(total_clv))
    if "VIP" in by_name.index:
        c3.metric("VIP customers", ui.number(by_name.loc["VIP", "customers"]),
                  f"{ui.percent(by_name.loc['VIP', 'share_of_clv'])} of all CLV", delta_color="off")
    if "Churn Risk" in by_name.index:
        c4.metric("Churn Risk customers", ui.number(by_name.loc["Churn Risk", "customers"]),
                  f"{ui.percent(by_name.loc['Churn Risk', 'share_of_customers'])} of customers", delta_color="off")

    st.subheader("Who is in each segment")
    left, right = st.columns(2)
    with left:
        fig = px.bar(segments, x="rfm_segment", y="customers", color="rfm_segment",
                     color_discrete_map=ui.SEGMENT_COLORS, text_auto=",", labels={"rfm_segment": "", "customers": "Customers"})
        fig.update_traces(hovertemplate="%{x}: %{y:,} customers<extra></extra>")
        ui.show(fig, legend=False, y_title="Customers")
    with right:
        fig = px.bar(segments, x="rfm_segment", y="share_of_clv", color="rfm_segment",
                     color_discrete_map=ui.SEGMENT_COLORS, text_auto=".0%", labels={"rfm_segment": ""})
        fig.update_traces(hovertemplate="%{x}: %{y:.1%} of CLV<extra></extra>")
        fig.update_yaxes(tickformat=".0%")
        ui.show(fig, legend=False, y_title="Share of total CLV")

    shown = segments.assign(meaning=segments["rfm_segment"].map(logic.SEGMENT_MEANING))[
        ["rfm_segment", "customers", "share_of_customers", "avg_clv", "avg_order_value",
         "orders_90d_per_customer", "meaning"]]
    ui.table(shown,
             rfm_segment="Segment", customers=st.column_config.NumberColumn("Customers", format="localized"),
             share_of_customers=st.column_config.NumberColumn("Share", format="percent"),
             avg_clv=st.column_config.NumberColumn("Avg CLV", format="dollar"),
             avg_order_value=st.column_config.NumberColumn("Avg order", format="dollar"),
             orders_90d_per_customer=st.column_config.NumberColumn("Orders / customer, last 90 days", format="%.2f"),
             meaning="Rule")

    st.subheader("Recency × frequency")
    st.caption("Each cell counts customers with that recency score (rows: 5 = ordered in the last week) and "
               "frequency score (columns: 5 = 6 or more orders in the last 90 days).")
    grid = logic.rfm_grid(cube)
    heat = go.Figure(go.Heatmap(z=grid.values, x=[f"F{c}" for c in grid.columns], y=[f"R{r}" for r in grid.index],
                                colorscale=ui.SEQUENTIAL_BLUE, texttemplate="%{z:,}", showscale=False,
                                hovertemplate="%{y}, %{x}: %{z:,} customers<extra></extra>"))
    heat.update_yaxes(autorange="reversed")
    ui.show(heat, height=320, legend=False)

    st.subheader("Customer lifetime value tiers")
    tiers = logic.tier_summary(cube)
    left, right = st.columns([2, 3])
    with left:
        ui.table(tiers, clv_tier="Tier", customers=st.column_config.NumberColumn("Customers", format="localized"),
                 clv=st.column_config.NumberColumn("CLV", format="dollar"),
                 share_of_clv=st.column_config.NumberColumn("Share of CLV", format="percent"))
    with right:
        st.caption("High = the top 20 % of customers by lifetime value on this day, Low = the bottom 20 %. "
                   "A small group of High customers holds most of the value.")

    st.subheader("How segments change over the year")
    series = data.query(queries.SEGMENTS_OVER_TIME)
    wide = logic.segments_over_time(series).reset_index().melt("snapshot_date", var_name="Segment", value_name="Customers")
    fig = px.area(wide, x="snapshot_date", y="Customers", color="Segment", color_discrete_map=ui.SEGMENT_COLORS,
                  category_orders={"Segment": logic.SEGMENT_ORDER})
    fig.add_vline(x=as_of, line_dash="dot", line_color=ui.MUTED)
    fig.update_traces(hovertemplate="%{y:,} customers<extra>%{fullData.name}</extra>")
    ui.show(fig, y_title="Customers", x_title="")
