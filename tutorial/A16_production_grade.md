# Chapter A16: What makes a project production-grade

**Time:** 1 to 2 sessions. **Goal:** honestly score this project, and know exactly what separates it from a team's production system. The gaps become Part C.

## 1. Definition

Production-grade = it runs without you, fails safely and loudly, can be understood and changed by someone else, protects data and money, and can be restored. "Works on my laptop" is the starting point, not the finish.

## 2. The areas

| Area | Questions | This project (today) | Gap → chapter |
|---|---|---|---|
| **Correctness** | Do numbers reconcile? Are rules tested? | 99 unit tests, 25 DQ checks, AWS numbers match reference to the cent | end-to-end test in CI → C3 |
| **Repeatability** | Can anyone rebuild from the repo? | CDK + scripts + docs | environments + CD → C7 |
| **Source control discipline** | Is main protected? | branch + PR + CI by habit, **not enforced** | C1 |
| **Code quality** | Lint, format, types? | none automated | C2 |
| **Observability** | Do you know before users do? | failure alert by email; logs; run table | freshness/volume alarms, quarantine alerts → C4 |
| **Operations** | Is there a runbook? On-call? | decisions log, no runbook | C5 |
| **Data maintenance** | Do tables stay healthy? | none | compaction, snapshot expiry → C6 |
| **Delivery** | Manual deploy with `up.sh`? | manual, long-lived keys on a laptop | OIDC CD → C7 |
| **Security** | HTTPS, SSO, least privilege, private networking, audit? | HTTP, one IP, shared Glue role, NAT, no audit trail | C8 |
| **Reliability** | Multi-AZ, backups, DR? | single AZ, no backups | C9 |
| **Governance & scale** | Catalog, retention, deletion on request, partitioning, sizing? | minimal | C10 |
| **Cost** | Budget, alerts, tags? | budget alert exists; stack deleted after use | cost dashboards, tags |
| **Documentation** | Decisions, design, runbook, onboarding? | strong decisions log and design doc | runbook, data dictionary |

## 3. Scoring exercise

For each row, give a score from 1 (none) to 5 (a mature team's standard) **with evidence** (a file, a test, a command). Example: Correctness 4: evidence `tests/` (99), `quality/checks.py` (25), AWS reconciliation in `docs/decisions.md`. Write the table into `docs/production_readiness.md` on a branch.

## 4. How teams actually gate production

- **Definition of done:** tests, review, docs, monitoring, rollback plan.
- **Change management:** PR template, required reviewers, CODEOWNERS, status checks, signed commits optional.
- **Release process:** versioned releases, changelog, staged rollout, rollback.
- **Incident handling:** alert → runbook → fix → blameless postmortem → a test or alarm so it never repeats. (This project's three deployment bugs each got a test.)
- **SLAs/SLOs for data:** freshness (data ready by 07:00), completeness, accuracy.

## 5. Honest framing for your resume and interviews

Say: "I built a medallion lakehouse pipeline on AWS (Glue/PySpark, Iceberg, MWAA, CDK, Streamlit on Fargate), deployed it once, ran a full year of data through it with exact reconciliation, and tore it down. It is built to production standard (tests, CI, IaC, data-quality gates, alerts); a demo deployment, not a live service." Then describe the Part C items you added. That is accurate and still strong.

## 6. Exercises

1. Fill the scoring table with evidence.
2. Pick the three gaps with the best value for effort; justify.
3. Write the one-paragraph resume summary above in your own words, and three bullets with numbers (52,015 orders reconciled, 25 DQ checks, 99 + 21 tests, ~$0.42/hour).
4. For each deployment bug in `docs/decisions.md`, name the check that now prevents it.
5. Draft a postmortem (what, impact, cause, fix, prevention) for the CDKToolkit `DELETE_FAILED` incident.

## Interview questions

1. What does "production-ready" mean to you? 2. How do you monitor a pipeline? 3. What do you do when a pipeline fails at 3 AM? 4. How do you roll back a bad data load? 5. How do you secure a data platform? 6. How do you control cost? 7. How do you onboard a new engineer to your pipeline? 8. How do you decide what to automate first?

## Done when

`docs/production_readiness.md` exists with scores and evidence, and you can tell the gap story in two minutes.
