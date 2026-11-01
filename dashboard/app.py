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


def main() -> None:
    st.sidebar.markdown("### GlobalPartners")
    current = st.navigation(PAGES)
    try:
        ui.as_of_selector()
        st.sidebar.caption(f"2023 orders · data from the gold tables ({'Athena' if data.engine() == 'athena' else 'local Spark'}) · "
                           "refreshed after each daily pipeline run")
        current.run()
    except Exception as error:                      # noqa: BLE001  (Streamlit's own stop / rerun signals are not Exceptions)
        # Typical right after a deployment: the dashboard is up, but the pipeline has not produced the gold tables yet.
        st.error("The dashboard could not read the gold tables. If the pipeline has not run yet, run the daily DAG "
                 "in Airflow first (it builds the gold tables), then reload this page.")
        with st.expander("Technical details"):
            st.code(f"{type(error).__name__}: {error}")


main()
