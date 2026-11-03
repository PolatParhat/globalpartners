# Chapter C3: an end-to-end test in CI

**Branch:** `harden-e2e-test`. **Cost:** free (runs in GitHub Actions). **Why:** unit tests prove pieces; an end-to-end test proves the pieces fit and the numbers come out.

## What you build

A tiny, hand-made dataset with **known answers**, run through the real transformations and metrics in a local Spark session (no SQL Server, no Docker, no Airflow):

1. **Fixture data:** `tests/e2e/data/` with ~10 orders: 2 customers, a guest, a test-app order, an option with quantity 2, an order near midnight UTC (to test the New York date), and one bad row (negative price → quarantine).
2. **Expected numbers by hand** (in a comment or JSON): orders, revenue, customers, CLV per customer, RFM segment, churn status at a given day.
3. **`tests/e2e/test_pipeline.py`:** load the fixtures as "bronze" DataFrames → silver transforms → gold facts/dimensions → metrics → assert every expected number, plus: quarantine has exactly the bad row with its reason; revenue equal in orders, lines and sales; snapshot has a row for every day between first order and last day.
4. **Idempotency test:** run the chain twice with MERGE helpers on a temp Iceberg (Hadoop catalog in a temp folder); counts identical.
5. **CI:** mark with `@pytest.mark.e2e`; run in the same job (it should take well under a minute).

## Check

- The test fails if you change the revenue formula or the time zone.
- The test passes on a clean runner (CI green).

## Interview angle

Test pyramid; golden datasets; testing data pipelines without production data; idempotency tests.

## Done when

The e2e test is green in CI, and breaking a business rule turns it red.
