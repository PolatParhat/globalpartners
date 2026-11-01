"""Dashboard data access (dashboard/data.py, queries.py): type conversion, the Athena path, SQL safety."""
import datetime
import io
import sys
import types
from decimal import Decimal

import pandas as pd
import pytest

from dashboard import data, queries


# ---------------------------------------------------------------- queries
def test_day_makes_a_sql_date_literal():
    assert queries.day(datetime.date(2023, 12, 31)) == "DATE '2023-12-31'"


def test_day_refuses_text_so_no_sql_can_be_smuggled_in():
    with pytest.raises(TypeError):
        queries.day("2023-01-01'; DROP TABLE gold.sales_daily; --")


def test_every_query_reads_only_gold_tables_and_never_writes():
    day = datetime.date(2023, 5, 1)
    texts = [queries.SALES_DAILY, queries.SALES_CATEGORY, queries.LOCATION_SUMMARY, queries.SNAPSHOT_RANGE,
             queries.SEGMENTS_OVER_TIME, queries.customer_cube(day), queries.churn_bands(day), queries.at_risk_customers(day)]
    for sql in texts:
        upper = sql.upper()
        assert upper.lstrip().startswith("SELECT") and "FROM " in upper and "GOLD." not in upper
        assert not any(word in upper for word in ("INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER"))


def test_at_risk_limit_must_be_a_number():
    with pytest.raises(ValueError):
        queries.at_risk_customers(datetime.date(2023, 5, 1), limit="5; DROP")


# ---------------------------------------------------------------- Spark results
def test_normalize_turns_decimals_and_dates_into_floats_and_datetimes():
    raw = pd.DataFrame({"revenue": [Decimal("10.50"), None], "business_date": [datetime.date(2023, 1, 2), datetime.date(2023, 1, 3)],
                        "name": ["a", "b"], "orders": [1, 2]}, dtype=object)
    raw["orders"] = raw["orders"].astype("int64")
    out = data.normalize(raw)
    assert out["revenue"].dtype == "float64" and out["revenue"].iloc[0] == 10.5 and pd.isna(out["revenue"].iloc[1])
    assert str(out["business_date"].dtype).startswith("datetime64")
    assert out["name"].tolist() == ["a", "b"] and out["orders"].dtype == "int64"


def test_normalize_leaves_empty_and_text_columns_alone():
    out = data.normalize(pd.DataFrame({"x": pd.Series([None, None], dtype=object)}))
    assert out["x"].isna().all()


# ---------------------------------------------------------------- Athena results
def test_convert_athena_uses_the_types_athena_reported():
    raw = pd.DataFrame({"d": ["2023-01-02"], "n": ["5"], "money": ["12.30"], "flag": ["true"], "text": ["x"]}, dtype=str)
    out = data.convert_athena(raw, ["date", "bigint", "decimal", "boolean", "varchar"])
    assert out["d"].iloc[0] == pd.Timestamp("2023-01-02") and out["n"].iloc[0] == 5
    assert out["money"].iloc[0] == 12.3 and out["flag"].iloc[0] is True or out["flag"].iloc[0] == True  # noqa: E712
    assert out["text"].iloc[0] == "x"


class FakeAthena:
    def __init__(self, states, csv, types_, calls):
        self.states, self.csv, self.types, self.calls = list(states), csv, types_, calls

    def start_query_execution(self, **kwargs):
        self.calls.append(kwargs)
        return {"QueryExecutionId": "q-1"}

    def get_query_execution(self, QueryExecutionId):
        state = self.states.pop(0) if len(self.states) > 1 else self.states[0]
        return {"QueryExecution": {"Status": {"State": state, "StateChangeReason": "boom"},
                                   "ResultConfiguration": {"OutputLocation": "s3://lake-bucket/athena-results/q-1.csv"}}}

    def get_query_results(self, QueryExecutionId, MaxResults):
        return {"ResultSet": {"ResultSetMetadata": {"ColumnInfo": [{"Type": t} for t in self.types]}}}


class FakeS3:
    def __init__(self, csv, calls):
        self.csv, self.calls = csv, calls

    def get_object(self, Bucket, Key):
        self.calls.append((Bucket, Key))
        return {"Body": io.BytesIO(self.csv.encode())}


@pytest.fixture
def fake_boto3(monkeypatch):
    calls = {"athena": [], "s3": []}
    holder = {"states": ["RUNNING", "SUCCEEDED"], "csv": "business_date,orders\n2023-01-02,5\n2023-01-03,\n", "types": ["date", "bigint"]}

    def client(name, region_name=None):
        if name == "athena":
            return FakeAthena(holder["states"], holder["csv"], holder["types"], calls["athena"])
        return FakeS3(holder["csv"], calls["s3"])

    monkeypatch.setitem(sys.modules, "boto3", types.SimpleNamespace(client=client))
    monkeypatch.setattr(data.time, "sleep", lambda s: None)
    return holder, calls


def test_athena_path_runs_the_query_in_the_workgroup_and_reads_the_csv_from_s3(fake_boto3):
    holder, calls = fake_boto3
    out = data._run_athena("SELECT 1")
    assert calls["athena"] == [{"QueryString": "SELECT 1", "WorkGroup": data.ATHENA_WORKGROUP,
                                "QueryExecutionContext": {"Database": "gold"}}]
    assert calls["s3"] == [("lake-bucket", "athena-results/q-1.csv")]
    assert out["orders"].iloc[0] == 5 and pd.isna(out["orders"].iloc[1])        # an empty cell is a missing value
    assert out["business_date"].iloc[1] == pd.Timestamp("2023-01-03")


def test_athena_failure_raises_with_the_reason(fake_boto3):
    holder, _ = fake_boto3
    holder["states"] = ["FAILED"]
    with pytest.raises(RuntimeError, match="FAILED: boom"):
        data._run_athena("SELECT 1")


def test_engine_follows_pipeline_env(monkeypatch):
    monkeypatch.setenv("PIPELINE_ENV", "prod")
    assert data.engine() == "athena"
    monkeypatch.setenv("PIPELINE_ENV", "local")
    assert data.engine() == "spark"
    monkeypatch.delenv("PIPELINE_ENV")
    assert data.engine() == "spark"
