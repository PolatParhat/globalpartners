"""GlobalPartners daily pipeline: replay → extract → silver → gold → data-quality checks.

One run per business day. The run's logical date is the business day being loaded, and its
run_id is passed to every job as --batch-id, so every row can be traced back to this run.

Local (PIPELINE_ENV=local): each step runs inside the project's Docker containers (docker exec).
AWS (prod, from the MWAA configuration option globalpartners.pipeline_env, which MWAA passes as the
environment variable AIRFLOW__GLOBALPARTNERS__PIPELINE_ENV): each step starts the AWS Glue job of the
same name (globalpartners-<step>, created by the CDK PipelineStack) and waits for it.
"""
import os
from datetime import datetime, timedelta

from airflow.sdk import dag, task

PIPELINE_ENV = os.environ.get("PIPELINE_ENV") or os.environ.get("AIRFLOW__GLOBALPARTNERS__PIPELINE_ENV", "local")
SPARK_CONTAINER = os.environ.get("SPARK_CONTAINER", "globalpartners-spark-1")
SQLSERVER_CONTAINER = os.environ.get("SQLSERVER_CONTAINER", "globalpartners-sqlserver-1")
SPARK_JOBS = ["extract_to_bronze", "bronze_to_silver", "silver_to_gold", "dq_checks"]
GLUE_JOB_PREFIX = os.environ.get("GLUE_JOB_PREFIX", "globalpartners-")


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
        sql = f"EXEC seed.replay_days '{ds}'"
        run_in_container(SQLSERVER_CONTAINER, [
            "sh", "-c",
            f'/opt/mssql-tools18/bin/sqlcmd -C -S localhost -U sa -P "$MSSQL_SA_PASSWORD" -d globalpartners -b -W -Q "{sql}"',
        ])

    def spark_job(job: str):
        @task(task_id=job)
        def run(run_id=None):
            run_in_container(SPARK_CONTAINER, ["spark-submit", f"src/globalpartners/jobs/{job}.py", "--batch-id", run_id])
        return run()

    def glue_job(job: str, script_args: dict):
        from airflow.providers.amazon.aws.operators.glue import GlueJobOperator
        return GlueJobOperator(
            task_id=job,
            job_name=f"{GLUE_JOB_PREFIX}{job}",
            script_args=script_args,                # templated: {{ ds }} and {{ run_id }} are filled in per run
            wait_for_completion=True,
            verbose=True,                           # copy the Glue job's log lines into the Airflow task log
            stop_job_run_on_kill=True,
        )

    if PIPELINE_ENV == "local":
        steps = [replay_day()] + [spark_job(job) for job in SPARK_JOBS]
    else:
        steps = ([glue_job("replay_day", {"--date": "{{ ds }}"})]
                 + [glue_job(job, {"--batch-id": "{{ run_id }}"}) for job in SPARK_JOBS])
    for upstream, downstream in zip(steps, steps[1:]):
        upstream >> downstream


globalpartners_daily()