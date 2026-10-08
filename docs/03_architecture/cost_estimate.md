# Step 3: Cost Estimate

GlobalPartners Business Insights Pipeline. Prepared 2026-10-07.

**Purpose:** estimate what the pipeline costs to build and run, show where the money goes,
and choose the cheapest setup that still meets the SME's requirements
(SQL Server source, AWS only, PySpark, scheduling, encryption, failure reload).

**Headline**

| Phase | Monthly cost | Notes |
|---|---|---|
| 1. Local development (Docker on the developer's Mac) | **$0** | All components run locally |
| 2. AWS, "as first designed", always on 24/7 | **≈ $455** | 79 % of it is the always-on Airflow environment |
| 3. AWS, optimized, always on 24/7 | **≈ $307** | MWAA micro, Glue Flex |
| 4. AWS, optimized, deployed only when needed (**chosen**) | **≈ $22** in a working month, **≈ $2** idle | Pipeline stack created and destroyed with CDK |
| 5. One always-on week before submission (**chosen**) | **≈ $71** once | Proves unattended daily operation |

All prices are **on-demand list prices for us-east-1**, taken from the AWS Price List API on
2026-10-07, before tax and before any Free Tier or credits. Section 6 compares us-west-1.

---

## 1. How the pipeline is billed (concepts)

AWS charges in three ways. Knowing which applies to each box on the diagram is the key
to keeping cost down.

| Billing type | Meaning | Examples here | Lever |
|---|---|---|---|
| **Per hour while it exists** | You pay every hour it is switched on, used or not | RDS, NAT gateway, provisioned MWAA, ALB, Fargate, public IPv4 | Switch off / delete when not needed |
| **Per use** | You pay only while work runs, per second or per request | Glue jobs, Athena queries, KMS requests | Run less often, run shorter |
| **Per GB stored per month** | Storage, tiny for 55 MB of source data | S3, RDS disk, snapshots, logs | Small; keep tidy |

**Rule of thumb for this project:** the data is small (55 MB of CSVs, about 1 GB in the lake),
so storage and per-use costs are cents. **The bill is almost entirely things that run per
hour while they exist.** The cost plan therefore removes or switches off per-hour items.

---

## 2. Phase 1: Local development ($0)

Everything is built and tested on the developer's Mac first, then promoted to AWS
(decision 2026-10-04: local-first).

| Component | Local equivalent | Cost | Approx. memory |
|---|---|---|---|
| RDS SQL Server Express | SQL Server 2022 Developer edition in Docker (free for non-production) | $0 | 2 GB |
| AWS Glue 5.1 (PySpark) | Official AWS image `public.ecr.aws/glue/aws-glue-libs:5.1.0` (arm64 build available) | $0 | 4 GB |
| S3 + Iceberg + Glue Catalog | Iceberg tables on the local disk | $0 | – |
| MWAA (Airflow) | Official MWAA local Docker image (`aws-mwaa-docker-images`), same Airflow version as AWS | $0 | 3–4 GB |
| ECS Fargate (Streamlit) | Same Streamlit Docker image | $0 | 0.5 GB |
| Athena | Spark SQL on the local Iceberg tables | $0 | – |

**Machine check (2026-10-07):** Apple M4 Pro, 14 cores, 48 GB RAM, 737 GB free disk.
Give Docker about 12 GB RAM and 6 CPUs, which leaves plenty for the Mac.

Notes:
- SQL Server container images are built for Intel (amd64) only. On Apple Silicon they run
  through Docker Desktop's Rosetta emulation. This works, but needs "Use Rosetta" switched on.
- Docker Desktop is free for personal use, education and small businesses. A larger
  company would need a paid Docker subscription, so this matters under the SME's
  "no new licenses" rule if the local setup were used inside GlobalPartners.
- The full 2023 replay (365 simulated days) is run **locally**, where it is free. See section 5.

---

## 3. Unit prices used (us-east-1, on-demand)

| Service | Price | Billing |
|---|---|---|
| MWAA provisioned, small environment | $0.49 / hour | per hour while it exists |
| MWAA provisioned, micro environment | $0.29 / hour | per hour while it exists |
| MWAA Serverless | $0.08 / task-hour | per task, per second, 1-minute minimum per task |
| Glue ETL job (Glue 5.1) | $0.44 / DPU-hour | per second, 1-minute minimum |
| Glue Flex ETL job (Glue 5.1) | $0.29 / DPU-hour | same, runs on spare capacity (may start later) |
| Glue ETL job (Glue 6.0) | $0.308 / DPU-hour (Flex $0.203) | see section 7 |
| RDS SQL Server Express, db.t3.micro, Single-AZ, license included | $0.022 / hour | per hour while running |
| RDS gp3 storage (SQL Server minimum 20 GB) | $0.115 / GB-month | always, even when stopped |
| NAT gateway | $0.045 / hour + $0.045 / GB | per hour while it exists |
| VPC interface endpoint | $0.01 / hour per AZ + $0.01 / GB | per hour while it exists |
| VPC gateway endpoint for S3 | free | – |
| Public IPv4 address | $0.005 / hour each | per hour while it exists |
| Application Load Balancer | $0.0225 / hour + $0.008 / LCU-hour | per hour while it exists |
| Fargate | $0.04048 / vCPU-hour + $0.004445 / GB-hour | per second while running |
| S3 Standard | $0.023 / GB-month | storage |
| Athena | $5 / TB scanned (10 MB minimum per query) | per query |
| KMS customer-managed key | $1 / key-month + $0.03 / 10,000 requests | – |
| Secrets Manager | $0.40 / secret-month | – |
| CloudWatch Logs | $0.50 / GB ingested (5 GB/month free) | – |
| CloudWatch alarm | $0.10 / alarm-month (10 free) | – |
| SNS email | first 1,000 emails/month free | – |
| Glue Data Catalog | first 1 M objects and 1 M requests/month free | – |
| CloudFormation / CDK, GitHub Actions (public repo) | free | – |

A month is taken as **730 hours**.

---

## 4. Workload assumptions

| Item | Assumption | Why |
|---|---|---|
| Daily DAG | replay task + 5 Glue Spark jobs (extract, bronze→silver, silver→gold, metrics, DQ checks) | Design from Step 3.2 + decision D |
| Glue job size | 2 × G.1X workers = 2 DPU (the minimum for a Spark job) | 55 MB of data needs no more |
| Glue job duration billed | ≈ 3 minutes each | Small data; most of it is Spark start-up |
| Glue per day | 5 jobs × 2 DPU × 3/60 h = **0.5 DPU-hours** | → $0.22/day standard, $0.145/day Flex |
| Orchestrator per day | 6 tasks × ≈ 3.5 min ≈ **20 task-minutes** | Each Glue task waits for its job |
| Lake size | < 1 GB (Parquet is compressed; Iceberg keeps some old snapshots) | Source CSVs are 55 MB |
| Dashboard | 1 Fargate task, 0.25 vCPU / 0.5 GB | Streamlit for a handful of users |
| Logs | < 5 GB/month | Inside the CloudWatch free tier |

---

## 5. Scenarios

### Scenario A: "as first designed", always on 24/7 (≈ $455 / month)

Provisioned MWAA small environment, Glue standard, ALB + Fargate in private subnets, one NAT gateway.

| Item | Calculation | $/month |
|---|---|---|
| MWAA small environment | 0.49 × 730 | 357.70 |
| NAT gateway | 0.045 × 730 | 32.85 |
| RDS SQL Server Express + 20 GB | 0.022 × 730 + 20 × 0.115 | 18.36 |
| ALB | 0.0225 × 730 + LCUs | 17.01 |
| Public IPv4 (2 for ALB, 1 for NAT) | 3 × 0.005 × 730 | 10.95 |
| Fargate (Streamlit) | (0.25 × 0.04048 + 0.5 × 0.004445) × 730 | 9.01 |
| Glue jobs (standard) | 0.5 DPU-h × 0.44 × 30 | 6.60 |
| KMS, Secrets Manager (2), S3, alarms, Athena, ECR | small items | 2.85 |
| **Total** | | **≈ 455** (≈ $5,460 / year) |

**Finding:** 79 % of the bill is the Airflow environment sitting idle 23+ hours a day,
waiting for a 20-minute daily run.

### Scenario B: optimized, always on 24/7 (≈ $307 / month)

Same architecture, with two changes: the **micro** MWAA environment (enough for one
daily DAG) instead of small, and **Glue Flex** for the daily jobs.

| Item | Calculation | $/month |
|---|---|---|
| MWAA micro environment | 0.29 × 730 | 211.70 |
| NAT gateway + its public IPv4 | (0.045 + 0.005) × 730 | 36.50 |
| RDS SQL Server Express + 20 GB | | 18.36 |
| ALB + its 2 public IPv4 | 17.01 + 7.30 | 24.31 |
| Fargate (Streamlit) | | 9.01 |
| Glue jobs (Flex) | 0.5 × 0.29 × 30 | 4.35 |
| KMS, Secrets Manager, S3, alarms, Athena, ECR | | 2.85 |
| **Total** | | **≈ 307** (≈ $3,685 / year), ≈ $0.42 per hour |

**Finding:** MWAA is still 69 % of the bill, because any provisioned Airflow environment is billed
every hour it exists. The next item is the **NAT gateway** (12 %); removing it (VPC endpoints for
4 services cost about the same, $29/month) is evaluated in Step 4 and not assumed here.
Running 24/7 is therefore not worth it for a learning project: see scenario C.

### Scenario C: optimized, deployed only when needed (chosen, ≈ $22 / month)

Infrastructure is split into two CDK stacks:

| Stack | Contents | Lifetime |
|---|---|---|
| `DataStack` | S3 lake bucket, KMS key, ECR repository, RDS snapshot | **Permanent:** data survives rebuilds, costs cents |
| `PipelineStack` | VPC, NAT, RDS (restored from snapshot), Glue jobs, MWAA micro environment, Fargate, ALB, alarms | **Created for a test or demo session, destroyed after** (`cdk deploy` / `cdk destroy`) |

Example working month: **40 hours deployed** (e.g. 5 days × 8 h of AWS testing/demo), during
which **20 daily runs** are executed (a 14-day replay plus re-runs).

| Item | Calculation | $/month |
|---|---|---|
| Per-hour resources for 40 h (RDS 0.022, NAT 0.045, ALB 0.023, Fargate 0.012, 3 × IPv4 0.015) + RDS disk | 40 h × $0.118/h + 0.13 | 4.83 |
| Glue jobs (Flex), 20 runs | 20 × 0.145 | 2.90 |
| MWAA micro environment for 40 h | 40 × 0.29 | 11.60 |
| Permanent and small items (S3 0.50, KMS key 1.00, secret 0.40, ECR 0.05, snapshot 0.10, alarms 0.30, Athena 0.10) | | 2.45 |
| **Total** | | **≈ 22** |

**Idle month** (only `DataStack` exists: S3, KMS key, secret, ECR, snapshot): **≈ $2**.

Trade-off: a full deploy takes about 40 minutes (creating the MWAA environment takes 20–30
minutes, restoring RDS about 15), so a session has to be planned. For a learning project and
SME demos, that is acceptable.

### One always-on week before submission (chosen, ≈ $71 once)

Scenario B for 168 hours: 168 × $0.42 ≈ **$71** (3 days ≈ $30). Shows the pipeline running
unattended on schedule for 7 daily runs, with alerts, before the final submission.

### One-off: replaying all of 2023

The replay script simulates one day of orders per DAG run. Replaying all 365 days of 2023:

| Where | Glue | Orchestration | Total |
|---|---|---|---|
| AWS, Glue standard | 365 × 0.5 × 0.44 = $80.30 | 365 runs × ≈ 20 min ≈ 122 h with the whole stack up: 122 × $0.42 ≈ $51 | **≈ $131** |
| AWS, Glue Flex | 365 × 0.5 × 0.29 = $52.93 | same, ≈ $51 | **≈ $104** |
| **Local Docker** | – | – | **$0** |

**Recommendation:** run the full-year replay locally. On AWS, load history in one initial
full run and replay a short window (about 14 days) to demonstrate daily-evolving CLV.

---

## 6. Region: us-east-1 vs us-west-1

The AWS CLI on the developer machine defaults to us-west-1 (N. California). Every service used is
available in both regions, including MWAA Serverless.

| Scenario | us-east-1 | us-west-1 | Difference |
|---|---|---|---|
| A: as designed, 24/7 | ≈ $455 | ≈ $519 | +14 % |
| B: optimized, 24/7 | ≈ $307 | ≈ $349 | +14 % |

Examples: RDS $0.022 vs $0.027/h, NAT $0.045 vs $0.048/h, MWAA micro $0.29 vs $0.334/h,
CloudWatch Logs $0.50 vs $0.67/GB. Glue is the same in both ($0.44, Flex $0.29).

For a nightly batch pipeline, network distance to the user does not matter.
**us-east-1 is cheaper and receives new features first.**

---

## 7. Options considered and not taken (for now)

| Option | Saving | Why not now |
|---|---|---|
| **Glue 6.0** (Spark 4.1, Python 3.13, released 2026-08-24) | 30 % on Glue (≈ $1.30/month in scenario B) | No local Docker image for 6.0 yet (newest is `aws-glue-libs:5.1.0`), so local and AWS would differ. Revisit when AWS publishes one |
| **MWAA Serverless** (pay per task, ≈ $1/month) | ≈ $11 per working month | Workflows become YAML (DAG Factory), Airflow 3, and there is no Airflow web UI in AWS. Provisioned MWAA with Python DAGs and the UI is the industry standard and a learning goal of the project |
| Multi-AZ RDS | – | Doubles RDS cost; not needed for a daily batch source in a learning project |
| AWS DMS for extract | – | Extra service, logic outside PySpark (decision C) |

---

## 8. Cost guardrails (free)

| Guardrail | What it does |
|---|---|
| **AWS Budgets** alert at $20/month (email at 50 %, 80 %, 100 %) | Warns before a forgotten resource becomes expensive |
| **Cost Anomaly Detection** | Emails when daily spend jumps unexpectedly |
| **Cost allocation tags** `project=globalpartners`, `env=dev|prod`, `stack=data|pipeline` on every resource (set once in CDK) | Cost Explorer can show exactly what this project costs |
| **Check Free Tier / credits** in the Billing console | New accounts (since 2025-07-15) get sign-up credits; older accounts may have 750 free hours/month of RDS SQL Server Express micro |
| `cdk destroy PipelineStack` at the end of every AWS session | Removes every per-hour resource |

---

## 9. Decisions (approved 2026-10-07)

| # | Decision | Reason |
|---|---|---|
| E | **Provisioned MWAA, micro environment, inside the disposable `PipelineStack`** (not MWAA Serverless) | Keeps Python DAGs and the Airflow UI (industry standard, matches the official local MWAA image) for ≈ $12 more per working month |
| F | **us-east-1** | 10–14 % cheaper than us-west-1; new features arrive first |
| G | **Two CDK stacks:** permanent `DataStack` + disposable `PipelineStack`, deployed for testing/demos; plus **one always-on week** before submission | Stateful vs stateless split is standard practice; rebuild-from-code proves the IaC is complete; the final week shows unattended operation |
| H | **Glue Flex** for the scheduled daily jobs, set per job in config | −34 % on Glue; switch to standard for an urgent rerun |
| I | **Full-year replay locally**; on AWS one full initial load + a ~14-day replay | Backfill skills are learned locally for free; on AWS it would cost ≈ $104–131 and take about 5 days |
| – | Guardrails: Budgets alert, Anomaly Detection, cost tags (section 8) | Free |
| – | Stay on **Glue 5.1** | Glue 6.0 has no local Docker image yet (section 7) |

**Not covered by this project (would be added for a real production rollout):** high availability
(Multi-AZ RDS, failover), formal SLAs and on-call rotation.

---

## Sources

- AWS Price List API (`pricing.us-east-1.amazonaws.com` offer files and `aws pricing get-products`), queried 2026-10-07
- [MWAA pricing](https://aws.amazon.com/managed-workflows-for-apache-airflow/pricing/) and [What is Amazon MWAA Serverless?](https://docs.aws.amazon.com/mwaa/latest/mwaa-serverless-userguide/what-is-mwaa-serverless.html)
- [Introducing AWS Glue 6.0 for Apache Spark](https://aws.amazon.com/blogs/big-data/introducing-aws-glue-6-0-for-apache-spark/)
- [Develop and test AWS Glue jobs locally using a Docker image](https://docs.aws.amazon.com/glue/latest/dg/develop-local-docker-image.html); image tags listed from `public.ecr.aws/glue/aws-glue-libs`
