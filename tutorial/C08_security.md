# Chapter C8: security hardening

**Branch:** `harden-security`. **Cost:** some items add cost (domain, certificate is free in ACM, VPC endpoints are paid per hour); build and test first, deploy only when you choose.

## What you build (each a small PR with tests)

1. **HTTPS and sign-in for the dashboard.** Needs a domain (Route 53 or any registrar, a few dollars a year). ACM certificate (DNS-validated), an HTTPS listener on the ALB, HTTP → HTTPS redirect. Authentication: ALB with **Amazon Cognito** (or OIDC/SSO) in front of the target group. This closes the documented deviation from the SME-approved design (HTTP, one IP). Test: the listener on 443 exists, port 80 only redirects.
2. **Per-job least-privilege Glue roles.** Instead of one role for all eight jobs: `setup_source`/`load_seed`/`replay_day` need the admin secret; the five pipeline jobs need only the reader secret and S3/Glue permissions on their own layers (for example `bronze_to_silver` reads bronze, writes silver). Tests assert each role's actions.
3. **VPC endpoints instead of a NAT gateway** (S3 gateway endpoint is free; interface endpoints for Secrets Manager, Glue, CloudWatch Logs, ECR, Athena cost per hour but remove NAT charges and keep traffic private). Test: no route to an internet gateway from the private subnets.
4. **RDS certificate verification.** Today `trust_server_certificate: true`. Build a truststore from the RDS CA bundle, ship it with the Glue job (`--extra-files`) and configure JDBC `trustServerCertificate=false;trustStore=…`. Test: connection fails with a wrong CA.
5. **Audit logging.** CloudTrail (management events) to an encrypted bucket, S3 access logs, ALB access logs; CloudWatch log retention set (30/90 days).
6. **Secrets rotation:** enable rotation on the RDS secret; no secrets in Glue job arguments or logs.
7. **Scanning:** ECR image scanning on push; `docker scout`/Trivy in CI; `cdk-nag` in synth to flag insecure settings.
8. **Data protection:** S3 bucket policy denying non-TLS, block public access (already), KMS key policy review, PII review (loyalty card number stays in silver).

## Check

- `cdk-nag` runs clean or with documented suppressions.
- Each new test fails if you widen a role or remove the redirect.

## Interview angle

Defense in depth, least privilege, encryption at rest and in transit, private networking, secret management, audit trails, threat modeling basics, shared responsibility.

## Done when

The security checklist in `docs/production_readiness.md` (A16) improves from the baseline, with a test for each change.
