#!/usr/bin/env bash
# Create the whole GlobalPartners pipeline on AWS with one command, ready to run.
#
#   infra/up.sh                     deploy, then create + load the source database
#   infra/up.sh you@example.com     same, and email an alert when a Glue job fails
#
# Costs ≈ $0.42 per hour from now on, until infra/down.sh has finished.
set -euo pipefail
cd "$(dirname "$0")"
export AWS_REGION=us-east-1 AWS_DEFAULT_REGION=us-east-1

ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
echo "This creates the GlobalPartners pipeline in AWS account $ACCOUNT, region $AWS_REGION."
echo "It costs about \$0.42 per hour until infra/down.sh has finished."
read -r -p "Type the account id to continue: " answer
[ "$answer" = "$ACCOUNT" ] || { echo "Cancelled, nothing was created."; exit 1; }

for file in order_items.csv order_item_options.csv date_dim.csv; do
  [ -f "../data/raw/$file" ] || { echo "Missing data/raw/$file (the seed data)."; exit 1; }
done

echo; echo "== 1/5 CDK tools (Python packages for the CDK app)"
[ -d .venv ] || python3.11 -m venv .venv
.venv/bin/pip install --quiet -r requirements.txt
export PATH="$PWD/.venv/bin:$PATH" CDK_DEFAULT_ACCOUNT=$ACCOUNT

echo; echo "== 2/5 CDK bootstrap (only creates something the first time)"
cdk bootstrap "aws://$ACCOUNT/$AWS_REGION"

echo; echo "== 3/5 Deploy DataStack + PipelineStack (about 45 minutes; MWAA takes the longest)"
cdk deploy --all ${1:+--context alert_email=$1} --outputs-file outputs.json

echo; echo "== 4/5 Seed CSVs → S3"
LAKE=$(python -c "from globalpartners_infra import names; print(names.lake_bucket('$ACCOUNT'))")
aws s3 sync ../data/raw "s3://$LAKE/raw/" --exclude "*" --include "*.csv"

echo; echo "== 5/5 Create the source database on RDS and load the seed (2 Glue jobs, a few minutes each)"
python run_glue_job.py setup_source
python run_glue_job.py load_seed

echo
echo "Ready. Next:"
echo "  - Airflow:  open the link 'AirflowUi' in infra/outputs.json → Open Airflow UI → trigger globalpartners_daily"
echo "  - by hand:  python run_glue_job.py replay_day --date 2023-01-01   (from infra/, after: source .venv/bin/activate)"
echo "  - when done: infra/down.sh   (stops all costs)"
