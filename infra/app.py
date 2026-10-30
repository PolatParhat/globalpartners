"""CDK app: the GlobalPartners pipeline on AWS (decision G: two stacks).

    cdk synth   → CloudFormation templates in cdk.out/ (nothing touches AWS)
    ./up.sh     → deploy everything;  ./down.sh → delete everything

Options (-c name=value): alert_email (failed-job emails), glue_execution_class (STANDARD | FLEX).
"""
import os

import aws_cdk as cdk

from globalpartners_infra import names
from globalpartners_infra.data_stack import DataStack
from globalpartners_infra.pipeline_stack import PipelineStack


def build_app(account: str | None = None) -> cdk.App:
    app = cdk.App()
    env = cdk.Environment(account=account or os.environ.get("CDK_DEFAULT_ACCOUNT"), region=names.REGION)

    data = DataStack(app, names.DATA_STACK, env=env, description="GlobalPartners: S3 lake, KMS key, Glue catalog, Athena")
    pipeline = PipelineStack(
        app, names.PIPELINE_STACK, env=env,
        description="GlobalPartners: VPC, RDS SQL Server, Glue jobs, MWAA, alerts",
        lake=data.lake, artifacts_bucket=data.artifacts,
        glue_execution_class=app.node.try_get_context("glue_execution_class") or "STANDARD",
        alert_email=app.node.try_get_context("alert_email"),
    )

    for key, value in names.TAGS.items():
        cdk.Tags.of(app).add(key, value)
    cdk.Tags.of(data).add("stack", "data")
    cdk.Tags.of(pipeline).add("stack", "pipeline")
    return app


if __name__ == "__main__":
    build_app().synth()
