"""GlobalPartners business insights dashboard (Streamlit). Entry point:

    streamlit run dashboard/app.py

Streamlit runs this script from top to bottom on every click; st.navigation then runs the chosen page.
Local: reads the Iceberg lake with Spark. AWS: reads the gold tables with Athena (see data.py).
"""
import streamlit as st

from dashboard import data, ui
from dashboard.views import churn, discounts, loyalty, locations, sales, segmentation

st.set_page_config(page_title="GlobalPartners insights", page_icon=":material/insights:", layout="wide")

PAGES = [
    st.Page(segmentation.render, title="Customer segmentation", url_path="segmentation", icon=":material/groups:", default=True),
    st.Page(churn.render, title="Churn risk", url_path="churn", icon=":material/notifications_active:"),
    st.Page(sales.render, title="Sales trends", url_path="sales", icon=":material/trending_up:"),
    st.Page(loyalty.render, title="Loyalty program", url_path="loyalty", icon=":material/loyalty:"),
    st.Page(locations.render, title="Location performance", url_path="locations", icon=":material/storefront:"),
    st.Page(discounts.render, title="Pricing and discounts", url_path="discounts", icon=":material/sell:"),
]

st.sidebar.markdown("### GlobalPartners")
current = st.navigation(PAGES)
ui.as_of_selector()
st.sidebar.caption(f"2023 orders · data from the gold tables ({'Athena' if data.engine() == 'athena' else 'local Spark'}) · "
                   "refreshed after each daily pipeline run")
current.run()
