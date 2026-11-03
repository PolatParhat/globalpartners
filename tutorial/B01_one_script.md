# Stage B1: one script

**Goal:** a single `main.py` that reads the raw CSVs with pandas and prints the reference numbers.
**Why start here:** every real project begins as one messy script. You learn the problem first; structure comes when the mess hurts (B2).
**You type everything.** Create a new empty repo folder for the rebuild:

```bash
mkdir -p ~/globalpartners-rebuild/data && cd ~/globalpartners-rebuild
python3 -m venv .venv && source .venv/bin/activate && pip install pandas pytest pyyaml
ln -s "/Users/fulatipaerhati/Documents/DataEngineerBootcamp/Projects/globalpartners/data/raw" data/raw
git init -b main
```

(The symlink points at the immutable source CSVs: `order_items.csv`, `order_item_options.csv`, `date_dim.csv`. Raw files are never edited.)

## The data (look before you code)

```bash
head -n 2 data/raw/order_items.csv
head -n 2 data/raw/order_item_options.csv
wc -l data/raw/*.csv
```

`order_items` has one row per **order line** (`ORDER_ID`, `LINEITEM_ID`, `USER_ID`, `ITEM_PRICE`, `ITEM_QUANTITY`, `APP_NAME`, `CREATION_TIME_UTC`, …). `order_item_options` has one row per **option on a line** (`ORDER_ID`, `LINEITEM_ID`, `OPTION_PRICE`, `OPTION_QUANTITY`, …).

## The rules (from `config/business_rules.yaml`, SME decisions)

1. Scope: orders on business dates 2023-01-01 to 2023-12-31, where the business day is the **America/New_York** date of `creation_time_utc`.
2. Exclude the test app `Alltown Fresh - DEVELOPMENT`.
3. Line revenue = `item_price` (already the line total) + Σ `option_price` × `item_quantity` of that line.
4. Customers: exclude guests (empty `user_id`) and the faulty account `5ece77fe902ad501337b23fd`; sales keep them.

## Type this: `main.py`

```python
import pandas as pd

raw = "data/raw"
items = pd.read_csv(f"{raw}/order_items.csv", dtype=str, keep_default_na=False)
opts = pd.read_csv(f"{raw}/order_item_options.csv", dtype=str, keep_default_na=False)
items.columns = [c.lower() for c in items.columns]
opts.columns = [c.lower() for c in opts.columns]

items["item_price"] = pd.to_numeric(items["item_price"])
items["item_quantity"] = pd.to_numeric(items["item_quantity"])
opts["option_price"] = pd.to_numeric(opts["option_price"])

ts = pd.to_datetime(items["creation_time_utc"], format="ISO8601", utc=True)
items["business_date"] = ts.dt.tz_convert("America/New_York").dt.date
items = items[(items["business_date"] >= pd.Timestamp("2023-01-01").date())
              & (items["business_date"] <= pd.Timestamp("2023-12-31").date())]
items = items[items["app_name"] != "Alltown Fresh - DEVELOPMENT"]

opt_sum = opts.groupby(["order_id", "lineitem_id"], as_index=False)["option_price"].sum()
lines = items.merge(opt_sum, on=["order_id", "lineitem_id"], how="left")
lines["option_price"] = lines["option_price"].fillna(0)
lines["revenue"] = lines["item_price"] + lines["option_price"] * lines["item_quantity"]

faulty = "5ece77fe902ad501337b23fd"
customers = lines[(lines["user_id"] != "") & (lines["user_id"] != faulty)]["user_id"].nunique()

print("orders", lines["order_id"].nunique())
print("lines", len(lines))
print("revenue", round(lines["revenue"].sum(), 2))
print("item revenue", round(lines["item_price"].sum(), 2))
print("customers", customers)
```

Explain to yourself each choice: `dtype=str, keep_default_na=False` (read everything as text first, never let pandas guess types; empty stays empty), `format="ISO8601"` (explicit format; timestamps come both with and without fractions), `utc=True` then `tz_convert` (store UTC, convert for the business day), `how="left"` (lines without options must stay), `fillna(0)`.

## Check

```bash
python main.py
```

Expected (verified on the real data): **orders 52015 · lines 79965 · revenue 746223.86 · item revenue 711616.66 · customers 10512**.

Experiment: remove the faulty-account filter and see customers become 10513; remove the NY conversion (use UTC) and see which numbers move. Write one sentence on what you learned in `notes.md`, then commit:

```bash
git add main.py notes.md && git commit -m "B1: one script reproduces the reference numbers"
```

## Done when

The five numbers match and you can explain every line.
