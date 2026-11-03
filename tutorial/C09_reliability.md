# Chapter C9: reliability and disaster recovery

**Branch:** `harden-reliability`. **Cost:** multi-AZ roughly doubles the database price while deployed; build with config flags and enable only in a prod environment.

## Vocabulary

- **RPO** (recovery point objective): how much data you can afford to lose (time). **RTO** (recovery time objective): how long you can be down.
- **HA** (high availability): survive a component/AZ failure automatically. **DR** (disaster recovery): recover from losing a region or the data.

## What you build

1. **Environment-driven settings:** in `config`/CDK context: `multi_az`, `backup_retention_days`, `deletion_protection`, `instance_class`. Demo: single-AZ, no backup, destroy. Prod: multi-AZ, 7 to 35 days of backups, deletion protection, `RemovalPolicy.RETAIN` (or snapshot) for the database and the lake.
2. **RDS:** multi-AZ, automated backups and point-in-time recovery, a larger instance class (the t3.micro ran out of CPU credits during the year load), storage autoscaling.
3. **S3:** versioning on the lake, lifecycle rules (expire non-current versions), optional cross-region replication of the gold layer for DR.
4. **Iceberg:** snapshot retention (C6) is your fast "undo"; define how far back.
5. **Airflow:** MWAA already spreads across AZs; keep DAGs in a versioned bucket; document recreating the environment from code (CDK) in minutes.
6. **Dashboard:** run two Fargate tasks across AZs behind the ALB; a health-check path; deployment circuit breaker/rollback.
7. **Restore drill (do it, don't just write it):** restore the lake from an S3 object version or rollback a table; restore RDS to a point in time into a new instance; record how long it took in `docs/runbook.md`.
8. **Idempotent replays as DR:** the pipeline can rebuild bronze→gold from the source; state the maximum rebuild time (the year load took about 1 hour 10 minutes of replay plus pipeline runs).

## Check

- Tests assert the prod configuration (multi-AZ true, backups > 0, deletion protection) and the demo configuration (destroy).
- The restore drill has a recorded RTO.

## Interview angle

RPO/RTO, backup vs replication, multi-AZ vs multi-region, failure modes, chaos/game days, designing for the failure of every component.

## Done when

Two configurations exist (demo and prod), tested, and a restore drill is documented with timings.
