# Chapter A9: Testing with pytest

**Time:** 2 hours. **Goal:** write tests first, use fixtures and parametrize, test PySpark functions, and read this project's 99 tests.

## 1. Why test

Tests prove the code does what you think, today and after every change. In a pipeline, a silent wrong number is worse than a crash. This project: **99 unit tests** and **21 infra tests**, run on every push by CI.

## 2. First test

```python
# calc.py
def total(xs): return sum(xs)

# test_calc.py
from calc import total
def test_total():
    assert total([1, 2, 3]) == 6
```

```bash
pytest            # finds files test_*.py and functions test_*
pytest -q         # quiet
pytest -x         # stop at first failure
pytest -k total   # only tests with "total" in the name
pytest -v tests/test_cleaning.py::test_name
```

Anatomy: **Arrange** (set up inputs) → **Act** (call the code) → **Assert** (check). One idea per test, a name that says what is expected (`test_negative_price_goes_to_quarantine`).

## 3. Assertions, errors, floats

```python
assert x == 5
assert "boston" in names
import pytest
with pytest.raises(ValueError):
    parse("bad")
assert 0.1 + 0.2 == pytest.approx(0.3)       # floats; for money use Decimal and exact equality
```

## 4. Fixtures

A **fixture** prepares something tests need and cleans it up. Defined with `@pytest.fixture`; a test asks for it by naming it as an argument.

```python
import pytest

@pytest.fixture
def orders():
    return [{"id": 1, "amount": 10}, {"id": 2, "amount": 5}]

def test_sum(orders):
    assert sum(o["amount"] for o in orders) == 15
```

Scope: `function` (default, fresh each test), `module`, `session` (created once; used for the **Spark session**, because starting Spark takes seconds). Shared fixtures live in `tests/conftest.py`.

## 5. Parametrize

Run one test with many inputs:

```python
@pytest.mark.parametrize("raw, expected", [("12.50", 1250), ("0", 0), ("-1", -100)])
def test_cents(raw, expected):
    assert to_cents(raw) == expected
```

## 6. Testing PySpark code

Design for it: transformations are **pure functions** `DataFrame -> DataFrame`; jobs do the I/O (project rule). Test with tiny DataFrames and a session fixture:

```python
def test_revenue(spark):
    df = spark.createDataFrame([(1, "10.00", "2.00")], "id int, item_price string, option_total string")
    out = add_line_revenue(df)
    assert out.collect()[0]["revenue"] == Decimal("12.00")
```

Tips: assert on collected rows or on `df.collect()` sets; sort before comparing; keep data tiny; test edge cases (NULLs, empty input, duplicates, negative prices, bad dates). See `tests/test_silver_order_items.py`, `test_customer_snapshot.py`.

## 7. Mocking and testing I/O

A **mock** replaces a real dependency (AWS, database) with a fake, so tests are fast and need no credentials. `unittest.mock.patch`, `MagicMock`, pytest's `monkeypatch`. `tests/test_dashboard_data.py` uses a stand-in for boto3/Athena. Do not over-mock: tests that check mocks prove nothing. Streamlit pages are tested headlessly with `streamlit.testing.v1.AppTest` (`test_dashboard_pages.py`).

## 8. Infrastructure tests

`infra/tests/test_stacks.py` synthesizes the CDK app into CloudFormation and asserts properties: for example, every Airflow log module has a log level, the dashboard role is read-only, nothing is retained after delete. Chapter A12.

## 9. Test pyramid and what to test

Many fast **unit** tests; fewer **integration** tests (several parts together, e.g. silver → gold on a tiny CSV); few **end-to-end** tests (chapter C3). Test: business rules (revenue formula, churn thresholds), edge cases, regressions (every bug gets a test: the MWAA log level, the `PYTHONPATH`), and data-quality logic. Don't test the library.
**Coverage** (`pytest --cov`) shows which lines ran; 100 % does not mean correct.

## 10. TDD in one loop

1. Write a failing test for the new behavior (red). 2. Write the least code to pass (green). 3. Clean up (refactor). Repeat. The test documents the rule.

## 11. Exercises

1. Run the project's tests: `docker compose exec spark python3 -m pytest -q`. Count them (99).
2. Read `tests/test_cleaning.py`; explain the Arrange/Act/Assert of three tests.
3. **Break a rule on purpose** (on a scratch branch): change the revenue formula and watch which tests fail; revert.
4. TDD: add the rule "an order total over 500 dollars is flagged `is_large`". Write the failing test first in `tests/`, then the code.
5. Parametrize three cases of your new rule (below, at, above the limit).
6. Add a fixture and use it in two tests.
7. Write a test for a function with a mocked boto3 client.

## Interview questions

1. Unit vs integration vs end-to-end? 2. What is a fixture; fixture scopes? 3. What is mocking; when is it harmful? 4. How do you test PySpark code? 5. What is TDD? 6. What is a regression test? 7. How do you test data quality? 8. What does coverage tell you and not tell you? 9. How do you keep tests fast? (small data, session-scoped Spark) 10. What makes a test flaky? (time, randomness, shared state, network)

## Done when

Exercises 1 to 7 done; you add a rule test-first and CI-style run is green.
