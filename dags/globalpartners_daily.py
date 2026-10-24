"""GlobalPartners daily pipeline: replay → extract → silver → gold → data-quality checks.

One run per business day. The run's logical date is the business day being loaded, and its
run_id is passed to every job as --batch-id, so every row can be traced back to this run.

Local (PIPELINE_ENV=local): each step runs inside the project's Docker containers (docker exec).
AWS (PIPELINE_ENV=prod): the Spark steps run as AWS Glue jobs (added in Step 4.9).
"""
import os
from datetime import datetime, timedelta

from airflow.sdk import dag, task

PIPELINE_ENV = os.environ.get("PIPELINE_ENV", "local")
SPARK_CONTAINER = os.environ.get("SPARK_CONTAINER", "globalpartners-spark-1")
SQLSERVER_CONTAINER = os.environ.get("SQLSERVER_CONTAINER", "globalpartners-sqlserver-1")
SPARK_JOBS = ["extract_to_bronze", "bronze_to_silver", "silver_to_gold", "dq_checks"]


def run_in_container(container: str, command: list[str]) -> None:
    """Run a command inside a running container, stream its output into the task log, fail on a non-zero exit."""
    import docker

    api = docker.from_env().api
    exec_id = api.exec_create(container, command)["Id"]
    for chunk in api.exec_start(exec_id, stream=True):
        print(chunk.decode(errors="replace"), end="")
    exit_code = api.exec_inspect(exec_id)["ExitCode"]
    if exit_code != 0:
        raise RuntimeError(f"{' '.join(command[:3])}… in {container} exited with code {exit_code}")


@dag(
    dag_id="globalpartners_daily",
    schedule="0 6 * * *",                       # every day at 06:00
    start_date=datetime(2023, 1, 1),
    catchup=False,                              # past days are loaded on purpose (backfill), never by accident
    max_active_runs=1,                          # one business day at a time, in order
    default_args={"retries": 2, "retry_delay": timedelta(minutes=2)},
    tags=["globalpartners"],
)
def globalpartners_daily():

    @task
    def replay_day(ds=None):
        """Simulate the shops: copy the business day's orders into SQL Server's live tables."""
        if PIPELINE_ENV != "local":
            return
        sql = f"EXEC seed.replay_days '{ds}'"
        run_in_container(SQLSERVER_CONTAINER, [
            "sh", "-c",
            f'/opt/mssql-tools18/bin/sqlcmd -C -S localhost -U sa -P "$MSSQL_SA_PASSWORD" -d globalpartners -b -W -Q "{sql}"',
        ])

    def spark_job(job: str):
        @task(task_id=job)
        def run(run_id=None):
            if PIPELINE_ENV == "local":
                run_in_container(SPARK_CONTAINER, ["spark-submit", f"src/globalpartners/jobs/{job}.py", "--batch-id", run_id])
            else:
                raise NotImplementedError("AWS Glue jobs are wired up in Step 4.9")
        return run()

    steps = [replay_day()] + [spark_job(job) for job in SPARK_JOBS]
    for upstream, downstream in zip(steps, steps[1:]):
        upstream >> downstream


globalpartners_daily()