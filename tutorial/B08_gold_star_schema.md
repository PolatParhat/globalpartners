# Stage B8: gold, the star schema

**Goal:** build facts and dimensions on Iceberg with MERGE. Prerequisites: A3 (grain), A7, A8, B7. Spec: `docs/03_architecture/Step3_Data_Model.md`.

## Design first: state the grain

| Table | One row per | Contents |
|---|---|---|
| `fact_order_line` | order line | keys, quantities, item revenue, option revenue, line revenue |
| `fact_order` | order | order revenue, line and item counts, business date, customer, flags |
| `dim_customer` | customer | id, loyalty flag |
| `dim_location` | restaurant | id (no names exist in the source) |
| `dim_item` | item | name, category |
| `dim_app` | app | name, test-data flag |
| `dim_date` | calendar day | from `date_dim` (weekend, holiday) |

**Two grains on purpose:** counting orders from the line table would count an order once per item.

## Steps

1. `transformations/gold_facts.py`: `fact_order_line` (line revenue = item price + Σ option price × quantity; business date in New York time) and `fact_order` (aggregate of the lines).
2. `transformations/gold_dimensions.py`: the five dimensions (rebuilt in full each run: they are small).
3. `jobs/silver_to_gold.py`: only the **affected orders** (added or changed in silver by the batch) are rebuilt and MERGEd into the facts; dimensions are rebuilt. Surrogate keys vs natural keys: this project uses the natural business ids.
4. Join the small dimensions by **broadcast**.
5. Tests: tiny silver inputs → exact fact rows (the revenue formula with options and quantity 2 is a must).

## Check

For the 3 replay days:

| | Value |
|---|---|
| `fact_order` rows | 289 |
| `fact_order_line` rows | 463 |
| Σ `fact_order.revenue` = Σ `fact_order_line.line_revenue` | $4,183.54 (1,078.19 + 1,424.16 + 1,681.19) |

After the full year: 52,015 in-scope orders and $746,223.86 (items $711,616.66 + options $34,607.20).
The revenue in orders, lines and every later aggregate **must be identical**; B10 turns that into a check.

## Compare with the real project

`transformations/gold_facts.py`, `gold_dimensions.py`, `jobs/silver_to_gold.py`, `tests/test_gold.py`.

## Done when

The totals agree between the two facts, a rerun changes nothing, and you can explain why two grains exist.
