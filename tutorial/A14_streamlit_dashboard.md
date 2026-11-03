# Chapter A14: Streamlit and the dashboard

**Time:** 2 hours. **Goal:** understand Streamlit's rerun model, read `dashboard/`, add a page and a test.

## 1. What Streamlit is

A Python library that turns a script into a web app. No HTML/JS. You write Python top to bottom; widgets and charts appear.

```python
import streamlit as st
import pandas as pd
st.title("Orders")
df = pd.read_csv("orders.csv")
loc = st.selectbox("Location", sorted(df["location"].unique()))
st.metric("Revenue", f'{df[df.location == loc].amount.sum():.2f}')
st.bar_chart(df.groupby("location").amount.sum())
```

Run: `pip install streamlit` then `streamlit run app.py` → http://localhost:8501.

## 2. The rerun model (the key idea)

**Every time the user touches a widget, Streamlit re-runs your whole script from the top.** Consequences:
- Variables reset on each run. Keep values with `st.session_state` (`st.session_state["x"] = 1`).
- Expensive work must be cached: `@st.cache_data` (data results, keyed by arguments, with `ttl`) and `@st.cache_resource` (connections, models; one shared object).
- Widgets return their current value; use `key=` to give them identity.

## 3. Layout and widgets

`st.sidebar`, `st.columns`, `st.tabs`, `st.expander`, `st.container`; widgets: `selectbox`, `slider`, `date_input`, `radio`, `multiselect`, `button`, `toggle`; display: `st.dataframe`, `st.table`, `st.metric`, `st.plotly_chart`, `st.caption`, `st.warning`. Multi-page: this project's `app.py` builds the sidebar navigation and calls one function per page in `dashboard/views/`.

## 4. This project's layers

| File | Responsibility |
|---|---|
| `dashboard/queries.py` | SQL strings that return small sums/aggregates (no row-level data) |
| `dashboard/logic.py` | pandas calculations on those results (tested without Streamlit) |
| `dashboard/data.py` | `query(sql)`: Spark SQL locally, Athena on AWS (chosen by `PIPELINE_ENV`) |
| `dashboard/ui.py` | shared widgets/formatting |
| `dashboard/views/*.py` | the six pages: segmentation, churn, sales, loyalty, locations, discounts |
| `dashboard/app.py` | sidebar ("as of" date), navigation, page dispatch |

Why this split: SQL in one place, logic testable, UI thin, data source swappable. The same code runs on your laptop and AWS.

## 5. Charts

Use Plotly (`plotly.express`) for interactive charts: `px.line`, `px.bar`, `px.scatter`, `px.treemap`; pass a DataFrame and column names; `st.plotly_chart(fig, use_container_width=True)`. Good practice: label axes and units, sort bars, avoid dual axes, one message per chart, show numbers where a decision needs them. The "as of" date selects the day the customer pages describe because `customer_daily_snapshot` has a row per customer per day.

## 6. Performance and safety

- Push aggregation into SQL (Athena/Spark), not pandas on millions of rows; each Athena query scans data and costs money, so **cache** with a `ttl`.
- Read-only role for the app. No secrets in code; use the task role.
- Behind AWS: ECS Fargate task + ALB; HTTP and one IP in this demo (HTTPS + sign-in needed for production).

## 7. Testing (Streamlit `AppTest`)

```python
from streamlit.testing.v1 import AppTest
def test_page_runs():
    at = AppTest.from_file("dashboard/app.py").run(timeout=60)
    assert not at.exception
```

`tests/test_dashboard_pages.py` runs every page headlessly against a stand-in data layer and checks key numbers. `tests/test_dashboard_logic.py` tests pandas logic directly.

## 8. Exercises

1. Build the 10-line app above on the A1 sandbox `orders.csv`; add a slider that filters by amount.
2. Run the project dashboard locally (README, "Run the dashboard") and click every page.
3. Add `st.session_state` to remember the last chosen location.
4. Add a seventh page `dashboard/views/top_customers.py` (top 10 customers by CLV at the "as of" date): query in `queries.py`, logic in `logic.py`, test in `tests/`.
5. Explain what happens when you move the "as of" date (rerun → new query → new numbers).
6. Explain why `@st.cache_data` matters on AWS (cost and latency).

## Interview questions

1. How does Streamlit's execution model work? 2. `cache_data` vs `cache_resource`? 3. Streamlit vs Dash vs Tableau/Power BI? 4. How do you deploy a Streamlit app? 5. How do you keep a dashboard fast and cheap? 6. How do you handle authentication? 7. How do you test a dashboard? 8. Where should business logic live? (not in the UI)

## Done when

Exercise 4 done with a passing test, and you explain the layer split.
