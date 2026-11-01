"""Page 2: churn risk indicators and threshold alerts."""
import plotly.express as px
import streamlit as st

from dashboard import data, logic, queries, ui

DIMENSIONS = {
    "How many orders": ("order_band", logic.ORDER_BANDS),
    "How often they order": ("gap_band", logic.GAP_BANDS),
    "Spend trend (last 30 days vs the 30 before)": ("trend_band", logic.TREND_BANDS),
}


def render() -> None:
    ui.page_header("Churn risk",
                   "Which behaviours (days since the last order, order rhythm, spend trend) go with a higher churn risk?")
    as_of = ui.as_of_date()
    ui.as_of_note(as_of)
    bands = data.query(queries.churn_bands(as_of))
    if bands.empty:
        st.warning("No customers on this day. Pick a later date in the sidebar.")
        return

    totals = logic.churn_totals(bands)
    status = totals.set_index("churn_status")
    st.caption("Status by days since the last order: **active** = 45 days or fewer, **at risk** = 46 to 90 days, "
               "**lapsed** = more than 90 days (config/business_rules.yaml, churn).")

    cols = st.columns(4)
    for col, name in zip(cols[:3], logic.CHURN_ORDER):
        if name in status.index:
            col.metric(ui.STATUS_LABELS[name], ui.number(status.loc[name, "customers"]),
                       f"{ui.percent(status.loc[name, 'share'])} of customers · {ui.money(status.loc[name, 'clv'])} CLV",
                       delta_color="off")
    held = status.reindex(["at_risk", "lapsed"])["clv"].sum()
    cols[3].metric("CLV held by at-risk + lapsed", ui.money(held), delta_color="off")

    st.subheader("What goes with a higher churn risk")
    st.caption("For each group of customers: the share who are no longer active. Taller bar = higher churn risk.")
    tabs = st.tabs(list(DIMENSIONS))
    for tab, (label, (column, order)) in zip(tabs, DIMENSIONS.items()):
        with tab:
            risk = logic.band_risk(bands, column, order)
            fig = px.bar(risk, x=column, y="not_active_share", text_auto=".0%", labels={column: ""},
                         color_discrete_sequence=[ui.BLUE])
            fig.update_traces(customdata=risk[["customers", "at_risk", "lapsed"]],
                              hovertemplate="%{x}<br>%{y:.0%} not active<br>%{customdata[0]:,} customers "
                                            "(%{customdata[1]:,} at risk, %{customdata[2]:,} lapsed)<extra></extra>")
            fig.update_yaxes(tickformat=".0%", range=[0, 1])
            ui.show(fig, legend=False, height=300, y_title="Not active (at risk or lapsed)")
            ui.table(risk.rename(columns={column: label}),
                     active=st.column_config.NumberColumn("Active", format="localized"),
                     at_risk=st.column_config.NumberColumn("At risk", format="localized"),
                     lapsed=st.column_config.NumberColumn("Lapsed", format="localized"),
                     customers=st.column_config.NumberColumn("Customers", format="localized"),
                     not_active_share=st.column_config.NumberColumn("Not active", format="percent"),
                     lapsed_share=st.column_config.NumberColumn("Lapsed", format="percent"))

    st.subheader("Re-engagement alert")
    st.caption("At-risk customers who are worth a message: silent for a while and with a high lifetime value.")
    c1, c2 = st.columns(2)
    min_days = c1.slider("Days since the last order, at least", 46, 90, 60,
                         help="At-risk customers are between 46 and 90 days since their last order.")
    min_clv = c2.slider("Lifetime value, at least ($)", 0, 500, 50, step=10)
    customers = data.query(queries.at_risk_customers(as_of))
    alerts = logic.at_risk_alerts(customers, min_days, min_clv)
    if len(customers) >= 500:
        st.caption("The list holds the 500 at-risk customers with the highest lifetime value.")
    st.metric("Customers to contact", ui.number(len(alerts)),
              f"{ui.money(alerts['revenue_to_date'].sum())} lifetime value" if len(alerts) else None, delta_color="off")
    shown = alerts[["customer_id", "days_since_last_order", "orders_to_date", "revenue_to_date",
                    "avg_days_between_orders", "spend_change_pct_30d", "rfm_segment", "is_loyalty_as_of"]]
    ui.table(shown, customer_id="Customer",
             days_since_last_order=st.column_config.NumberColumn("Days since last order", format="%d"),
             orders_to_date="Orders", revenue_to_date=st.column_config.NumberColumn("CLV", format="dollar"),
             avg_days_between_orders=st.column_config.NumberColumn("Usual days between orders", format="%.0f"),
             spend_change_pct_30d=st.column_config.NumberColumn("Spend change, 30 days (%)", format="%.0f"),
             rfm_segment="Segment", is_loyalty_as_of="Loyalty member")
    if len(alerts):
        st.download_button("Download the list (CSV)", shown.to_csv(index=False), file_name=f"at_risk_{as_of}.csv",
                           mime="text/csv")
