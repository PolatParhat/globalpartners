"""ops.pipeline_runs: one row per job run (when, status, row counts, error)."""
from contextlib import contextmanager
from datetime import datetime, timezone

from pyspark.sql import SparkSession

COLUMNS = ("run_id string, job string, started_at timestamp, finished_at timestamp, status string, "
           "rows_in long, rows_out long, rows_quarantined long, error string")


@contextmanager
def logged_run(spark: SparkSession, lake: str, job: str, run_id: str):
    """Wrap a job's work: a row is written to ops.pipeline_runs whether the work succeeds or fails.

    The job fills in the counts:  with logged_run(...) as run:  run["rows_in"] = ...
    """
    run = {"rows_in": None, "rows_out": None, "rows_quarantined": None}
    started_at = datetime.now(timezone.utc)
    status, error = "SUCCESS", None
    try:
        yield run
    except Exception as exc:
        status, error = "FAILED", f"{type(exc).__name__}: {exc}"[:2000]
        raise                                   # the job still fails; we only record it first
    finally:
        try:
            table = f"{lake}.ops.pipeline_runs"
            spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {lake}.ops")
            spark.sql(f"CREATE TABLE IF NOT EXISTS {table} ({COLUMNS}) USING iceberg")
            row = (run_id, job, started_at, datetime.now(timezone.utc), status,
                   run["rows_in"], run["rows_out"], run["rows_quarantined"], error)
            spark.createDataFrame([row], COLUMNS).writeTo(table).append()
            print(f"run log: {job} {run_id} {status}")
        except Exception as log_error:          # never hide the job's own error behind a logging error
            print(f"run log could not be written: {log_error}")