"""Names shared by the CDK stacks and the up/down scripts.

Fixed names (instead of CDK's random ones) make the scripts, the Glue job parameters and the
leftover check simple: everything this project creates starts with "globalpartners".
"""
PROJECT = "globalpartners"
REGION = "us-east-1"                                  # decision F

DATA_STACK = "GlobalPartnersData"
PIPELINE_STACK = "GlobalPartnersPipeline"

TAGS = {"project": PROJECT, "env": "prod"}            # cost allocation + leftover check

GLUE_DATABASES = ["bronze", "silver", "gold", "ops"]  # = the Iceberg namespaces lake.<layer>
GLUE_JOB_PREFIX = f"{PROJECT}-"
GLUE_JOBS = ["setup_source", "load_seed", "replay_day",
             "extract_to_bronze", "bronze_to_silver", "silver_to_gold", "dq_checks"]

ADMIN_SECRET = f"{PROJECT}/rds-admin"                 # RDS master login (setup jobs only)
READER_SECRET = f"{PROJECT}/rds-etl-reader"           # read-only pipeline login
MWAA_ENVIRONMENT = PROJECT
ALERTS_TOPIC = f"{PROJECT}-alerts"


def lake_bucket(account: str) -> str:
    return f"{PROJECT}-lake-{account}-{REGION}"


def artifacts_bucket(account: str) -> str:
    return f"{PROJECT}-artifacts-{account}-{REGION}"
