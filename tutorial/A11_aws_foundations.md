# Chapter A11: AWS foundations (every service this project used)

**Time:** 2 to 3 sessions. **Goal:** explain each AWS service in this project, how they connect, what they cost, and the security model; answer cloud interview questions.

## 1. Basics

- **Account, region, availability zone (AZ):** this project: account `941377112484`, region `us-east-1`. A region has several AZs (separate data centers). Many services are regional.
- **Shared responsibility:** AWS secures the cloud; you secure what you put in it (IAM, data, networking).
- **Pricing models:** pay per use (Glue per DPU-second, Athena per TB scanned, S3 per GB-month), or per hour while it exists (MWAA, RDS, NAT, load balancer). The second kind is why we delete the stack after the demo.
- Tools: console (browser), CLI (`aws …`), SDK (`boto3`), IaC (CDK/CloudFormation).

## 2. IAM (identity and access management)

| Concept | Meaning |
|---|---|
| **User** | a person or program with long-lived credentials (avoid for programs) |
| **Role** | an identity a service *assumes* with temporary credentials (Glue job role, Fargate task role) |
| **Policy** | JSON: `Effect` (Allow/Deny), `Action` (`s3:GetObject`), `Resource` (an ARN), optional `Condition` |
| **Least privilege** | grant only what is needed. This project: the dashboard role is read-only |
| **ARN** | unique resource name, `arn:aws:s3:::bucket/key` |
| **Trust policy** | who may assume a role |

Deny wins over Allow; default is deny. Never put access keys in code or git; prefer roles and short-lived credentials (OIDC, chapter C7).

## 3. Networking (VPC)

- **VPC:** your private network. **Subnet:** a slice in one AZ. **Public subnet:** route to an **internet gateway**. **Private subnet:** no direct inbound internet; outbound via a **NAT gateway** (costs about $0.045/hour plus data).
- **Security group:** a stateful firewall per resource (allow rules only). Example: the dashboard's load balancer allows port 80 only from one IP (`dashboard_cidr`).
- **VPC endpoint:** private path to AWS services without the NAT (chapter C8).
- Typical flow here: internet → **ALB** (public subnet) → **Fargate task** (private) → Athena/S3; Glue and MWAA run in private subnets; RDS is private.

## 4. Storage and keys

- **S3:** object storage (buckets, keys, versions). Cheap, durable, the lake. Lifecycle rules, versioning, encryption. A "folder" is just a key prefix.
- **KMS:** encryption keys; a customer-managed key encrypts the lake; keys can only be *scheduled* for deletion (7 days minimum).
- **Secrets Manager:** stores secrets (the RDS password); apps fetch them at runtime. Deleted secrets linger 7 to 30 days unless force-deleted (`cleanup.py` does).

## 5. The services in the pipeline

| Service | Role in this project | Billing |
|---|---|---|
| **RDS for SQL Server (Express, db.t3.micro)** | the source database | per hour |
| **Glue (Spark jobs, 2 × G.1X)** | eight PySpark jobs | $0.44 per DPU-hour, per second |
| **Glue Data Catalog** | Iceberg catalog; databases bronze/silver/gold/ops | nearly free |
| **S3** | lake + artifacts bucket | per GB |
| **Athena** | SQL on gold for the dashboard (workgroup `globalpartners`) | per data scanned |
| **MWAA** | Airflow | about $0.29/hour (mw1.micro) |
| **ECS Fargate** | runs the dashboard container (ARM64) | per vCPU/GB-hour |
| **ALB** | public front door | about $0.0225/hour + LCU |
| **ECR** | stores the dashboard image | per GB |
| **EventBridge + SNS** | Glue job failure → email alert | tiny |
| **CloudWatch** | logs, metrics, alarms | per GB and alarm |
| **CloudFormation** | creates/destroys the stacks | free |

Total while deployed: about **$0.42/hour** plus Glue runs.

## 6. How the pieces connect (trace one request)

1. 06:00 MWAA triggers `globalpartners_daily`.
2. Task 1 starts the Glue job `replay_day` (role → Secrets Manager → RDS over the VPC).
3. Tasks 2 to 6 start Glue jobs that read RDS (JDBC) and write Iceberg tables to S3, registering them in the Glue Catalog; logs go to CloudWatch.
4. A job failure triggers EventBridge → SNS email.
5. A user opens the ALB URL; the Fargate task runs Streamlit, which asks Athena (using the task role) to query gold tables in S3 and shows charts.

## 7. Cost thinking

Always-on costs dominate a demo: MWAA, NAT, ALB, RDS. Use `cost_estimate.md` as the model; set a **budget alert**; tag resources; delete what you do not need; check **Cost Explorer** (data lags by hours). Real numbers from this project: demo day about $9 to $10; a full month deployed about $310.

## 8. Reliability and security concepts

Multi-AZ, backups, point-in-time recovery, encryption at rest (KMS) and in transit (TLS), audit with CloudTrail, least privilege, no public databases, secrets in Secrets Manager, patching, WAF/HTTPS in production (this demo used HTTP limited to one IP because there was no domain).

## 9. Exercises (console + CLI; read-only unless stated)

1. `aws sts get-caller-identity` and explain every field.
2. `aws s3 ls`, `aws ecs list-clusters --region us-east-1`, `aws cloudformation list-stacks --region us-east-1` (after teardown they should be empty or `DELETE_COMPLETE`).
3. Open IAM in the console and read the policy of any role in a CDK-created stack in `infra/globalpartners_infra/pipeline_stack.py`; list its allowed actions.
4. Draw the network: VPC, subnets, NAT, ALB, Fargate, RDS, Glue, MWAA. Compare with the CloudFormation resource list in `infra/cdk.out` (synth output).
5. Compute the monthly cost of the always-on parts ($0.42 × 730) and say which two services you would drop first.
6. Explain why Glue needs a NAT or VPC endpoints to reach the internet and Secrets Manager.
7. Write an IAM policy (JSON) allowing read-only access to one S3 prefix.

## Interview questions

1. IAM user vs role vs policy? 2. What is a VPC; public vs private subnet; NAT vs internet gateway? 3. Security group vs NACL? 4. S3 consistency, storage classes, versioning, lifecycle? 5. How do you secure an S3 data lake? 6. Glue vs EMR vs Lambda? 7. Athena vs Redshift? 8. How do you manage secrets? 9. How do you control cost? 10. What is high availability vs disaster recovery? (RPO/RTO) 11. What is an ARN? 12. How do services authenticate to each other? (roles)

## Done when

Exercises 1 to 7 done; you describe the five-step request trace and the cost per hour without notes.
