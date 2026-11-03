# Stage B14: infrastructure with the AWS CDK

**Goal:** two tested stacks that create the whole system and delete it completely. Prerequisites: A11, A12, B13. **Do not deploy in this stage:** synth and test only (deployment is B15).

## Design

| Stack | Contents |
|---|---|
| `Data` | KMS key, lake bucket, artifacts bucket, Glue databases (bronze, silver, gold, ops), Athena workgroup |
| `Pipeline` | VPC (public + private subnets, NAT), RDS SQL Server Express (db.t3.micro), secrets, eight Glue jobs, MWAA, ECS Fargate + ALB (dashboard), EventBridge rule → SNS (failed Glue jobs) |

Rules: everything `RemovalPolicy.DESTROY`; least privilege (the dashboard role is read-only; Glue and MWAA roles scoped); encryption with the KMS key; tags; no secrets in code.

## Steps

1. `cd infra && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt -r requirements-dev.txt` and install the CDK CLI (`npm install -g aws-cdk@2.1146.1`; Node 24).
2. `names.py`: central names. `app.py`: the CDK app with the two stacks and the `dashboard_cidr` / `alert_email` contexts.
3. `data_stack.py`, then `pipeline_stack.py`: build resource group by group; run `cdk synth --quiet` after each group.
4. `artifacts.py`: stage Glue scripts and the dashboard build folder (Dockerfile, requirements, code only; never data).
5. **Tests first for the risky parts** (`infra/tests/test_stacks.py`): every MWAA log module has a log level; the dashboard role cannot write; nothing is retained after delete; the dashboard Dockerfile sets `PYTHONPATH=/app`; the load balancer is not open to the world (only `dashboard_cidr`).
6. Scripts: `up.sh` (bootstrap, deploy, upload seed data, run setup jobs, print the dashboard URL), `down.sh` (destroy + `cleanup.py`), `cleanup.py` (secrets, log groups, bootstrap leftovers; **empty the ECR repository and bucket before deleting `CDKToolkit`**), `run_glue_job.py`.

## Check

```bash
cd infra
CDK_DEFAULT_ACCOUNT=123456789012 cdk synth --quiet     # placeholder account, no credentials needed
pytest -q                                              # 21 tests in the real project
```

## Compare with the real project

`infra/globalpartners_infra/*.py`, `infra/tests/test_stacks.py`, `infra/up.sh`, `down.sh`, `cleanup.py`, and the bugs table in chapter A12.

## Done when

`cdk synth` succeeds, your tests pass in CI, and you can explain each resource's purpose and its delete behavior.
