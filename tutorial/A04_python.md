# Chapter A4: Python for this project

**Time:** 2 sessions. **Goal:** read and write the Python used in `src/globalpartners/` and write a small tested CLI that reads YAML and CSV.

```bash
mkdir ~/py-practice && cd ~/py-practice && python3 -m venv .venv && source .venv/bin/activate && pip install pyyaml pandas pytest
```

## 1. Environments and packages

- **Virtual environment (`venv`):** a private folder of installed packages for one project, so versions do not clash. `source .venv/bin/activate` turns it on (your prompt shows `(.venv)`); `deactivate` turns it off.
- **pip:** installs packages: `pip install pandas`, `pip install -r requirements.txt`, `pip freeze` lists installed versions. Pin versions in requirements files for repeatable builds.
- This project: `requirements.txt` (dashboard), `tests/requirements.txt` (CI), `infra/requirements*.txt`, and the Glue/MWAA images bring their own.

## 2. Modules, packages, imports

- A **module** is a `.py` file; a **package** is a folder with `__init__.py`.
- `import json` / `from pathlib import Path` / `from globalpartners.common import config`. The import path comes from `sys.path`; `PYTHONPATH` adds folders. (Our dashboard crashed on AWS with `ModuleNotFoundError` because Streamlit only added the script's own folder: fix `PYTHONPATH=/app`.)
- `if __name__ == "__main__":` runs code only when the file is executed, not when imported.

## 3. The standard library you will meet

| Module | Use | Example |
|---|---|---|
| `pathlib.Path` | file paths | `Path("config") / "environments.yaml"`, `.exists()`, `.read_text()`, `.mkdir(parents=True, exist_ok=True)`, `.glob("*.csv")` |
| `argparse` | command-line arguments | `p = argparse.ArgumentParser(); p.add_argument("--date", required=True); args = p.parse_args()` |
| `os` / `os.environ` | environment variables | `os.environ.get("PIPELINE_ENV", "local")` |
| `logging` | log messages with levels | `logging.getLogger(__name__).info("loaded %s rows", n)` |
| `datetime` | dates and times | `datetime.strptime("2023-01-01", "%Y-%m-%d")`, `timedelta(days=3)` |
| `json` | JSON text ↔ dict | `json.loads(text)`, `json.dumps(obj, indent=2)` |
| `shutil` | copy/delete trees | `shutil.copytree`, `shutil.rmtree` |
| `subprocess` | run other programs | `subprocess.run(["ls"], check=True, capture_output=True, text=True)` |
| `dataclasses` | simple data containers | `@dataclass(frozen=True) class Rule: name: str; days: int` |
| `typing` | type hints | `def f(x: int) -> list[str]:` |
| `decimal.Decimal` | exact money arithmetic | `Decimal("0.1") + Decimal("0.2") == Decimal("0.3")` |

Type hints do not change how code runs; they document and enable tools (mypy, editors).

## 4. Functions, data structures, errors

- **Pure function:** same inputs → same output, no side effects. This project's rule: transformations are pure; jobs do I/O. Pure functions are trivial to test.
- Data structures: `list` (ordered), `dict` (key → value), `set` (unique), `tuple` (fixed). Comprehensions: `[x*2 for x in xs if x > 0]`, `{k: v for k, v in pairs}`.
- **Exceptions:** `try: … except ValueError as e: … else: … finally: …`; `raise ValueError("bad date")`. Catch specific errors; let unexpected ones crash loudly. Never `except: pass`.
- **Context managers:** `with open(path) as f:` closes the file even on error.
- **Mutable default argument trap:** `def f(x=[])` shares one list; use `None`.

## 5. YAML and configuration

`config/environments.yaml` holds per-environment settings; `config/business_rules.yaml` holds rules.

```python
import yaml
from pathlib import Path
cfg = yaml.safe_load(Path("config/environments.yaml").read_text())
print(cfg["local"]["catalog"]["name"])        # lake
```

Use `safe_load` (never `load` on untrusted input). The project reads `${NAME}` placeholders from job parameters in `common/config.py`. **Principle:** same code, different config per environment (chapter A15).

## 6. pandas in 15 minutes

```python
import pandas as pd
df = pd.read_csv("orders.csv")                       # from chapter A1 sandbox
df["amount"].sum()
df[df["status"] == "done"].groupby("location")["amount"].sum()
df.sort_values("amount", ascending=False).head(3)
df.merge(other, on="key", how="left")
df.assign(gross=lambda d: d.amount * 1.1)
```

`df.dtypes`, `df.isna().sum()`, `df.describe()`. pandas is in-memory, single machine; the dashboard uses it for the final small results (`dashboard/logic.py`); Spark does the big work.

## 7. boto3 (AWS from Python)

```python
import boto3
athena = boto3.client("athena", region_name="us-east-1")
```

A **client** wraps one AWS service API; credentials come from the environment (profile, env vars, or the IAM role on AWS, never in code). `dashboard/data.py` starts an Athena query, polls until done, and reads the rows. Paginate list calls (`get_paginator`). Wrap AWS calls in `try/except botocore.exceptions.ClientError`.

## 8. Testing in Python (preview of chapter A9)

```python
# test_math.py
def total(xs): return sum(xs)
def test_total(): assert total([1, 2, 3]) == 6
```

Run `pytest`.

## 9. Style and tooling

PEP 8 naming (`snake_case` functions, `CapWords` classes, `UPPER_CASE` constants). Tools: `ruff` (lint + format), `mypy` (types), `pre-commit` (run both before every commit): chapter C2.

## 10. Exercise: a tiny tested CLI

Create `report.py` that:
1. takes `--csv orders.csv --config rules.yaml` (argparse),
2. reads `rules.yaml` containing `counted_status: done`,
3. prints the revenue by location for orders with that status (pandas),
4. has a pure function `revenue_by_location(df, status)` and a test with a 3-row DataFrame.

Expected output with the A1 sandbox data and `counted_status: done`: boston 50.5, cambridge 26.35, somerville 40.4 (same as Spark practice P1).

## 11. Read these project files (in order)

`src/globalpartners/common/job_args.py` → `config.py` → `credentials.py` → `source.py` → `tables.py` → `transformations/cleaning.py`. For each: what does it import, what goes in, what comes out, what could fail?

## Interview questions

1. List vs tuple vs set vs dict? 2. What is a decorator / generator / context manager? 3. `is` vs `==`? 4. What are `*args` and `**kwargs`? 5. How does Python manage memory (reference counting + GC)? 6. What is the GIL, and why does it matter for data engineering? (threads do not run Python bytecode in parallel; use processes or Spark) 7. Mutable default arguments? 8. How do you handle configuration and secrets? (YAML + env vars + secret manager, never in git) 9. How do you structure a Python project? 10. How do you make code testable? (pure functions, injected dependencies)

## Done when

Your CLI works, its test passes, and you can explain each import in `common/job_args.py`.
