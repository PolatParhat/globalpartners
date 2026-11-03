# Chapter A12: AWS CDK and CloudFormation (infrastructure as code)

**Time:** 2 sessions. **Goal:** explain what infrastructure as code is, read the two stacks, run `cdk synth`, and add a resource with a test.

## 1. Why infrastructure as code (IaC)

Clicking in a console is not repeatable, reviewable or testable. IaC describes infrastructure in files: reviewed in PRs, tested in CI, created with one command, deleted with one command (`up.sh` / `down.sh`).

- **CloudFormation (CFN):** AWS's engine. You give a JSON/YAML **template**; it creates a **stack** of resources in the right order and rolls back on failure.
- **CDK:** write the infrastructure in a real language (Python here). It **synthesizes** (`cdk synth`) into a CloudFormation template, then CFN deploys it. CDK = nicer authoring; CFN = the executor.
- Alternatives: Terraform (multi-cloud; not allowed in this project's constraints), Pulumi, SAM, Serverless Framework.

## 2. CDK concepts

| Concept | Meaning |
|---|---|
| **App** | the program (`infra/app.py`) |
| **Stack** | a unit of deployment. This project: `GlobalPartnersData` and `GlobalPartnersPipeline` |
| **Construct** | a building block. L1 = raw CFN resource (`CfnEnvironment`), L2 = friendly (`s3.Bucket`), L3 = patterns |
| **Environment** | account + region |
| **Context** | inputs: `--context dashboard_cidr=<ip>/32 --context alert_email=…` |
| **Asset** | a local file/image that CDK uploads (Glue scripts, the dashboard image) |
| **Bootstrap** | one-time setup (`CDKToolkit` stack, an S3 bucket and ECR repo for assets) |
| **Removal policy** | what happens to a resource when the stack is deleted (`DESTROY` everywhere here) |

## 3. The workflow

```bash
cd infra
cdk synth              # print/produce CloudFormation templates (no AWS changes)
cdk diff               # what would change
cdk deploy --all       # create/update (costs money)
cdk destroy --all      # delete
```

CI runs `cdk synth` with a placeholder account and `pytest` on the templates: **nothing is deployed**.

## 4. Read this project's stacks

- `names.py`: central names (project, region, stack names).
- `data_stack.py`: KMS key, lake and artifacts buckets, Glue databases, Athena workgroup.
- `pipeline_stack.py`: VPC, RDS, secrets, the eight Glue jobs, the MWAA environment, Fargate service + ALB, EventBridge → SNS alert.
- `artifacts.py`: stages the Glue scripts and the dashboard build folder for upload.
- `up.sh` / `down.sh` / `cleanup.py` / `run_glue_job.py`: orchestration around CDK.

For each file explain: what does it create, what does it depend on, and what happens at delete. **Cross-stack references** (the pipeline stack uses the data stack's bucket) make CDK deploy in order.

## 5. Things that went wrong in the real deployment (read these as lessons)

| Failure | Cause | Fix / lesson |
|---|---|---|
| Stack `ROLLBACK_COMPLETE` | MWAA create failed (a null log level); CFN rolled back | delete the stack before redeploying; a test now asserts every log module has a level |
| Redeploy changed the alert subscription | the `alert_email` context was omitted | always pass the same contexts |
| `CDKToolkit` `DELETE_FAILED` | ECR repository still had images | empty/delete the repository and bucket *before* deleting the bootstrap stack (fixed in `cleanup.py`) |
| Subnet deletion fails | Glue/MWAA ENIs linger | wait and retry (down.sh retries 3×) |
| Secrets name blocked after delete | secrets are kept 7 to 30 days | force-delete in cleanup |

## 6. Testing infrastructure

`infra/tests/test_stacks.py` uses `aws_cdk.assertions.Template.from_stack(stack)` to assert on the synthesized template:

```python
template.has_resource_properties("AWS::S3::Bucket", {"BucketEncryption": Match.any_value()})
template.resource_count_is("AWS::RDS::DBInstance", 1)
```

Examples in the 21 tests: every Airflow log module has a level; the dashboard role cannot write; nothing has a retain policy; the image sets `PYTHONPATH`. **Regression rule:** every deployment bug gets a template test.

## 7. Exercises

1. `cd infra && cdk synth --quiet`; open `cdk.out/*.template.json`; find the Glue job definitions.
2. Run `pytest` in `infra/` (needs `pip install -r requirements-dev.txt`).
3. Add an S3 bucket (L2 construct) to `data_stack.py` on a scratch branch, with encryption and `RemovalPolicy.DESTROY`; run `cdk diff` (shows the new bucket) and write a template test.
4. Add a CloudWatch alarm on an SNS topic; test it.
5. Explain why the Glue job role cannot be shared with the dashboard role.
6. Read `up.sh`: list each step and what it protects against (it checks Docker is running, bootstraps, deploys, uploads seed files, runs setup jobs).
7. Explain how `cdk destroy` and `cleanup.py` split the work.

## Interview questions

1. IaC benefits; CDK vs Terraform vs CloudFormation? 2. What is a stack, a construct (L1/L2/L3)? 3. What does `cdk synth` do; `diff`; `bootstrap`? 4. What happens on a failed deployment? (rollback) 5. How do you manage environments with CDK? (contexts, stack props, one account per env) 6. How do you prevent accidental deletion of data? (removal policy RETAIN, termination protection, backups) 7. How do you test IaC? 8. Drift detection? 9. How do you handle secrets in IaC? (references, never values) 10. How do you handle dependencies between stacks?

## Done when

Exercises 1 to 4 done and the CI-style run (`cdk synth` + `pytest`) is green.
