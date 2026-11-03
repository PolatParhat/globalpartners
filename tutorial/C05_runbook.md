# Chapter C5: the runbook

**Branch:** `harden-runbook`. **Cost:** free. **Why:** at 3 AM nobody remembers; a runbook turns an incident into a checklist.

## What you write: `docs/runbook.md`

Each section: **Symptom → Check → Fix → Verify → Prevent.** Base every entry on something that really happened in this project:

| Section | Source of truth |
|---|---|
| A run failed | read the failed task log in Airflow; Glue log lines are copied in (`verbose=True`); common causes below |
| `dq_checks` failed | open `lake.ops.dq_results` for the batch; which check; reconcile layers |
| An empty run failed `location_summary_ties_to_fact_order` | expected for dates with no orders; ignore or mark failed |
| Re-run a failed day safely | clear the task; MERGE + watermark make it idempotent |
| **Backfill a date range** | trigger the DAG with `replay_until` in chunks (not a year at once); pick 06:00; use a new time to re-trigger the same date |
| Restore after a bad load | Iceberg time travel: find the snapshot, `CALL system.rollback_to_snapshot(...)` on the affected tables, rerun the downstream steps, rerun `dq_checks` |
| Source database crash/slow | SQL Server container restart locally; on AWS check RDS CPU credits (a t3.micro ran out) and long transactions |
| Dashboard down | ALB target health, ECS service events, container logs; the `PYTHONPATH` incident |
| Alert emails | SNS subscription confirmation; re-deploy with the same `alert_email` context |
| Redeploy after a failed first deploy | delete `ROLLBACK_COMPLETE` stacks, redeploy with the same contexts, never rerun `up.sh` on loaded data |
| **Teardown** | `infra/down.sh`; then check no stacks, RDS, NAT gateway, load balancer, MWAA remain; KMS key pending deletion is fine |
| Cost surprise | list the hourly resources; Cost Explorer lags hours; delete the stack |

Add: contacts/ownership, a short architecture recap, "how to deploy", "how to rotate a secret", and the **decision log link**.

## Practice (game day)

Pick three scenarios (a broken date, a failing DQ check on purpose, a bad load you roll back). Follow only the runbook; fix its gaps. Time yourself.

## Interview angle

Runbooks, incident response, blameless postmortems, mean time to recovery (MTTR), game days.

## Done when

A stranger could recover from each listed failure using only the runbook.
