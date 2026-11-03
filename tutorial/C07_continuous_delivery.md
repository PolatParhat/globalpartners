# Chapter C7: continuous delivery with GitHub OIDC and environments

**Branch:** `harden-cd`. **Cost:** free to build; each real deployment costs money (about $0.42/hour). **You create the AWS role and settings yourself; Claude explains them.**

## The idea

Today a human runs `cdk deploy` with long-lived keys on a laptop. Production: GitHub Actions deploys after review, using **short-lived credentials** obtained through **OIDC** (GitHub proves its identity to AWS; AWS hands out a temporary role session). No access keys are stored anywhere.

## What you build

1. **AWS side (one time, CDK or console):** an IAM OIDC identity provider for `token.actions.githubusercontent.com` and a deploy role whose trust policy only allows your repo and branch/environment (`repo:<owner>/<repo>:environment:staging`), with a permissions policy scoped to what CDK needs.
2. **Workflow `deploy.yml`:** `permissions: id-token: write, contents: read`; `aws-actions/configure-aws-credentials` with `role-to-assume`; steps: synth, `cdk diff` (posted to the PR), `cdk deploy` on approval.
3. **Environments:** GitHub *environments* `staging` and `prod` with required reviewers and per-environment variables (account id, region, `dashboard_cidr`).
4. **Config per environment:** `config/environments.yaml` gets `staging:`; stack names include the environment; separate AWS accounts in a real organization.
5. **Release flow:** merge to `main` → CI → deploy to staging → smoke test (dashboard health URL, one Athena query returning the expected row count) → manual approval → prod.
6. **Rollback:** redeploy the previous tag; data rollback via Iceberg (C5).
7. **Cost guard:** a scheduled workflow that destroys staging at night.

## Check

- Workflow run shows "Assumed role" with a session name and no secrets in logs.
- A deploy from a branch not allowed by the trust policy is rejected.

## Interview angle

OIDC vs access keys, environments and approvals, promotion between environments, blue/green and canary, rollback, least-privilege deploy roles.

## Done when

A staging deployment works from GitHub without any stored AWS key (build it once, then destroy it).
