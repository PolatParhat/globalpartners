"""Page 5: location performance."""
import plotly.express as px
import streamlit as st

from dashboard import data, logic, queries, ui


def render() -> None:
    ui.page_header("Location performance",
                   "Which restaurants earn the most, and what sets the top performers apart (order size, orders per day, customer retention)?")
    daily = data.query(queries.SALES_DAILY)
    summary = data.query(queries.LOCATION_SUMMARY)
    if daily.empty:
        st.warning("No sales loaded yet.")
        return

    first, last = daily["business_date"].min().date(), daily["business_date"].max().date()
    dates = st.date_input("Dates", value=(first, last), min_value=first, max_value=last)
    if len(dates) != 2:
        st.info("Pick an end date.")
        return
    table = logic.location_table(logic.select_sales(daily, *dates), summary)
    if table.empty:
        st.warning("No sales in these dates.")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("Restaurants with sales", ui.number(len(table)))
    c2.metric("Top restaurant", table.iloc[0]["label"], f"{ui.money(table.iloc[0]['revenue'])} revenue", delta_color="off")
    top3 = table.head(3)["share_of_revenue"].sum()
    c3.metric("Revenue from the top 3", ui.percent(top3), delta_color="off")
    st.caption("The source has no restaurant names, only ids; each restaurant is shown by the last 6 characters of its id "
               "(the full id is in the table). This is a data limitation confirmed with the SME.")

    st.subheader("Revenue ranking")
    ranked = table.iloc[::-1]
    fig = px.bar(ranked, x="revenue", y="label", orientation="h", color_discrete_sequence=[ui.BLUE],
                 labels={"label": ""}, custom_data=["orders", "avg_order_value", "orders_per_day"])
    fig.update_traces(hovertemplate="%{y}<br>$%{x:,.0f} revenue<br>%{customdata[0]:,} orders · $%{customdata[1]:.2f} per order"
                                    "<br>%{customdata[2]:.1f} orders per day<extra></extra>")
    ui.show(fig, legend=False, height=max(300, 26 * len(table) + 60), x_title="Revenue ($)")

    st.subheader("What distinguishes the top performers")
    for note in logic.location_insights(table):
        st.markdown(f"- {note}")
    scatter_data = table.dropna(subset=["repeat_rate"])
    if not scatter_data.empty:
        fig = px.scatter(scatter_data, x="avg_order_value", y="repeat_rate", size="revenue", text="label",
                         color_discrete_sequence=[ui.BLUE], size_max=34, custom_data=["revenue", "customers"])
        fig.update_traces(textposition="top center", marker=dict(line=dict(width=2, color="white")),
                          hovertemplate="%{text}<br>average order $%{x:.2f}<br>%{y:.0%} of customers ordered again"
                                        "<br>$%{customdata[0]:,.0f} revenue · %{customdata[1]:,} customers<extra></extra>")
        fig.update_yaxes(tickformat=".0%")
        st.caption("Each bubble is a restaurant: order size (across) against customer retention (up); bubble size = revenue.")
        ui.show(fig, height=420, legend=False, x_title="Average order ($)", y_title="Customers who ordered again")

    st.subheader("All restaurants")
    shown = table[["rank", "restaurant_id", "revenue", "share_of_revenue", "orders", "avg_order_value", "orders_per_day",
                   "customers", "repeat_customers", "repeat_rate"]]
    ui.table(shown, rank="Rank", restaurant_id="Restaurant id",
             revenue=st.column_config.NumberColumn("Revenue", format="dollar"),
             share_of_revenue=st.column_config.NumberColumn("Share", format="percent"),
             orders=st.column_config.NumberColumn("Orders", format="localized"),
             avg_order_value=st.column_config.NumberColumn("Average order", format="dollar"),
             orders_per_day=st.column_config.NumberColumn("Orders / day", format="%.1f"),
             customers=st.column_config.NumberColumn("Customers (year)", format="localized"),
             repeat_customers=st.column_config.NumberColumn("Ordered again (year)", format="localized"),
             repeat_rate=st.column_config.NumberColumn("Retention (year)", format="percent"))
    st.caption("Revenue, orders and order size follow the dates above. Customers and retention are whole-year figures: a customer "
               "who ordered at two restaurants counts at both, and a repeat order cannot be split by date. "
               "Retention = customers with 2 or more orders at that restaurant ÷ customers of that restaurant.")
