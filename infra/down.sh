#!/usr/bin/env bash
# Delete EVERYTHING the GlobalPartners pipeline created on AWS, including the lake data,
# then check that nothing is left. Safe to run again if it stops halfway.
#
#   infra/down.sh
set -euo pipefail
cd "$(dirname "$0")"
export AWS_REGION=us-east-1 AWS_DEFAULT_REGION=us-east-1

ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
echo "This DELETES the GlobalPartners pipeline and all its data in AWS account $ACCOUNT, region $AWS_REGION."
read -r -p "Type the account id to continue: " answer
[ "$answer" = "$ACCOUNT" ] || { echo "Cancelled, nothing was deleted."; exit 1; }

[ -d .venv ] || python3.11 -m venv .venv
.venv/bin/pip install --quiet -r requirements.txt
export PATH="$PWD/.venv/bin:$PATH" CDK_DEFAULT_ACCOUNT=$ACCOUNT

echo; echo "== 1/2 Delete PipelineStack, then DataStack (about 30 minutes; MWAA takes the longest)"
# Glue and MWAA release their network interfaces a few minutes after they stop, which can make
# deleting a subnet or security group fail the first time. Then wait and try again.
for attempt in 1 2 3; do
  if cdk destroy --all --force; then break; fi
  [ "$attempt" = 3 ] && { echo "cdk destroy failed 3 times: check the CloudFormation console, then run down.sh again."; exit 1; }
  echo "cdk destroy failed (attempt $attempt); waiting 5 minutes for AWS to release network interfaces…"
  sleep 300
done

echo; echo "== 2/2 Remove what AWS keeps after a stack is deleted, then check nothing is left"
python cleanup.py
