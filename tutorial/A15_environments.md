# Chapter A15: How real teams handle environments

**Time:** 1 session. **Goal:** explain environments, why the local stack lives in the same repo and branch, and where local and cloud differ.

## 1. The core idea

An **environment** is a complete copy of the system in one place. **Same code, different configuration.** You never keep "the local version" on a separate branch: branches are for *changes in progress*, environments are for *where the code runs*.

## 2. The usual ladder

```
laptop (local) → CI (automated tests) → dev / integration → staging (prod-like) → production
```

| Environment | Purpose | Data | Who deploys |
|---|---|---|---|
| **Local** | fast feedback while coding | tiny/sample | you |
| **CI** | tests on every push, clean machine | synthetic | GitHub Actions |
| **Dev / integration** | shared cloud sandbox; parts working together | sample/synthetic | automation |
| **Staging** | same shape as prod, final rehearsal | masked copy of prod | automation, with approval |
| **Production** | real users | real | automation, with approval |

Big teams use **separate AWS accounts** per environment (blast radius, permissions, cost tracking). This project had one account and one short-lived deployment.

## 3. Branching and environments

- **Trunk-based development:** one long-lived branch (`main`), short-lived feature branches (hours to days), merged by PR after CI. Releases are tags or deployments of `main`.
- Alternatives: Git-flow (long-lived `develop`/`release` branches; heavier, rarely recommended now).
- **Feature flags** hide unfinished work in production without long branches.
- **Ephemeral environments:** spin up a copy for a PR (or a test run), destroy it after. This project's "single deployment then `down.sh`" is exactly that pattern.

## 4. This project's environments

| | Local | AWS (prod-like demo) |
|---|---|---|
| Select | `PIPELINE_ENV=local` | `PIPELINE_ENV=prod` |
| Config | `config/environments.yaml` → `local:` | → `prod:` |
| Source DB | SQL Server container | RDS SQL Server |
| Spark | Glue 5.1 container | Glue jobs |
| Lake | folder, Iceberg Hadoop catalog | S3, Iceberg + Glue Data Catalog |
| Scheduler | MWAA image in Docker | MWAA |
| Dashboard | Streamlit container, Spark SQL | Fargate + ALB, Athena |
| Secrets | `.env` file | Secrets Manager |

Nothing in the transformation code knows which one it is in: `common/config.py` reads the right section.

## 5. Why local never matches the cloud exactly (this project's examples)

| Difference | What happened |
|---|---|
| Catalogs | locally Spark's default catalog resolved through Hive/Glue (`USE lake` asked for AWS credentials); the dashboard needed an in-memory default catalog |
| Query engine | the dashboard uses Spark SQL locally and **Athena** on AWS: different SQL dialects (`GROUP BY 1` works in Spark/Athena but not SQL Server) |
| Architecture | SQL Server container runs under Rosetta on an M-series Mac; RDS does not |
| Size and speed | a year-size replay was fine locally and hung on a db.t3.micro |
| Permissions | local = root-like; AWS = IAM least privilege (a missing permission is only found in AWS) |
| Networking | containers talk by service name; AWS has VPCs, security groups, NAT |
| Packaging | the dashboard's `ModuleNotFoundError` appeared only in the AWS image |
| Service quirks | MWAA required log levels even for disabled modules |

**How teams close the gap:** run the *same image* everywhere; keep config in files/env; add an integration environment in the cloud and automated smoke tests; write a test for every environment-specific bug; document differences.

## 6. Teams on managed warehouses (Snowflake, BigQuery, dbt)

They often have no local stack: dev = a personal schema/database in the real warehouse, CI = a temporary schema built per PR, prod = the real schema. Zero-copy cloning makes cheap copies. The principle is identical.

## 7. Configuration rules

- Config in files and environment variables, never hard-coded; secrets in a secret manager; one config format.
- Defaults for local; explicit values for prod; fail if a required value is missing.
- Parity: same versions (CI mirrors Glue 5.1).

## 8. Exercises

1. Draw the ladder for this project and mark what exists today and what is missing (staging).
2. Read `config/environments.yaml` and list every key that differs between `local` and `prod` and why.
3. Find three places in `src/` that read the environment (`common/config.py`, `common/spark.py`, `dashboard/data.py`).
4. For each row of the table in section 5, name the test or check that would have found it earlier.
5. Explain to a friend why a `local` branch would be a mistake.

## Interview questions

1. How do you manage dev/stage/prod? 2. Trunk-based vs Git-flow? 3. How do you handle configuration and secrets per environment? 4. What are ephemeral environments? 5. How do you keep environments consistent? 6. How do you promote a change to prod safely? (CI, staging, approvals, rollbacks) 7. How do you test data pipelines without prod data? (synthetic or masked data)

## Done when

You can explain exercise 5 and draw the ladder with this project on it.
