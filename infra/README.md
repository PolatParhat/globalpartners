# infra/: the pipeline on AWS (AWS CDK, Python)

Two CloudFormation stacks, written in Python with the AWS CDK, region **us-east-1**:

| Stack | Contents | Cost while deployed |
|---|---|---|
| `GlobalPartnersData` | KMS key, S3 lake bucket (seed CSVs + Iceberg tables), S3 artifacts bucket (job code, DAG), Glue databases `bronze` `silver` `gold` `ops`, Athena workgroup | ≈ $2 / month |
| `GlobalPartnersPipeline` | VPC + NAT, RDS SQL Server Express, 2 logins in Secrets Manager, 7 Glue jobs, MWAA (Airflow 3.3.1, micro), alerts (EventBridge → SNS email) | ≈ $0.42 / hour |

## Commands

| Command | What it does | Touches AWS? |
|---|---|---|
| `./up.sh [email]` | bootstrap → deploy both stacks → upload seed CSVs → create + load the source database | **creates everything** |
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

## Known limitations (demo setup)

- JDBC to RDS is encrypted, but the RDS certificate is not verified (needs the RDS CA in a Java truststore).
- One NAT gateway and single-AZ RDS: no high availability.
- Deploying takes ≈ 45 minutes, deleting ≈ 30 (MWAA).
