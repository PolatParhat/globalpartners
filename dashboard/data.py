"""Data access: one function, `query(sql) -> DataFrame`, two engines.

    PIPELINE_ENV=local (default)  Spark SQL on the local Iceberg lake (same Glue 5.1 image as the pipeline)
    PIPELINE_ENV=prod             Amazon Athena on the Glue catalog (the dashboard container on ECS Fargate)

The pages never know which engine answered. Results are cached for an hour (st.cache_data), because Streamlit
re-runs a page's script on every click and the gold tables change at most once a day.
"""
import datetime
import io
import os
import time
from decimal import Decimal

import pandas as pd
import streamlit as st

REGION = os.environ.get("AWS_REGION", "us-east-1")
ATHENA_WORKGROUP = os.environ.get("ATHENA_WORKGROUP", "globalpartners")
ATHENA_DATABASE = "gold"
CACHE_SECONDS = 3600


def engine() -> str:
    return "athena" if os.environ.get("PIPELINE_ENV", "local") == "prod" else "spark"


@st.cache_data(ttl=CACHE_SECONDS, show_spinner="Querying the lake…")
def query(sql: str) -> pd.DataFrame:
    """Run a SELECT on the gold tables and return the result as a DataFrame."""
    return _execute(sql)


def _execute(sql: str) -> pd.DataFrame:
    return _run_athena(sql) if engine() == "athena" else _run_spark(sql)


# ---------------------------------------------------------------- local: Spark
@st.cache_resource
def _spark():
    """One SparkSession for the whole dashboard process (starting Spark takes a few seconds)."""
    from globalpartners.common.config import load_environment    # imported here: the AWS image has no pyspark
    from globalpartners.common.spark import build_spark

    env = load_environment()
    warehouse = os.environ.get("DASHBOARD_WAREHOUSE")             # e.g. the full-year demo lake
    if warehouse:
        env["catalog"]["warehouse"] = warehouse
    # in-memory default catalog: the Glue image's default one is Hive-backed and wants AWS credentials; we only use Iceberg
    spark = build_spark("dashboard", env, extra_conf={"spark.sql.catalogImplementation": "in-memory"})
    spark.sparkContext.setLogLevel("ERROR")
    spark.conf.set("spark.sql.shuffle.partitions", "8")           # small data: 200 partitions would only add overhead
    # Point Spark at the gold database, so `FROM sales_daily` means lake.gold.sales_daily, as in Athena (Database=gold).
    spark.sql(f"SET CATALOG {env['catalog']['name']}")
    spark.sql("USE gold")
    return spark


def _run_spark(sql: str) -> pd.DataFrame:
    return normalize(_spark().sql(sql).toPandas())


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Spark hands back Decimal and date objects; the pages want floats and datetimes."""
    df = df.copy()
    for column in df.columns:
        series = df[column]
        if series.dtype != object or not series.notna().any():
            continue
        first = series.dropna().iloc[0]
        if isinstance(first, Decimal):
            df[column] = series.astype(float)
        elif isinstance(first, datetime.date):
            df[column] = pd.to_datetime(series)
    return df


# ---------------------------------------------------------------- AWS: Athena
def _run_athena(sql: str) -> pd.DataFrame:
    import boto3                                                   # imported here: not needed locally

    athena = boto3.client("athena", region_name=REGION)
    query_id = athena.start_query_execution(
        QueryString=sql, WorkGroup=ATHENA_WORKGROUP,
        QueryExecutionContext={"Database": ATHENA_DATABASE})["QueryExecutionId"]
    while True:
        execution = athena.get_query_execution(QueryExecutionId=query_id)["QueryExecution"]
        state = execution["Status"]["State"]
        if state in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
        time.sleep(0.4)
    if state != "SUCCEEDED":
        raise RuntimeError(f"Athena query {state}: {execution['Status'].get('StateChangeReason', 'no reason given')}")

    # Athena always writes the full result as one CSV in S3: much faster than paging through get_query_results.
    types = [c["Type"] for c in athena.get_query_results(QueryExecutionId=query_id, MaxResults=1)
             ["ResultSet"]["ResultSetMetadata"]["ColumnInfo"]]
    bucket, key = execution["ResultConfiguration"]["OutputLocation"].removeprefix("s3://").split("/", 1)
    body = boto3.client("s3", region_name=REGION).get_object(Bucket=bucket, Key=key)["Body"].read()
    raw = pd.read_csv(io.BytesIO(body), dtype=str, keep_default_na=False, na_values=[""])
    return convert_athena(raw, types)


def convert_athena(raw: pd.DataFrame, types: list[str]) -> pd.DataFrame:
    """Athena's CSV is all text: turn each column into the type Athena reported for it."""
    df = raw.copy()
    for column, athena_type in zip(df.columns, types):
        if athena_type in ("tinyint", "smallint", "integer", "bigint", "double", "float", "real", "decimal"):
            df[column] = pd.to_numeric(df[column])
        elif athena_type in ("date", "timestamp"):
            df[column] = pd.to_datetime(df[column])
        elif athena_type == "boolean":
            df[column] = df[column].map({"true": True, "false": False})
    return df


# ---------------------------------------------------------------- shared helpers used by the pages
def snapshot_range() -> tuple[datetime.date, datetime.date]:
    """First and last day in gold.customer_daily_snapshot."""
    from dashboard import queries
    row = query(queries.SNAPSHOT_RANGE).iloc[0]
    return row["first_day"].date(), row["last_day"].date()
