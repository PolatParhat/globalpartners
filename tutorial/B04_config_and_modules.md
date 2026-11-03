# Stage B4: configuration and the package layout

**Goal:** move rules out of code into YAML, and move code into the project's package structure. Numbers must not change.
**Prerequisites:** B1 to B3, chapters A4 and A15.

## Why

Hard-coded rules (`"Alltown Fresh - DEVELOPMENT"`, the faulty account, the time zone) are business decisions that change when the SME answers a question. They belong in one file that analysts can read, so a rule change is a settings change, not a code change.

## Steps

1. **Create the layout** (empty files for now):

```
globalpartners-rebuild/
├── config/ business_rules.yaml · environments.yaml
├── src/globalpartners/__init__.py
├── src/globalpartners/common/__init__.py · config.py
├── src/globalpartners/transformations/__init__.py · cleaning.py · gold_facts.py
├── tests/ conftest.py · test_cleaning.py · test_config.py
└── pytest.ini
```

2. **`config/business_rules.yaml`:** type the rules you used in B1: reporting dates, `business_timezone`, `excluded_apps`, `non_customer_ids`, `option_price_times_item_quantity: true`. Add a comment naming each rule's source (SME answer or assumption). Compare with the project's file only after you finish.
3. **`config/environments.yaml`:** a `local:` section with `raw_dir` (for now). Later stages add the Spark catalog and database.
4. **`common/config.py`:** two functions, `load_business_rules()` and `load_environment()`, using `yaml.safe_load(Path(...).read_text())`. `load_environment` reads `PIPELINE_ENV` (default `local`) and returns that section.
5. **Move the functions** from `report.py` into `transformations/` modules (cleaning, revenue) and make them take the rules as a parameter instead of using constants.
6. **`pytest.ini`:** `pythonpath = src` and `testpaths = tests` so `import globalpartners…` works.
7. **Update the tests** to import from the package; add `test_config.py` (the YAML loads and has the expected keys).

## Check

```bash
pytest -q
python -c "from globalpartners.common.config import load_business_rules as r; print(r()['reporting_scope'])"
```

Expected: tests green; the summary numbers from B2 unchanged (52,015 orders, $746,223.86, 10,512 customers).

## Compare with the real project

`config/business_rules.yaml`, `config/environments.yaml`, `src/globalpartners/common/config.py`, `tests/test_config.py`. Note that the real rules file also holds the CLV tiers, RFM bands and churn thresholds, which you add in B9.

## Done when

No business constant remains in Python code; changing the excluded app in YAML changes the result.
