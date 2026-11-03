# Stage B12: the Streamlit dashboard

**Goal:** six pages that answer the business questions, reading gold through one data layer that works locally (Spark SQL) and on AWS (Athena). Prerequisites: A14, B9.

## Layers (build in this order)

1. `dashboard/data.py`: `query(sql) -> pandas.DataFrame`. Local: a Spark session with an in-memory default catalog and the Iceberg `lake` catalog; AWS: boto3 Athena (start query, poll, read rows). Selected by `PIPELINE_ENV`.
2. `dashboard/queries.py`: SQL strings returning small aggregates.
3. `dashboard/logic.py`: pandas calculations (no Streamlit imports) with tests.
4. `dashboard/ui.py`: shared formatting.
5. `dashboard/views/*.py`: one function per page.
6. `dashboard/app.py`: sidebar navigation and the **as-of date** that selects the day the customer pages describe.

## The six pages

| Page | Question | Key elements |
|---|---|---|
| Customer segmentation | who are our customers? | RFM segments, recency × frequency grid, CLV tiers, segments over time |
| Churn risk | who is leaving? | churn status counts, threshold slider, re-engagement alert list |
| Sales trends | when do we sell? | revenue over time, holidays, weekday × hour, by category |
| Loyalty program | does loyalty pay off? | members vs non-members: CLV, repeat rate (association, not proof) |
| Location performance | which restaurants lead? | ranking, top vs rest, table by restaurant id |
| Pricing and discounts | do discounts work? | states that the data contains no discounts |

## Check (full-year data)

At 31 December: 10,512 customers; CLV $673,614.04; segments Churn Risk 7,693 · Regular 1,661 · VIP 755 · New 403; churn 2,409 / 1,553 / 6,550; revenue $746,223.86; 52,015 orders; 20 restaurants; loyalty 4,985 members (47 %), repeat-order rate 67 % vs 37 %.

```bash
docker compose up -d dashboard      # http://localhost:8501
python -m pytest tests/test_dashboard_logic.py tests/test_dashboard_pages.py -q
```

## Tests

`streamlit.testing.v1.AppTest` runs each page headlessly. Add a regression test for the AWS import bug: assert the Dockerfile sets `PYTHONPATH=/app`.

## Compare with the real project

Everything under `dashboard/`, plus `tests/test_dashboard_*.py`.

## Done when

All six pages load, show the numbers above, and the page tests pass.
