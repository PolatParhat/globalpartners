from pathlib import Path
import pandas as pd

RAW_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "raw"

def show_failures(file_name:str, column: str) -> None:
  df = pd.read_csv(RAW_DIR / file_name, dtype=str, keep_default_na=False)
  df.columns = df.columns.str.strip().str.lower()
  values = df[column]
  
  parsed = pd.to_datetime(values, errors='coerce', utc=True)
  failed = values[parsed.isna()]
  print(f"\n=== {file_name} / {column} ===")
  print("first 3 values :", values.head(3).tolist())
  print("failed count   :", len(failed))
  print("failed samples :", failed.head(5).tolist())

show_failures("order_items.csv", "creation_time_utc")
show_failures("date_dim.csv", "date_key")