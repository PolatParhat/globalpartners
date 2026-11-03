# Chapter A13: GitHub Actions (CI/CD)

**Time:** 2 hours. **Goal:** read `.github/workflows/ci.yml`, build your own workflow, and explain CI vs CD.

## 1. Concepts

- **CI (continuous integration):** on every push/PR, automatically build and test. Catches breakage before merge.
- **CD (continuous delivery/deployment):** automatically release (deploy) after CI passes. This project has CI only; chapter C7 adds CD.
- **GitHub Actions:** GitHub's automation. A **workflow** (YAML in `.github/workflows/`) has **jobs**; each job runs on a **runner** (a fresh virtual machine) as a list of **steps** (shell commands or reusable **actions**).

| Key | Meaning |
|---|---|
| `on:` | triggers: `push`, `pull_request`, `schedule`, `workflow_dispatch` (manual) |
| `jobs.<name>.runs-on` | the runner image (`ubuntu-24.04`; pinned so it doesn't change silently) |
| `steps[].uses` | an action (`actions/checkout@v7`, `setup-python@v7`, `setup-java@v6`, `setup-node@v7`) |
| `steps[].run` | a shell command |
| `with:` | inputs for an action |
| `env:` | environment variables |
| `permissions:` | token rights; `contents: read` = read-only (least privilege) |
| `timeout-minutes:` | stop runaway jobs |
| `needs:` | job order |
| `strategy.matrix` | run the job for several versions |
| `cache` | reuse downloaded dependencies |
| `secrets.NAME` | encrypted values you store in repo settings |

## 2. Read the project's workflow

`ci.yml` has two jobs that run in parallel:

1. **unit-tests:** checkout → Python 3.11 (pip cache) → Java 17 (Spark needs the JVM) → `pip install -r tests/requirements.txt` → `python -m py_compile dags/*.py` (DAG syntax) → `pytest`.
2. **infra:** checkout → Python 3.11 → Node 24 (the CDK CLI runs on Node) → `npm install -g aws-cdk@2.1146.1` + pip requirements → `cdk synth --quiet` (placeholder account `123456789012`; no AWS credentials) → `pytest`.

Versions mirror AWS Glue 5.1 (Python 3.11, Java 17, Spark 3.5.6), so "green in CI" means "likely green on Glue".

## 3. The PR flow with CI

Push a branch → workflow runs → checks appear on the PR (`gh pr checks <n>`) → green is required to merge (enforced by branch protection, chapter C1). A red check shows the log of the failing step.

## 4. Writing your own (exercise)

On a scratch repo, `.github/workflows/test.yml`:

```yaml
name: test
on: [push]
permissions:
  contents: read
jobs:
  pytest:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-python@v7
        with:
          python-version: "3.11"
      - run: pip install pytest
      - run: pytest
```

Then: break a test and watch it go red; fix and see green; add a matrix of Python 3.10/3.11; add a lint step (`pip install ruff && ruff check .`) that fails on a style error.

## 5. Security

Pin actions to a version (or a commit SHA for the strictest setups); use `permissions` read-only by default; never print secrets; **do not use long-lived AWS keys**: use **OIDC** so GitHub gets short-lived credentials by assuming an IAM role (C7); beware of untrusted PRs and secrets; enable Dependabot to update action versions.

## 6. CD sketch (preview)

```
PR → CI (tests, cdk synth) → merge to main → deploy to staging (OIDC role) → smoke test → manual approval → deploy to prod
```

Use GitHub **environments** for approvals and per-environment secrets.

## 7. Troubleshooting

| Symptom | Cause |
|---|---|
| Works locally, fails in CI | version differences, missing system packages (Java!), absolute paths, different timezone |
| "Resource not accessible by integration" | token `permissions` too narrow |
| Slow CI | no cache, tests start Spark per test (use a session fixture) |
| Flaky tests | time, order, shared state |

## Interview questions

1. CI vs CD vs continuous deployment? 2. Workflow, job, step, runner, action? 3. How do you cache dependencies? 4. How do you handle secrets? 5. Why OIDC instead of access keys? 6. How do you run jobs in parallel / in order? 7. How do you protect main? 8. How would you deploy this project from GitHub? 9. How do you reduce CI time? 10. What would you gate a merge on? (tests, lint, types, security scan, coverage threshold, review)

## Done when

Your scratch workflow goes red, then green, with a lint step; you explain every line of this project's `ci.yml`.
