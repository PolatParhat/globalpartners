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


def test_every_airflow_log_module_has_a_log_level(pipeline):
    # MWAA rejects a module without LogLevel, even a disabled one (first deploy failed on this).
    env = next(iter(pipeline.find_resources("AWS::MWAA::Environment").values()))
    modules = env["Properties"]["LoggingConfiguration"]
    assert set(modules) == {"TaskLogs", "SchedulerLogs", "DagProcessingLogs", "WebserverLogs", "WorkerLogs"}
    for name, module in modules.items():
        assert module.get("LogLevel") in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}, name


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


# ---------------------------------------------------------------- Step 6: dashboard (Streamlit on Fargate behind an ALB)
def test_dashboard_runs_one_arm_task_in_a_private_subnet_without_a_public_ip(pipeline):
    pipeline.has_resource_properties("AWS::ECS::Service", {
        "ServiceName": names.DASHBOARD_SERVICE,
        "LaunchType": "FARGATE",
        "DesiredCount": 1,
        "NetworkConfiguration": {"AwsvpcConfiguration": Match.object_like({"AssignPublicIp": "DISABLED"})},
        "DeploymentConfiguration": Match.object_like({"DeploymentCircuitBreaker": {"Enable": True, "Rollback": True},
                                                      "MinimumHealthyPercent": 100}),
    })
    pipeline.has_resource_properties("AWS::ECS::TaskDefinition", {
        "Cpu": "512", "Memory": "1024",
        "RuntimePlatform": {"CpuArchitecture": "ARM64", "OperatingSystemFamily": "LINUX"},
        "ContainerDefinitions": [Match.object_like({
            "PortMappings": [Match.object_like({"ContainerPort": names.DASHBOARD_PORT})],
            "Environment": Match.array_with([{"Name": "PIPELINE_ENV", "Value": "prod"},
                                             {"Name": "ATHENA_WORKGROUP", "Value": names.ATHENA_WORKGROUP}]),
            "LogConfiguration": Match.object_like({"LogDriver": "awslogs"}),
        })],
    })


def test_load_balancer_checks_streamlits_health_endpoint(pipeline):
    pipeline.has_resource_properties("AWS::ElasticLoadBalancingV2::LoadBalancer", {"Scheme": "internet-facing"})
    pipeline.has_resource_properties("AWS::ElasticLoadBalancingV2::TargetGroup", {
        "HealthCheckPath": "/_stcore/health", "TargetType": "ip", "Matcher": {"HttpCode": "200"}})
    pipeline.has_resource_properties("AWS::ElasticLoadBalancingV2::Listener", {"Port": 80, "Protocol": "HTTP"})


def test_only_the_allowed_address_can_open_the_dashboard(pipeline):
    """By default nobody (127.0.0.1/32); the world (0.0.0.0/0) must never be the default."""
    load_balancer_sg = [r for r in pipeline.find_resources("AWS::EC2::SecurityGroup").values()
                        if "Who may open the dashboard" in str(r["Properties"].get("SecurityGroupIngress"))]
    assert len(load_balancer_sg) == 1
    ingress = load_balancer_sg[0]["Properties"]["SecurityGroupIngress"]
    assert [(rule["CidrIp"], rule["FromPort"], rule["ToPort"]) for rule in ingress] == [("127.0.0.1/32", 80, 80)]


def test_dashboard_address_can_be_set():
    from aws_cdk import App
    from globalpartners_infra.data_stack import DataStack
    from globalpartners_infra.pipeline_stack import PipelineStack
    app = App()
    data_stack = DataStack(app, "D")
    stack = PipelineStack(app, "P", lake=data_stack.lake, artifacts_bucket=data_stack.artifacts, dashboard_cidr="203.0.113.7/32")
    Template.from_stack(stack).has_resource_properties("AWS::EC2::SecurityGroup", {
        "SecurityGroupIngress": [Match.object_like({"CidrIp": "203.0.113.7/32", "FromPort": 80})]})


def test_dashboard_role_is_read_only_on_the_gold_data_and_cannot_touch_the_rest(pipeline):
    """No wildcard actions; Athena only in our workgroup; Glue only for the gold database; S3 only gold files + Athena results."""
    role_policies = [r for r in pipeline.find_resources("AWS::IAM::Policy").values()
                     if "DashboardRole" in str(r["Properties"]["Roles"])]
    assert len(role_policies) == 1
    statements = role_policies[0]["Properties"]["PolicyDocument"]["Statement"]
    text = str(statements)
    assert "gold.db/*" in text and "athena-results/*" in text
    for forbidden in ("silver", "bronze", "ops.db", "rds", "secretsmanager", "glue:Create", "glue:Delete", "glue:Update", "s3:DeleteObject"):
        assert forbidden not in text, forbidden
    for statement in statements:
        actions = statement["Action"] if isinstance(statement["Action"], list) else [statement["Action"]]
        assert not any(action == "*" or action.endswith(":*") for action in actions), actions
    athena = [s for s in statements if "athena:StartQueryExecution" in s["Action"]][0]
    assert athena["Resource"] == f"arn:aws:athena:{names.REGION}:123456789012:workgroup/{names.ATHENA_WORKGROUP}"


def test_dashboard_logs_are_kept_one_week_and_deleted_with_the_stack(pipeline):
    pipeline.has_resource_properties("AWS::Logs::LogGroup", {"LogGroupName": names.DASHBOARD_LOG_GROUP, "RetentionInDays": 7})


def test_dashboard_url_is_an_output(pipeline):
    assert "DashboardUrl" in pipeline.to_json()["Outputs"]


def test_dashboard_build_context_has_only_the_files_the_image_needs():
    files = artifacts.build(names.GLUE_JOBS)
    context = files["dashboard"]
    assert (context / "Dockerfile").exists() and (context / "requirements.txt").exists()
    assert (context / ".streamlit" / "config.toml").exists() and (context / "dashboard" / "app.py").exists()
    assert (context / "dashboard" / "views" / "segmentation.py").exists()
    assert not (context / "dashboard" / "Dockerfile").exists()
    names_in_context = {p.name for p in context.rglob("*")}
    assert not names_in_context & {"lake", "lake_demo", "raw", "data", "__pycache__", ".env", "order_items.csv"}
    assert sum(p.stat().st_size for p in context.rglob("*") if p.is_file()) < 1_000_000      # code only: well under 1 MB
