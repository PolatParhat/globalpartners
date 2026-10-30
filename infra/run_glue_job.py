"""Start one of the project's Glue jobs and wait until it finishes (used by up.sh; handy by hand too).

    python run_glue_job.py setup_source
    python run_glue_job.py replay_day --date 2023-01-01
"""
import sys
import time

import boto3

from globalpartners_infra import names

FINISHED = {"SUCCEEDED", "FAILED", "TIMEOUT", "STOPPED", "ERROR"}


def run(job: str, arguments: dict[str, str] | None = None) -> str:
    glue = boto3.client("glue", region_name=names.REGION)
    name = f"{names.GLUE_JOB_PREFIX}{job}"
    run_id = glue.start_job_run(JobName=name, Arguments=arguments or {})["JobRunId"]
    print(f"{name}: started run {run_id}")
    started = time.time()
    while True:
        time.sleep(20)
        job_run = glue.get_job_run(JobName=name, RunId=run_id)["JobRun"]
        state = job_run["JobRunState"]
        print(f"  {int(time.time() - started):>4}s  {state}")
        if state in FINISHED:
            break
    if state != "SUCCEEDED":
        print(f"  error: {job_run.get('ErrorMessage', '-')}")
        print(f"  logs:  https://{names.REGION}.console.aws.amazon.com/gluestudio/home?region={names.REGION}"
              f"#/job/{name}/run/{run_id}")
    return state


if __name__ == "__main__":
    job, pairs = sys.argv[1], sys.argv[2:]
    arguments = dict(zip(pairs[::2], pairs[1::2]))
    sys.exit(0 if run(job, arguments) == "SUCCEEDED" else 1)
