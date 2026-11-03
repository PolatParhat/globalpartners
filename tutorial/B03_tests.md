# Stage B3: tests

**Goal:** a pytest suite that proves each function and each business rule, with tiny inputs and exact answers.
**Prerequisite:** B2 (`report.py`). Read chapter A9 first.

## Type this: `test_report.py`

```python
import pandas as pd
import pytest

from report import FAULTY_ACCOUNT, add_business_date, in_scope, line_revenue, summary


def make_items(rows):
    cols = ["app_name", "creation_time_utc", "order_id", "user_id", "lineitem_id", "item_price", "item_quantity"]
    return pd.DataFrame(rows, columns=cols)


def test_business_date_uses_new_york_time():
    # 2023-01-01 03:00 UTC is still 31 Dec 2022 in New York
    items = make_items([["Alltown Fresh", "2023-01-01T03:00:00Z", "o1", "u1", "l1", "5.00", "1"]])
    assert str(add_business_date(items)["business_date"].iloc[0]) == "2022-12-31"


def test_timestamps_with_and_without_fraction_both_parse():
    items = make_items([
        ["Alltown Fresh", "2023-03-08T11:03:32.223Z", "o1", "u1", "l1", "5.00", "1"],
        ["Alltown Fresh", "2023-03-08T11:03:32Z", "o2", "u1", "l1", "5.00", "1"],
    ])
    assert len(add_business_date(items)) == 2


def test_test_app_and_out_of_range_are_excluded():
    items = add_business_date(make_items([
        ["Alltown Fresh", "2023-06-01T15:00:00Z", "o1", "u1", "l1", "5.00", "1"],
        ["Alltown Fresh - DEVELOPMENT", "2023-06-01T15:00:00Z", "o2", "u1", "l1", "5.00", "1"],
        ["Alltown Fresh", "2024-02-01T15:00:00Z", "o3", "u1", "l1", "5.00", "1"],
    ]))
    assert list(in_scope(items, "2023-01-01", "2023-12-31")["order_id"]) == ["o1"]


def test_line_revenue_adds_option_price_times_quantity():
    items = make_items([["Alltown Fresh", "2023-06-01T15:00:00Z", "o1", "u1", "l1", "10.00", "2"]])
    opts = pd.DataFrame([["o1", "l1", "0.50"], ["o1", "l1", "0.25"]],
                        columns=["order_id", "lineitem_id", "option_price"])
    assert line_revenue(items, opts)["revenue"].iloc[0] == pytest.approx(11.50)   # 10 + (0.50+0.25)*2


def test_line_without_options_keeps_item_price():
    items = make_items([["Alltown Fresh", "2023-06-01T15:00:00Z", "o1", "u1", "l1", "10.00", "1"]])
    opts = pd.DataFrame(columns=["order_id", "lineitem_id", "option_price"])
    assert line_revenue(items, opts)["revenue"].iloc[0] == pytest.approx(10.00)


def test_guests_and_faulty_account_are_not_customers():
    lines = make_items([
        ["a", "t", "o1", "", "l1", "1", "1"],
        ["a", "t", "o2", FAULTY_ACCOUNT, "l1", "1", "1"],
        ["a", "t", "o3", "u1", "l1", "1", "1"],
    ]).assign(revenue=1.0)
    assert summary(lines)["customers"] == 1
    assert summary(lines)["orders"] == 3          # sales keep guests and the faulty account
```

## Check

```bash
pytest -q
```

Expected (verified): `6 passed`.

## Exercises (do all)

1. **Break it:** change `tz_convert` to UTC and see which test fails. Revert.
2. **Test first:** add the rule "an order whose revenue is negative is flagged `is_invalid`". Write the failing test, then the function `flag_invalid(lines)`; make it pass. (This mirrors the quarantine idea in `quality/quarantine.py`.)
3. **Parametrize** the option test over three cases (no options, one, two).
4. **Edge cases:** empty DataFrame input to every function; what should happen?
5. Commit: `git add -A && git commit -m "B3: tests for the rules"`.

## Compare with the real project

`tests/test_cleaning.py`, `test_silver_order_items.py`, `test_gold.py`: same style, with a Spark session fixture instead of pandas.

## Done when

All tests pass, and you wrote one rule test-first.
