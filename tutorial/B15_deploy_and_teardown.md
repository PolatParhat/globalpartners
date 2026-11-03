# Stage B15: deploy your own build, verify, delete

**Goal:** run your rebuild on AWS once and prove the reference numbers on your dashboard, then delete everything. **You run all AWS commands yourself.** Cost: about $0.42 per hour while deployed plus Glue (the original demo day cost roughly $9 to $10).

## Before you start (checklist)

- [ ] B14 passes in CI; Docker is running; AWS CLI configured for your account; budget alert exists.
- [ ] You know your public IP (`curl -s https://checkip.amazonaws.com`) for `dashboard_cidr`.
- [ ] You have 4 hours free: deploy about 45 minutes, load about an hour, verify, teardown about 30 minutes.
- [ ] You read chapter A12 section 5 (the real first-deploy failures).

## Steps

1. **Deploy:** `infra/up.sh` (it bootstraps CDK, deploys both stacks, uploads the seed CSVs, runs `setup_source` and `load_seed`). If MWAA fails, read the CloudFormation event; delete the `ROLLBACK_COMPLETE` stack and redeploy **only the pipeline stack** with the same contexts (`cdk deploy --all --context dashboard_cidr=<ip>/32 --context alert_email=<address>`). Never run `up.sh` again on a loaded stack: step 5 reruns `setup_source`, which drops the source tables.
2. **Run the DAG** in the Airflow UI: single days first (1, 2, 3 January: 63, 96, 130 orders), then chunks with `replay_until` (4 to 31 Jan; 1 Feb to 31 May; 1 Jun to 31 Dec). Pick 06:00 for the trigger time.
3. **Verify in Athena** (workgroup `globalpartners`, database `gold`): 52,015 orders, $746,223.86, 10,512 customers, CLV $673,614.04, 2,283,740 snapshot rows, 20 locations. `dq_checks` 25/25.
4. **Open the dashboard** (the URL printed by `up.sh`; HTTP, only your IP) and click all six pages.
5. **Delete:** `cd infra && ./down.sh`, type your account id, wait. Then check nothing is left: no stacks, RDS, NAT gateway, load balancer, MWAA environment (`aws rds describe-db-instances`, `aws ec2 describe-nat-gateways`, `aws elbv2 describe-load-balancers`, `aws mwaa list-environments`). KMS keys stay pending deletion for 7 days (free). ECS items may still appear by tag while the cluster is `INACTIVE`: harmless.
6. **Next morning:** Cost Explorer (it lags many hours).

## Troubleshooting (all real)

| Symptom | Cause | Fix |
|---|---|---|
| MWAA `CREATE_FAILED`, null log level | log modules without a level | set a level on every module |
| Dashboard: `No module named 'dashboard'` | import path | `PYTHONPATH=/app` |
| Year-size replay hangs | one huge transaction on a micro database | replay in chunks |
| Run fails in seconds | impossible date (`2023-04-31`) | fix the date |
| Empty run fails `dq_checks` | today's date has no 2023 orders | expected: the check rejects empty loads |
| `CDKToolkit` `DELETE_FAILED` | ECR repo has images | delete the repo with `--force`, rerun cleanup |
| Subnet cannot be deleted | lingering network interfaces | wait and retry |

## Done when

Your own build matches every reference number on AWS, `down.sh` leaves nothing running, and you wrote a short post-deployment note in `notes.md` (what broke, why, the test that now prevents it).
