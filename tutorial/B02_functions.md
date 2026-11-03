# Stage B2: split into functions

**Goal:** the same logic in small **pure functions** (input → output, no hidden state, no printing). `main()` only wires them together.
**Why now:** B1 works but cannot be tested in parts; one bug means rereading everything. Pure functions are the unit of testing (B3) and later of Spark transformations.

## Rule of thumb

If a block of code has a name you can say in a sentence ("convert to New York date"), it is a function. Jobs do I/O (read files, print); functions only transform.

## Type this: `report.py` (rename/replace `main.py`)

```python
from decimal import Decimal  # (used from B4 onward for exact money)

import pandas as pd

TEST_APP = "Alltown Fresh - DEVELOPMENT"
FAULTY_ACCOUNT = "5ece77fe902ad501337b23fd"


def load_raw(raw_dir: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    items = pd.read_csv(f"{raw_dir}/order_items.csv", dtype=str, keep_default_na=False)
    opts = pd.read_csv(f"{raw_dir}/order_item_options.csv", dtype=str, keep_default_na=False)
    items.columns = [c.lower() for c in items.columns]
    opts.columns = [c.lower() for c in opts.columns]
    return items, opts


def add_business_date(items: pd.DataFrame, timezone: str = "America/New_York") -> pd.DataFrame:
    ts = pd.to_datetime(items["creation_time_utc"], format="ISO8601", utc=True)
    return items.assign(business_date=ts.dt.tz_convert(timezone).dt.date)


def in_scope(items: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    d = items["business_date"]
    keep = (d >= pd.Timestamp(start).date()) & (d <= pd.Timestamp(end).date()) & (items["app_name"] != TEST_APP)
    return items[keep]


def line_revenue(items: pd.DataFrame, opts: pd.DataFrame) -> pd.DataFrame:
    items = items.assign(item_price=pd.to_numeric(items["item_price"]),
                         item_quantity=pd.to_numeric(items["item_quantity"]))
    opt_sum = (opts.assign(option_price=pd.to_numeric(opts["option_price"]))
                   .groupby(["order_id", "lineitem_id"], as_index=False)["option_price"].sum())
    lines = items.merge(opt_sum, on=["order_id", "lineitem_id"], how="left").fillna({"option_price": 0})
    lines["revenue"] = lines["item_price"] + lines["option_price"] * lines["item_quantity"]
    return lines


def summary(lines: pd.DataFrame) -> dict:
    customers = lines[(lines["user_id"] != "") & (lines["user_id"] != FAULTY_ACCOUNT)]["user_id"].nunique()
    return {"orders": lines["order_id"].nunique(),
            "revenue": round(lines["revenue"].sum(), 2),
            "customers": customers}


def main(raw_dir: str = "data/raw") -> dict:
    items, opts = load_raw(raw_dir)
    items = in_scope(add_business_date(items), "2023-01-01", "2023-12-31")
    return summary(line_revenue(items, opts))


if __name__ == "__main__":
    print(main())
```

(The unused `Decimal` import is deliberate: delete it if you prefer; in B4 you will switch money to exact decimals.)

## Check

```bash
python report.py
```

Expected (verified): `{'orders': 52015, 'revenue': 746223.86, 'customers': 10512}` (pandas may print `np.float64(746223.86)`).

## Why `assign` and not in-place edits

`df.assign(...)` returns a new DataFrame; the input is untouched. In-place edits create bugs that depend on call order. Pure functions never modify their arguments.

## Compare with the real project

The same functions exist, in Spark, as `transformations/cleaning.py`, `silver_order_items.py`, `gold_facts.py`. Open one and find the matching idea.

## Done when

`python report.py` gives the expected dictionary and each function fits on a screen.
