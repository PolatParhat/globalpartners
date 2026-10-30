"""DataStack: where the data and the code files live (cheap, ≈ $2/month while deployed).

- KMS key        encrypts the lake bucket (and the Athena results)
- lake bucket    s3://globalpartners-lake-…/raw (seed CSVs) and /lake (Iceberg tables)
- artifacts      s3://globalpartners-artifacts-…/glue (job code), /mwaa (DAGs), /spark-events, /glue-temp
- Glue databases bronze, silver, gold, ops = the Iceberg namespaces lake.<layer>
- Athena         a workgroup to query the lake with SQL

Everything is removed by `cdk destroy` (RemovalPolicy.DESTROY, buckets emptied first).
"""
from aws_cdk import Duration, RemovalPolicy, Stack
from aws_cdk import aws_athena as athena
from aws_cdk import aws_glue as glue
from aws_cdk import aws_kms as kms
from aws_cdk import aws_s3 as s3
from constructs import Construct

from globalpartners_infra import names


def private_bucket(scope: Construct, construct_id: str, name: str, **kwargs) -> s3.Bucket:
    """A bucket that is never public, only reachable over HTTPS, and deleted with its stack."""
    return s3.Bucket(
        scope, construct_id,
        bucket_name=name,
        block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
        enforce_ssl=True,
        removal_policy=RemovalPolicy.DESTROY,
        auto_delete_objects=True,                 # empty the bucket so CloudFormation can delete it
        **kwargs,
    )


class DataStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.key = kms.Key(
            self, "LakeKey",
            alias=f"alias/{names.PROJECT}-lake",
            description="Encrypts the GlobalPartners lake bucket",
            enable_key_rotation=True,
            removal_policy=RemovalPolicy.DESTROY,
            pending_window=Duration.days(7),          # the shortest wait AWS allows before a key is deleted
        )

        self.lake = private_bucket(
            self, "Lake", names.lake_bucket(self.account),
            encryption=s3.BucketEncryption.KMS,
            encryption_key=self.key,
            bucket_key_enabled=True,                  # fewer KMS requests, lower cost
        )

        self.artifacts = private_bucket(
            self, "Artifacts", names.artifacts_bucket(self.account),
            encryption=s3.BucketEncryption.S3_MANAGED,
            versioned=True,                           # required by MWAA for its DAG bucket
            lifecycle_rules=[s3.LifecycleRule(noncurrent_version_expiration=Duration.days(7))],
        )

        for layer in names.GLUE_DATABASES:
            glue.CfnDatabase(
                self, f"Database{layer.title()}",
                catalog_id=self.account,
                database_input=glue.CfnDatabase.DatabaseInputProperty(
                    name=layer, description=f"GlobalPartners {layer} layer (Iceberg tables)"),
            )

        athena.CfnWorkGroup(
            self, "Athena",
            name=names.PROJECT,
            recursive_delete_option=True,             # delete saved queries with the workgroup
            work_group_configuration=athena.CfnWorkGroup.WorkGroupConfigurationProperty(
                enforce_work_group_configuration=True,
                engine_version=athena.CfnWorkGroup.EngineVersionProperty(selected_engine_version="Athena engine version 3"),
                result_configuration=athena.CfnWorkGroup.ResultConfigurationProperty(
                    output_location=f"s3://{self.lake.bucket_name}/athena-results/",
                    encryption_configuration=athena.CfnWorkGroup.EncryptionConfigurationProperty(
                        encryption_option="SSE_KMS", kms_key=self.key.key_arn),
                ),
            ),
        )
