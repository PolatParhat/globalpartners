"""After `cdk destroy`: remove what CloudFormation leaves behind, then check that nothing is left.

    python cleanup.py --dry-run     only list what would be removed / what still exists
    python cleanup.py               remove it (used by down.sh)

Left behind by design of the AWS services (not by our stacks):
- Secrets Manager keeps deleted secrets for 7–30 days (and blocks their names) → force-delete
- Glue, MWAA and CDK's helper Lambdas create CloudWatch log groups themselves → delete
- the CDK bootstrap (CDKToolkit stack) keeps its S3 bucket and ECR repository → empty and delete
- KMS keys can only be scheduled for deletion (7 days); a key "pending deletion" costs nothing
"""
import sys

import boto3
from botocore.exceptions import ClientError

from globalpartners_infra import names

REGION = names.REGION
BOOTSTRAP_STACK = "CDKToolkit"
QUALIFIER = "hnb659fds"                          # CDK's default bootstrap qualifier
DRY_RUN = "--dry-run" in sys.argv


def client(service: str):
    return boto3.client(service, region_name=REGION)


def act(message: str, action) -> None:
    print(("would " if DRY_RUN else "") + message)
    if not DRY_RUN:
        action()


def account_id() -> str:
    return boto3.client("sts").get_caller_identity()["Account"]


# ---------------- removal ----------------
def delete_secrets() -> None:
    sm = client("secretsmanager")
    for secret in sm.list_secrets(IncludePlannedDeletion=True,
                                  Filters=[{"Key": "name", "Values": [f"{names.PROJECT}/"]}])["SecretList"]:
        act(f"force-delete secret {secret['Name']}",
            lambda s=secret: sm.delete_secret(SecretId=s["ARN"], ForceDeleteWithoutRecovery=True))


def project_log_groups() -> list[str]:
    logs, found = client("logs"), []
    prefixes = [f"airflow-{names.MWAA_ENVIRONMENT}-", f"/aws/lambda/{names.DATA_STACK}", f"/aws/lambda/{names.PIPELINE_STACK}"]
    if not other_glue_jobs():                    # Glue's log groups are shared by every Glue job in the account
        prefixes.append("/aws-glue/")
    for prefix in prefixes:
        for page in logs.get_paginator("describe_log_groups").paginate(logGroupNamePrefix=prefix):
            found += [group["logGroupName"] for group in page["logGroups"]]
    return found


def delete_log_groups() -> None:
    logs = client("logs")
    for group in project_log_groups():
        act(f"delete log group {group}", lambda g=group: logs.delete_log_group(logGroupName=g))


def other_glue_jobs() -> list[str]:
    jobs = client("glue").list_jobs()["JobNames"]
    return [job for job in jobs if not job.startswith(names.GLUE_JOB_PREFIX)]


def empty_and_delete_bucket(bucket: str) -> None:
    s3 = boto3.resource("s3", region_name=REGION).Bucket(bucket)
    s3.object_versions.delete()                  # every version and delete marker
    s3.delete()


def remove_bootstrap(account: str) -> None:
    cfn = client("cloudformation")
    if stack_exists(BOOTSTRAP_STACK):
        def delete_stack():
            cfn.delete_stack(StackName=BOOTSTRAP_STACK)
            cfn.get_waiter("stack_delete_complete").wait(StackName=BOOTSTRAP_STACK)
        act(f"delete stack {BOOTSTRAP_STACK} (the CDK bootstrap)", delete_stack)
    bucket = f"cdk-{QUALIFIER}-assets-{account}-{REGION}"
    if bucket_exists(bucket):
        act(f"empty and delete bucket {bucket}", lambda: empty_and_delete_bucket(bucket))
    repository = f"cdk-{QUALIFIER}-container-assets-{account}-{REGION}"
    ecr = client("ecr")
    try:
        ecr.describe_repositories(repositoryNames=[repository])
        act(f"delete ECR repository {repository}", lambda: ecr.delete_repository(repositoryName=repository, force=True))
    except ecr.exceptions.RepositoryNotFoundException:
        pass


# ---------------- checks ----------------
def stack_exists(name: str) -> bool:
    try:
        status = client("cloudformation").describe_stacks(StackName=name)["Stacks"][0]["StackStatus"]
        return status != "DELETE_COMPLETE"
    except ClientError:
        return False


def bucket_exists(name: str) -> bool:
    try:
        boto3.client("s3", region_name=REGION).head_bucket(Bucket=name)
        return True
    except ClientError:
        return False


def leftovers(account: str) -> list[str]:
    found = [f"stack {s}" for s in (names.DATA_STACK, names.PIPELINE_STACK, BOOTSTRAP_STACK) if stack_exists(s)]
    found += [f"bucket {b}" for b in (names.lake_bucket(account), names.artifacts_bucket(account),
                                      f"cdk-{QUALIFIER}-assets-{account}-{REGION}") if bucket_exists(b)]
    found += [f"glue job {j}" for j in client("glue").list_jobs()["JobNames"] if j.startswith(names.GLUE_JOB_PREFIX)]
    catalog = {d["Name"] for d in client("glue").get_databases()["DatabaseList"]}
    found += [f"glue database {d}" for d in names.GLUE_DATABASES if d in catalog]
    found += [f"rds instance {d['DBInstanceIdentifier']}" for d in client("rds").describe_db_instances()["DBInstances"]
              if d["DBInstanceIdentifier"].startswith(names.PROJECT)]
    found += [f"mwaa environment {e}" for e in client("mwaa").list_environments()["Environments"] if e == names.MWAA_ENVIRONMENT]
    found += [f"secret {s['Name']}" for s in client("secretsmanager").list_secrets(
        IncludePlannedDeletion=True, Filters=[{"Key": "name", "Values": [f"{names.PROJECT}/"]}])["SecretList"]]
    found += [f"log group {g}" for g in project_log_groups()]
    # anything else that still carries the project tag (a KMS key pending deletion is expected and free)
    kms = client("kms")
    for page in client("resourcegroupstaggingapi").get_paginator("get_resources").paginate(
            TagFilters=[{"Key": "project", "Values": [names.PROJECT]}]):
        for resource in page["ResourceTagMappingList"]:
            arn = resource["ResourceARN"]
            if ":kms:" in arn and kms.describe_key(KeyId=arn)["KeyMetadata"]["KeyState"] == "PendingDeletion":
                continue
            found.append(f"tagged {arn}")
    return sorted(set(found))


def main() -> int:
    account = account_id()
    print(f"account {account}, region {REGION}{' (dry run: nothing is changed)' if DRY_RUN else ''}")
    for name in (names.DATA_STACK, names.PIPELINE_STACK):
        if stack_exists(name):
            print(f"stack {name} still exists: run `cdk destroy --all` first")
            return 1
    delete_secrets()
    delete_log_groups()
    remove_bootstrap(account)
    remaining = [] if DRY_RUN else leftovers(account)
    if DRY_RUN:
        print("\nwhat exists right now:", *(leftovers(account) or ["nothing"]), sep="\n  ")
        return 0
    if remaining:
        print("\nSTILL EXISTS (check in the console):", *remaining, sep="\n  ")
        return 1
    print("\nnothing left: every GlobalPartners resource is gone (a KMS key may show 'pending deletion' for 7 days, at no cost)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
