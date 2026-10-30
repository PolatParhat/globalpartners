"""Helpers that let the same jobs run locally and on AWS Glue: arguments, config, logins, SQL scripts."""
import argparse
import json
import sys
import types

import pytest

from globalpartners.common import config
from globalpartners.common.credentials import login
from globalpartners.common.job_args import parse_job_args
from globalpartners.common.sqlserver import split_batches

PROD_VARIABLES = ["LAKE_BUCKET", "SOURCE_DB_HOST", "SOURCE_ADMIN_SECRET", "SOURCE_READER_SECRET"]


def test_glue_parameters_become_environment_variables(monkeypatch):
    monkeypatch.delenv("PIPELINE_ENV", raising=False)
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-id")
    # what AWS Glue passes: its own parameters, ours in UPPER_CASE, and the job's own argument
    args = parse_job_args(parser, ["--JOB_NAME", "globalpartners-extract_to_bronze",
                                   "--job-bookmark-option", "job-bookmark-disable",
                                   "--PIPELINE_ENV", "prod", "--batch-id", "run-1"])
    assert args.batch_id == "run-1"
    assert config.pipeline_env() == "prod"


def test_existing_environment_variables_win(monkeypatch):
    monkeypatch.setenv("PIPELINE_ENV", "local")
    parse_job_args(argparse.ArgumentParser(), ["--PIPELINE_ENV", "prod"])
    assert config.pipeline_env() == "local"


def test_prod_settings_are_filled_from_environment_variables(monkeypatch):
    for name in PROD_VARIABLES:
        monkeypatch.setenv(name, f"<{name}>")
    env = config.load_environment("prod")
    assert env["catalog"]["warehouse"] == "s3://<LAKE_BUCKET>/lake"
    assert env["raw_dir"] == "s3://<LAKE_BUCKET>/raw"
    assert env["source_db"]["host"] == "<SOURCE_DB_HOST>"
    assert env["source_db"]["reader_secret"] == "<SOURCE_READER_SECRET>"


def test_missing_prod_variable_fails_with_a_clear_error(monkeypatch):
    for name in PROD_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(KeyError, match="environment variable missing"):
        config.load_environment("prod")


def test_local_login_comes_from_environment_variables(monkeypatch):
    monkeypatch.setenv("MSSQL_ETL_USER", "etl_reader")
    monkeypatch.setenv("MSSQL_ETL_PASSWORD", "reader-pw")
    monkeypatch.setenv("MSSQL_USER", "sa")
    monkeypatch.setenv("MSSQL_SA_PASSWORD", "admin-pw")
    db = config.load_environment("local")["source_db"]
    assert login(db) == ("etl_reader", "reader-pw")
    assert login(db, admin=True) == ("sa", "admin-pw")


def test_prod_login_comes_from_secrets_manager(monkeypatch):
    class FakeSecretsManager:
        def get_secret_value(self, SecretId):
            return {"SecretString": json.dumps({"username": f"user-of-{SecretId}", "password": "pw"})}
    monkeypatch.setitem(sys.modules, "boto3", types.SimpleNamespace(client=lambda service: FakeSecretsManager()))
    db = {"admin_secret": "gp/admin", "reader_secret": "gp/reader"}
    assert login(db) == ("user-of-gp/reader", "pw")
    assert login(db, admin=True) == ("user-of-gp/admin", "pw")


def test_sql_scripts_split_on_go_lines_like_sqlcmd():
    batches = split_batches(config.project_file("sql/03_replay_procedure.sql").read_text())
    assert batches[0].endswith("USE globalpartners;")                         # header comments + USE
    assert batches[1].startswith("CREATE OR ALTER PROCEDURE seed.replay_days")   # must start its own batch
    assert all("\nGO" not in batch for batch in batches)
