"""Command-line arguments that work both locally (spark-submit) and on AWS Glue.

Glue passes every job parameter as `--NAME value` and adds its own (--JOB_NAME, --job-bookmark-option, ...).
Parameters written in UPPER_CASE are copied into environment variables, so AWS settings reach the
code the same way as the Docker Compose variables do locally (e.g. --PIPELINE_ENV prod).
"""
import argparse
import os
import sys


def parse_job_args(parser: argparse.ArgumentParser, argv: list[str] | None = None) -> argparse.Namespace:
    argv = sys.argv[1:] if argv is None else argv
    for name, value in zip(argv, argv[1:]):
        key = name[2:]
        if name.startswith("--") and key.isupper() and not value.startswith("--"):
            os.environ.setdefault(key, value)
    args, _unknown = parser.parse_known_args(argv)      # ignore the parameters Glue adds
    return args
