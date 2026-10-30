"""Infrastructure rules, checked on the synthesized CloudFormation templates (nothing is deployed)."""
import zipfile

import pytest
from aws_cdk.assertions import Match, Template

from app import build_app
from globalpartners_infra import artifacts, names


@pytest.fixture(scope="module")
def templates():
    app = build_app(account="123456789012")
    return {stack.stack_name: Template.from_stack(stack) for stack in app.node.children if hasattr(stack, "stack_name")}


@pytest.fixture(scope="module")
def data(templates):
    return templates[names.DATA_STACK]


@pytest.fixture(scope="module")
def pipeline(templates):
    return templates[names.PIPELINE_STACK]


def test_nothing_survives_a_delete(templates):
    """down.sh must leave nothing behind: no resource may be retained or snapshotted."""
    for template in templates.values():
        for logical_id, resource in template.to_json()["Resources"].items():
            assert resource.get("DeletionPolicy", "Delete") == "Delete", logical_id
            assert resource.get("UpdateReplacePolicy", "Delete") == "Delete", logical_id


def test_buckets_are_private_encrypted_and_emptied_on_delete(data):
    data.resource_count_is("AWS::S3::Bucket", 2)
    data.resource_count_is("Custom::S3AutoDeleteObjects", 2)
    data.has_resource_properties("AWS::S3::Bucket", {
        "BucketName": f"globalpartners-lake-123456789012-{names.REGION}",
        "BucketEncryption": {"ServerSideEncryptionConfiguration": [
            Match.object_like({"ServerSideEncryptionByDefault": Match.object_like({"SSEAlgorithm": "aws:kms"})})]},
        "PublicAccessBlockConfiguration": {"BlockPublicAcls": True, "BlockPublicPolicy": True,
                                           "IgnorePublicAcls": True, "RestrictPublicBuckets": True},
    })
    data.has_resource_properties("AWS::S3::Bucket", {   # MWAA requires a versioned DAG bucket
        "BucketName": f"globalpartners-artifacts-123456789012-{names.REGION}",
        "VersioningConfiguration": {"Status": "Enabled"},
    })


def test_glue_catalog_has_one_database_per_layer(data):
    for layer in names.GLUE_DATABASES:
        data.has_resource_properties("AWS::Glue::Database", {"DatabaseInput": Match.object_like({"Name": layer})})


def test_source_database_is_small_private_and_deletable(pipeline):
    pipeline.has_resource_properties("AWS::RDS::DBInstance", {
        "Engine": "sqlserver-ex",
        "DBInstanceClass": "db.t3.micro",
        "LicenseModel": "license-included",
        "PubliclyAccessible": False,
        "StorageEncrypted": True,
        "BackupRetentionPeriod": 0,
        "DeletionProtection": False,
        "MultiAZ": False,
    })


def test_one_glue_job_per_pipeline_step(pipeline):
    pipeline.resource_count_is("AWS::Glue::Job", len(names.GLUE_JOBS))
    for job in names.GLUE_JOBS:
        pipeline.has_resource_properties("AWS::Glue::Job", {
            "Name": f"globalpartners-{job}",
            "GlueVersion": "5.1",
            "WorkerType": "G.1X",
            "NumberOfWorkers": 2,
            "ExecutionClass": "STANDARD",
            "MaxRetries": 0,
            "Connections": {"Connections": ["globalpartners-vpc"]},
            "DefaultArguments": Match.object_like({
                "--datalake-formats": "iceberg",
                "--additional-python-modules": "PyYAML==6.0.3",
                "--PIPELINE_ENV": "prod",
                "--SOURCE_ADMIN_SECRET": names.ADMIN_SECRET,
                "--SOURCE_READER_SECRET": names.READER_SECRET,
            }),
        })


def test_glue_execution_class_can_be_switched_to_flex():
    from aws_cdk import App
    from globalpartners_infra.data_stack import DataStack
    from globalpartners_infra.pipeline_stack import PipelineStack
    app = App()
    data = DataStack(app, "D")
    stack = PipelineStack(app, "P", lake=data.lake, artifacts_bucket=data.artifacts, glue_execution_class="FLEX")
    Template.from_stack(stack).has_resource_properties("AWS::Glue::Job", {"ExecutionClass": "FLEX"})


def test_airflow_is_the_micro_class_on_the_local_version(pipeline):
    pipeline.has_resource_properties("AWS::MWAA::Environment", {
        "Name": names.MWAA_ENVIRONMENT,
        "AirflowVersion": "3.3.1",
        "EnvironmentClass": "mw1.micro",
        "DagS3Path": "mwaa/dags",
        "WebserverAccessMode": "PUBLIC_ONLY",
        "AirflowConfigurationOptions": {"globalpartners.pipeline_env": "prod"},
        "Tags": Match.object_like({"project": "globalpartners"}),
    })


def test_failed_glue_jobs_send_an_alert(pipeline):
    pipeline.has_resource_properties("AWS::Events::Rule", {
        "EventPattern": Match.object_like({"source": ["aws.glue"],
                                           "detail": {"jobName": [{"prefix": "globalpartners-"}],
                                                      "state": ["FAILED", "TIMEOUT", "ERROR"]}}),
    })


def test_alert_email_is_optional():
    from aws_cdk import App
    from globalpartners_infra.data_stack import DataStack
    from globalpartners_infra.pipeline_stack import PipelineStack
    app = App()
    data = DataStack(app, "D")
    stack = PipelineStack(app, "P", lake=data.lake, artifacts_bucket=data.artifacts, alert_email="me@example.com")
    Template.from_stack(stack).has_resource_properties("AWS::SNS::Subscription",
                                                       {"Protocol": "email", "Endpoint": "me@example.com"})


def test_build_folder_has_the_code_glue_and_mwaa_need():
    files = artifacts.build(names.GLUE_JOBS)
    with zipfile.ZipFile(files["glue"] / "globalpartners.zip") as z:
        members = z.namelist()
    assert "globalpartners/common/config.py" in members
    assert not any("__pycache__" in m for m in members)
    assert sorted(p.stem for p in (files["glue"] / "jobs").iterdir()) == sorted(names.GLUE_JOBS)
    assert {p.name for p in (files["glue"] / "files").iterdir()} == {
        "environments.yaml", "business_rules.yaml",
        "01_create_database.sql", "02_create_tables.sql", "03_replay_procedure.sql"}
    assert (files["mwaa"] / "dags" / "globalpartners_daily.py").exists()


def test_package_zip_is_identical_when_nothing_changed(tmp_path):
    """Fixed timestamps: an unchanged package must not look new to CDK (no needless upload)."""
    a, b = tmp_path / "a.zip", tmp_path / "b.zip"
    artifacts.zip_package(artifacts.ROOT / "src" / "globalpartners", a)
    artifacts.zip_package(artifacts.ROOT / "src" / "globalpartners", b)
    assert a.read_bytes() == b.read_bytes()
