"""PipelineStack: the parts that run (≈ $0.42/hour while deployed, mostly MWAA).

- network        VPC in 2 zones: public subnets (NAT gateway) + private subnets (everything else)
- source         RDS SQL Server Express + 2 logins in Secrets Manager (admin, read-only etl_reader)
- Glue           one Spark job per pipeline step, running inside the VPC so it can reach RDS
- MWAA           Airflow 3.3.1, runs the daily DAG, which starts the Glue jobs
- alerts         a failed Glue job → EventBridge → SNS → email
- dashboard      Streamlit on ECS Fargate (private subnet) behind an Application Load Balancer; reads gold through Athena

Everything is removed by `cdk destroy` (no final RDS snapshot, no retained resources).
"""
from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecr_assets as ecr_assets
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_ecs_patterns as ecs_patterns
from aws_cdk import aws_elasticloadbalancingv2 as elbv2
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_glue as glue
from aws_cdk import aws_iam as iam
from aws_cdk import aws_logs as logs
from aws_cdk import aws_mwaa as mwaa
from aws_cdk import aws_rds as rds
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as s3deploy
from aws_cdk import aws_secretsmanager as secretsmanager
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sns_subscriptions as subscriptions
from constructs import Construct

from globalpartners_infra import artifacts, names

# SQL Server 2022: the newest version that RDS offers on db.t3.micro AND CloudFormation's schema knows
# (4295 is orderable too, but fails CloudFormation's template validation; checked 2026-10-30)
SQL_SERVER_VERSION = rds.SqlServerEngineVersion.of("16.00.4265.3.v1", "16.00")
AVAILABILITY_ZONES = ["us-east-1a", "us-east-1b"]
GLUE_VERSION = "5.1"                                                             # Spark 3.5.6, Python 3.11
AIRFLOW_VERSION = "3.3.1"                                                        # same as the local MWAA image
NOBODY = "127.0.0.1/32"                                                          # default for who may open the dashboard: no one (up.sh passes your IP)


class PipelineStack(Stack):

    @property
    def availability_zones(self) -> list[str]:
        """Fixed zones instead of a lookup in the account at synth time (works in CI without AWS access)."""
        return AVAILABILITY_ZONES

    def __init__(self, scope: Construct, construct_id: str, *, lake: s3.IBucket, artifacts_bucket: s3.IBucket,
                 glue_execution_class: str = "STANDARD", alert_email: str | None = None,
                 dashboard_cidr: str = NOBODY, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        files = artifacts.build(names.GLUE_JOBS)

        # ---------------- network ----------------
        vpc = ec2.Vpc(
            self, "Vpc",
            availability_zones=AVAILABILITY_ZONES,     # MWAA needs private subnets in 2 zones; named, so synth needs no AWS lookup
            nat_gateways=1,                            # one is enough for a demo (≈ $0.045/hour)
            subnet_configuration=[
                ec2.SubnetConfiguration(name="public", subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=24),
                ec2.SubnetConfiguration(name="private", subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS, cidr_mask=24),
            ],
        )
        vpc.add_gateway_endpoint("S3", service=ec2.GatewayVpcEndpointAwsService.S3)   # free; S3 traffic skips the NAT
        private = ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)

        glue_sg = ec2.SecurityGroup(self, "GlueSg", vpc=vpc, description="Glue jobs")
        glue_sg.add_ingress_rule(glue_sg, ec2.Port.all_tcp(), "Spark driver and executors talk to each other")
        db_sg = ec2.SecurityGroup(self, "DatabaseSg", vpc=vpc, description="RDS SQL Server")
        db_sg.add_ingress_rule(glue_sg, ec2.Port.tcp(1433), "Only the Glue jobs reach SQL Server")
        mwaa_sg = ec2.SecurityGroup(self, "AirflowSg", vpc=vpc, description="MWAA")
        mwaa_sg.add_ingress_rule(mwaa_sg, ec2.Port.all_traffic(), "Airflow components talk to each other")

        # ---------------- source database ----------------
        database = rds.DatabaseInstance(
            self, "SourceDb",
            instance_identifier=f"{names.PROJECT}-source",
            engine=rds.DatabaseInstanceEngine.sql_server_ex(version=SQL_SERVER_VERSION),
            license_model=rds.LicenseModel.LICENSE_INCLUDED,         # no own license needed
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MICRO),
            allocated_storage=20,                                    # SQL Server minimum
            storage_type=rds.StorageType.GP3,
            storage_encrypted=True,
            credentials=rds.Credentials.from_generated_secret("gpadmin", secret_name=names.ADMIN_SECRET),
            vpc=vpc, vpc_subnets=private, security_groups=[db_sg],
            publicly_accessible=False,
            multi_az=False,
            backup_retention=Duration.days(0),                       # no automated backups: faster, deletable
            delete_automated_backups=True,
            deletion_protection=False,
            removal_policy=RemovalPolicy.DESTROY,                    # no final snapshot
        )
        reader_secret = secretsmanager.Secret(
            self, "ReaderSecret",
            secret_name=names.READER_SECRET,
            description="Read-only SQL Server login used by the pipeline (created by the setup_source job)",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template='{"username": "etl_reader"}',
                generate_string_key="password",
                password_length=24,
                exclude_punctuation=True,                            # safe inside SQL and JDBC strings
                require_each_included_type=True,                     # upper, lower, digit: SQL Server policy
            ),
            removal_policy=RemovalPolicy.DESTROY,
        )

        # ---------------- code files in S3 ----------------
        glue_files = s3deploy.BucketDeployment(
            self, "GlueFiles",
            sources=[s3deploy.Source.asset(str(files["glue"]))],
            destination_bucket=artifacts_bucket, destination_key_prefix="glue/",
            memory_limit=512,
        )
        dag_files = s3deploy.BucketDeployment(
            self, "DagFiles",
            sources=[s3deploy.Source.asset(str(files["mwaa"]))],
            destination_bucket=artifacts_bucket, destination_key_prefix="mwaa/",
            memory_limit=512,
        )

        # ---------------- Glue jobs ----------------
        glue_role = iam.Role(
            self, "GlueRole",
            assumed_by=iam.ServicePrincipal("glue.amazonaws.com"),
            managed_policies=[iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSGlueServiceRole")],
        )
        lake.grant_read_write(glue_role)                             # includes the lake's KMS key
        artifacts_bucket.grant_read_write(glue_role)                 # code (read), Spark UI logs + temp (write)
        database.secret.grant_read(glue_role)
        reader_secret.grant_read(glue_role)

        connection = glue.CfnConnection(
            self, "GlueVpcConnection",
            catalog_id=self.account,
            connection_input=glue.CfnConnection.ConnectionInputProperty(
                name=f"{names.PROJECT}-vpc",
                connection_type="NETWORK",
                physical_connection_requirements=glue.CfnConnection.PhysicalConnectionRequirementsProperty(
                    subnet_id=vpc.private_subnets[0].subnet_id,
                    availability_zone=vpc.private_subnets[0].availability_zone,
                    security_group_id_list=[glue_sg.security_group_id],
                ),
            ),
        )

        code = f"s3://{artifacts_bucket.bucket_name}/glue"
        extra_files = ",".join(f"{code}/files/{name}" for name in sorted(p.name for p in (files["glue"] / "files").iterdir()))
        common_arguments = {
            "--job-language": "python",
            "--datalake-formats": "iceberg",
            "--additional-python-modules": "PyYAML==6.0.3",          # not in the Glue 5.1 image (decision 2026-10-15)
            "--extra-py-files": f"{code}/globalpartners.zip",
            "--extra-files": extra_files,
            "--enable-continuous-cloudwatch-log": "true",
            "--enable-spark-ui": "true",
            "--spark-event-logs-path": f"s3://{artifacts_bucket.bucket_name}/spark-events/",
            "--TempDir": f"s3://{artifacts_bucket.bucket_name}/glue-temp/",
            # UPPER_CASE parameters become environment variables (common/job_args.py) → config/environments.yaml prod
            "--PIPELINE_ENV": "prod",
            "--LAKE_BUCKET": lake.bucket_name,
            "--SOURCE_DB_HOST": database.db_instance_endpoint_address,
            "--SOURCE_ADMIN_SECRET": names.ADMIN_SECRET,
            "--SOURCE_READER_SECRET": names.READER_SECRET,
        }
        self.glue_jobs = []
        for job in names.GLUE_JOBS:
            glue_job = glue.CfnJob(
                self, f"Job{''.join(part.title() for part in job.split('_'))}",
                name=f"{names.GLUE_JOB_PREFIX}{job}",
                role=glue_role.role_arn,
                command=glue.CfnJob.JobCommandProperty(
                    name="glueetl", python_version="3", script_location=f"{code}/jobs/{job}.py"),
                glue_version=GLUE_VERSION,
                worker_type="G.1X",
                number_of_workers=2,                                 # the minimum for a Spark job
                execution_class=glue_execution_class,                # STANDARD for the demo; FLEX is 34 % cheaper
                timeout=60,                                          # minutes
                max_retries=0,                                       # Airflow does the retries
                connections=glue.CfnJob.ConnectionsListProperty(connections=[f"{names.PROJECT}-vpc"]),
                default_arguments=common_arguments,
            )
            glue_job.node.add_dependency(connection, glue_files)
            self.glue_jobs.append(glue_job)

        # ---------------- Airflow (MWAA) ----------------
        environment_arn = f"arn:aws:airflow:{self.region}:{self.account}:environment/{names.MWAA_ENVIRONMENT}"
        mwaa_role = iam.Role(
            self, "AirflowRole",
            assumed_by=iam.CompositePrincipal(iam.ServicePrincipal("airflow.amazonaws.com"),
                                              iam.ServicePrincipal("airflow-env.amazonaws.com")),
        )
        artifacts_bucket.grant_read(mwaa_role)
        mwaa_role.add_to_policy(iam.PolicyStatement(actions=["airflow:PublishMetrics"], resources=[environment_arn]))
        mwaa_role.add_to_policy(iam.PolicyStatement(
            actions=["logs:CreateLogStream", "logs:CreateLogGroup", "logs:PutLogEvents", "logs:GetLogEvents",
                     "logs:GetLogRecord", "logs:GetLogGroupFields", "logs:GetQueryResults"],
            resources=[f"arn:aws:logs:{self.region}:{self.account}:log-group:airflow-{names.MWAA_ENVIRONMENT}-*"]))
        mwaa_role.add_to_policy(iam.PolicyStatement(
            actions=["logs:DescribeLogGroups", "cloudwatch:PutMetricData", "s3:GetAccountPublicAccessBlock"],
            resources=["*"]))
        mwaa_role.add_to_policy(iam.PolicyStatement(
            actions=["sqs:ChangeMessageVisibility", "sqs:DeleteMessage", "sqs:GetQueueAttributes", "sqs:GetQueueUrl",
                     "sqs:ReceiveMessage", "sqs:SendMessage"],
            resources=[f"arn:aws:sqs:{self.region}:*:airflow-celery-*"]))
        mwaa_role.add_to_policy(iam.PolicyStatement(
            actions=["kms:Decrypt", "kms:DescribeKey", "kms:GenerateDataKey*", "kms:Encrypt"],
            not_resources=[f"arn:aws:kms:*:{self.account}:key/*"],     # AWS-owned key used by MWAA's queue
            conditions={"StringLike": {"kms:ViaService": [f"sqs.{self.region}.amazonaws.com"]}}))
        job_arns = [f"arn:aws:glue:{self.region}:{self.account}:job/{names.GLUE_JOB_PREFIX}*"]
        mwaa_role.add_to_policy(iam.PolicyStatement(
            actions=["glue:StartJobRun", "glue:GetJobRun", "glue:GetJobRuns", "glue:GetJob", "glue:BatchStopJobRun"],
            resources=job_arns))
        mwaa_role.add_to_policy(iam.PolicyStatement(                 # read the Glue job logs (verbose=True)
            actions=["logs:GetLogEvents", "logs:FilterLogEvents", "logs:DescribeLogStreams"],
            resources=[f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws-glue/*"]))

        environment = mwaa.CfnEnvironment(
            self, "Airflow",
            name=names.MWAA_ENVIRONMENT,
            airflow_version=AIRFLOW_VERSION,
            environment_class="mw1.micro",                           # decision E: the smallest, $0.29/hour
            execution_role_arn=mwaa_role.role_arn,
            source_bucket_arn=artifacts_bucket.bucket_arn,
            dag_s3_path="mwaa/dags",
            airflow_configuration_options={"globalpartners.pipeline_env": "prod"},   # read by the DAG
            webserver_access_mode="PUBLIC_ONLY",                     # Airflow UI in the browser, IAM sign-in
            network_configuration=mwaa.CfnEnvironment.NetworkConfigurationProperty(
                subnet_ids=[subnet.subnet_id for subnet in vpc.private_subnets],
                security_group_ids=[mwaa_sg.security_group_id],
            ),
            logging_configuration=mwaa.CfnEnvironment.LoggingConfigurationProperty(
                task_logs=mwaa.CfnEnvironment.ModuleLoggingConfigurationProperty(enabled=True, log_level="INFO"),
                scheduler_logs=mwaa.CfnEnvironment.ModuleLoggingConfigurationProperty(enabled=True, log_level="WARNING"),
                dag_processing_logs=mwaa.CfnEnvironment.ModuleLoggingConfigurationProperty(enabled=True, log_level="WARNING"),
                # The MWAA API rejects a module without a log level, even when the module is switched off.
                webserver_logs=mwaa.CfnEnvironment.ModuleLoggingConfigurationProperty(enabled=False, log_level="WARNING"),
                worker_logs=mwaa.CfnEnvironment.ModuleLoggingConfigurationProperty(enabled=False, log_level="WARNING"),
            ),
        )
        environment.node.add_dependency(dag_files, mwaa_role)

        # ---------------- alerts ----------------
        topic = sns.Topic(self, "Alerts", topic_name=names.ALERTS_TOPIC)
        if alert_email:
            topic.add_subscription(subscriptions.EmailSubscription(alert_email))
        events.Rule(
            self, "GlueJobFailed",
            description="A GlobalPartners Glue job failed, timed out or stopped with an error",
            event_pattern=events.EventPattern(
                source=["aws.glue"], detail_type=["Glue Job State Change"],
                detail={"jobName": [{"prefix": names.GLUE_JOB_PREFIX}], "state": ["FAILED", "TIMEOUT", "ERROR"]}),
            targets=[targets.SnsTopic(topic)],
        )

        # ---------------- dashboard: Streamlit on ECS Fargate behind an Application Load Balancer ----------------
        # The task role is read-only on the gold data: it can run Athena queries in our workgroup, read the gold
        # tables' metadata in the Glue catalog and the gold files in S3, and write Athena's result files. Nothing else.
        dashboard_role = iam.Role(self, "DashboardRole", assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
                                  description="Streamlit dashboard: reads the gold tables through Athena")
        dashboard_role.add_to_policy(iam.PolicyStatement(
            actions=["athena:StartQueryExecution", "athena:GetQueryExecution", "athena:GetQueryResults",
                     "athena:StopQueryExecution", "athena:GetWorkGroup"],
            resources=[f"arn:aws:athena:{self.region}:{self.account}:workgroup/{names.ATHENA_WORKGROUP}"]))
        glue_arn = f"arn:aws:glue:{self.region}:{self.account}"
        dashboard_role.add_to_policy(iam.PolicyStatement(
            actions=["glue:GetDatabase", "glue:GetTable", "glue:GetTables", "glue:GetPartition", "glue:GetPartitions"],
            resources=[f"{glue_arn}:catalog", f"{glue_arn}:database/{names.GOLD_DATABASE}",
                       f"{glue_arn}:table/{names.GOLD_DATABASE}/*"]))
        lake.grant_read(dashboard_role, f"lake/{names.GOLD_DATABASE}.db/*")   # Iceberg puts a table at <warehouse>/<database>.db/<table>/
        lake.grant_read(dashboard_role, "athena-results/*")                   # read the result file back
        lake.grant_put(dashboard_role, "athena-results/*")                    # Athena writes it with our credentials; no delete (and the KMS key)

        cluster = ecs.Cluster(self, "DashboardCluster", cluster_name=names.DASHBOARD_CLUSTER, vpc=vpc)
        dashboard_logs = logs.LogGroup(self, "DashboardLogs", log_group_name=names.DASHBOARD_LOG_GROUP,
                                       retention=logs.RetentionDays.ONE_WEEK, removal_policy=RemovalPolicy.DESTROY)
        dashboard = ecs_patterns.ApplicationLoadBalancedFargateService(
            self, "Dashboard",
            cluster=cluster, service_name=names.DASHBOARD_SERVICE,
            cpu=512, memory_limit_mib=1024, desired_count=1,                  # Streamlit + pandas + plotly: 0.5 GB is too tight
            min_healthy_percent=100, max_healthy_percent=200,                 # a new version starts before the old one stops
            runtime_platform=ecs.RuntimePlatform(cpu_architecture=ecs.CpuArchitecture.ARM64,     # cheaper, same as an Apple-silicon Mac
                                                 operating_system_family=ecs.OperatingSystemFamily.LINUX),
            task_subnets=private, assign_public_ip=False,                     # the task sits in a private subnet (NAT for the image pull)
            public_load_balancer=True, listener_port=80, protocol=elbv2.ApplicationProtocol.HTTP,
            open_listener=False,                                              # who may connect is set below, not "everyone"
            circuit_breaker=ecs.DeploymentCircuitBreaker(rollback=True),      # a broken image fails the deploy quickly
            health_check_grace_period=Duration.seconds(90),
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_asset(str(files["dashboard"]), platform=ecr_assets.Platform.LINUX_ARM64),
                container_port=names.DASHBOARD_PORT,
                task_role=dashboard_role,
                log_driver=ecs.LogDrivers.aws_logs(stream_prefix="dashboard", log_group=dashboard_logs),
                environment={"PIPELINE_ENV": "prod", "AWS_REGION": self.region,
                             "ATHENA_WORKGROUP": names.ATHENA_WORKGROUP},
            ),
        )
        dashboard.target_group.configure_health_check(                       # Streamlit's own health endpoint
            path="/_stcore/health", healthy_http_codes="200", interval=Duration.seconds(30),
            healthy_threshold_count=2, unhealthy_threshold_count=3)
        dashboard.target_group.set_attribute("deregistration_delay.timeout_seconds", "10")   # faster deploys and deletes
        dashboard.load_balancer.set_attribute("idle_timeout.timeout_seconds", "300")        # Streamlit keeps a websocket open
        dashboard.load_balancer.connections.allow_from(
            ec2.Peer.ipv4(dashboard_cidr), ec2.Port.tcp(80), "Who may open the dashboard (up.sh passes your IP)")

        CfnOutput(self, "DashboardUrl", value=f"http://{dashboard.load_balancer.load_balancer_dns_name}")
        CfnOutput(self, "AirflowUi", value=f"https://{self.region}.console.aws.amazon.com/mwaa/home?region={self.region}#environments/{names.MWAA_ENVIRONMENT}")
        CfnOutput(self, "SourceDbEndpoint", value=database.db_instance_endpoint_address)
