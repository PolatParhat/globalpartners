# infra/: the pipeline on AWS (AWS CDK, Python)

Two CloudFormation stacks, written in Python with the AWS CDK, region **us-east-1**:

| Stack | Contents | Cost while deployed |
|---|---|---|
| `GlobalPartnersData` | KMS key, S3 lake bucket (seed CSVs + Iceberg tables), S3 artifacts bucket (job code, DAG), Glue databases `bronze` `silver` `gold` `ops`, Athena workgroup | ≈ $2 / month |
| `GlobalPartnersPipeline` | VPC + NAT, RDS SQL Server Express, 2 logins in Secrets Manager, 8 Glue jobs, MWAA (Airflow 3.3.1, micro), alerts (EventBridge → SNS email), **dashboard: Streamlit on ECS Fargate (1 ARM64 task, 0.5 vCPU / 1 GB, private subnet) behind an Application Load Balancer** | ≈ $0.42 / hour |

## Commands

| Command | What it does | Touches AWS? |
|---|---|---|
| `./up.sh [email]` | check Docker is running + find your public IP → bootstrap → deploy both stacks (builds and pushes the dashboard image) → upload seed CSVs → create + load the source database | **creates everything** |
| `./down.sh` | delete both stacks → remove what AWS keeps (secrets, log groups, CDK bootstrap) → check nothing is left | **deletes everything** |
| `python cleanup.py --dry-run` | list what exists right now | reads only |
| `python run_glue_job.py <job> [--arg value]` | run one Glue job and wait (e.g. `replay_day --date 2023-01-01`) | runs a job |
| `cdk synth` / `cdk diff` | build the templates / show what a deploy would change | no / reads only |
| `pytest` | test the templates (no deploy, no credentials) | no |

Activate the tools first for the last 4: `source .venv/bin/activate` (up.sh/down.sh create `.venv`).

## How the code reaches AWS

```
src/globalpartners/  ─┐  artifacts.py (at synth)     BucketDeployment (at deploy)
config/*.yaml        ─┼─▶ infra/build/glue/ ─────────▶ s3://globalpartners-artifacts-…/glue/
sql/*.sql            ─┘   infra/build/mwaa/ ─────────▶ s3://globalpartners-artifacts-…/mwaa/dags/
dags/                ─┘
```

Glue job parameters in UPPER_CASE (`--PIPELINE_ENV prod`, `--LAKE_BUCKET …`, `--SOURCE_DB_HOST …`)
become environment variables in the job (`common/job_args.py`) and fill the `${…}` values of the
`prod` section in `config/environments.yaml`. Passwords come from Secrets Manager (`common/credentials.py`).

## The dashboard on AWS

```
Your browser ──HTTP :80──▶ ALB (public subnets; only YOUR IP may connect)
                              │ health check /_stcore/health
                              ▼
                     Fargate task, private subnet (Streamlit, no public IP)
                              │ boto3: StartQueryExecution (workgroup globalpartners, database gold)
                              ▼
                     Athena ──▶ Glue catalog (gold tables) + S3 lake (gold files) ──▶ results CSV in S3
```

- **Image:** built from `dashboard/Dockerfile` by `cdk deploy` (needs Docker running), pushed to the CDK bootstrap's
  ECR repository (`cleanup.py` deletes it). The build context is staged by `artifacts.py` into `infra/build/dashboard/`
  (code only: no data, no lake). ARM64 on purpose: cheaper on Fargate and the same as an Apple-silicon Mac.
- **Who can open it:** `up.sh` finds your public IP and passes `-c dashboard_cidr=<ip>/32`. Without that option the
  default is `127.0.0.1/32` (nobody). If your IP changes: `cdk deploy GlobalPartnersPipeline -c dashboard_cidr=<new ip>/32`.
- **What the task may do (IAM role `DashboardRole`):** run Athena queries in the `globalpartners` workgroup, read the
  `gold` database in the Glue catalog, read `lake/gold.db/*` and `athena-results/*` in S3, write Athena's result files.
  No other layer (silver holds card tokens), no secrets, no delete. Checked by `tests/test_stacks.py`.
- **Right after `up.sh`** the page says it cannot read the gold tables: that is expected until the daily DAG has run
  once (it creates them). Then reload.
- Logs: CloudWatch log group `/ecs/globalpartners-dashboard` (kept 1 week, deleted with the stack).

## Known limitations (demo setup)

- The dashboard is **HTTP only**: HTTPS on the load balancer needs a certificate for a domain name, and this project has
  no domain. The design document said HTTPS; this is the deviation (decision 2026-11-01). Access is limited to one IP instead.
- JDBC to RDS is encrypted, but the RDS certificate is not verified (needs the RDS CA in a Java truststore).
- One NAT gateway and single-AZ RDS: no high availability.
- Deploying takes ≈ 45 minutes, deleting ≈ 30 (MWAA).
