import hashlib
import json
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  
RAW_DIR = PROJECT_ROOT / "data" / "raw"

EXPECTED = {
    "order_items": {
        "rows": 203_519,
        "columns": [
            "app_name", "restaurant_id", "creation_time_utc", "order_id", "user_id",
            "printed_card_number", "is_loyalty", "currency", "lineitem_id",
            "item_category", "item_name", "item_price", "item_quantity",
        ],
        "key": ["order_id", "lineitem_id"],
        "numeric": ["item_price", "item_quantity"],
        "timestamp": {"creation_time_utc": "ISO8601"},
    },
    "order_item_options": {
        "rows": 193_017,
        "columns": [
            "order_id", "lineitem_id", "option_group_name", "option_name",
            "option_price", "option_quantity",
        ],
        "key": None,
        "numeric": ["option_price", "option_quantity"],
        "timestamp": {},
    },
    "date_dim": {
        "rows": None,
        "columns": [
            "date_key", "day_of_week", "week", "month", "year",
            "is_weekend", "is_holiday", "holiday_name",
        ],
        "key": ["date_key"],
        "numeric": ["week", "year"],
        "timestamp": {"date_key": "%d-%m-%Y"},
    },
}


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()




def check_file(name: str, spec: dict) -> dict:
    path = RAW_DIR / f"{name}.csv"
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    df.columns = df.columns.str.strip().str.lower()
    report = {
        "file": path.name,
        "size_bytes": path.stat().st_size,
        "sha256": sha256_of(path),
        "row_count": len(df),
        "row_count_ok": spec["rows"] is None or len(df) == spec["rows"],
        "missing_columns": sorted(set(spec["columns"]) - set(df.columns)),
        "extra_columns": sorted(set(df.columns) - set(spec["columns"])),
        "blank_counts": {c: int((df[c].str.strip() == "").sum()) for c in df.columns},
        "fully_duplicate_rows": int(df.duplicated().sum()),
    }

    if spec["key"]:
        missing_keys = [k for k in spec["key"] if k not in df.columns]
        if missing_keys:
            report["duplicate_keys"] = f"skipped: key columns missing {missing_keys}"
        else:
            report["duplicate_keys"] = int(df.duplicated(subset=spec["key"]).sum())

    for col in spec["numeric"]:
        if col in df.columns:
            present = df[col][df[col].str.strip()!=""]
            parsed = pd.to_numeric(present, errors='coerce')
            report[f"unparseable_{col}"] = int(parsed.isna().sum())
    
    for col, fmt in spec["timestamp"].items():
      if col in df.columns:
        present = df[col][df[col].str.strip()!=""]
        parsed = pd.to_datetime(present, format=fmt, errors="coerce", utc=True)
        report[f"unparseable_{col}"] = int(parsed.isna().sum())
        report[f"range_{col}"] = [str(parsed.min()), str(parsed.max())]

    return report


if __name__ == "__main__":
    results = {name: check_file(name, spec) for name, spec in EXPECTED.items()}
    print(json.dumps(results, indent=2))
    report_path = PROJECT_ROOT / "docs" / "01_data_verification" / "integrity_report.json"
    report_path.write_text(json.dumps(results, indent=2))
    