#!/usr/bin/env bash
set -euo pipefail
: "${AWS_PROFILE:?set AWS_PROFILE to the sandbox profile}"
case "$AWS_PROFILE" in *sandbox*) ;; *) echo "refusing: AWS_PROFILE is not the sandbox" >&2; exit 1;; esac
REGION="${AWS_REGION:-us-east-1}"
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
aws logs put-resource-policy --region "$REGION" --policy-name TransactionSearchXRay --policy-document "{
  \"Version\": \"2012-10-17\",
  \"Statement\": [{
    \"Sid\": \"TransactionSearchXRayAccess\",
    \"Effect\": \"Allow\",
    \"Principal\": {\"Service\": \"xray.amazonaws.com\"},
    \"Action\": \"logs:PutLogEvents\",
    \"Resource\": [\"arn:aws:logs:$REGION:$ACCOUNT:log-group:aws/spans:*\", \"arn:aws:logs:$REGION:$ACCOUNT:log-group:/aws/application-signals/data:*\"],
    \"Condition\": {\"ArnLike\": {\"aws:SourceArn\": \"arn:aws:xray:$REGION:$ACCOUNT:*\"}, \"StringEquals\": {\"aws:SourceAccount\": \"$ACCOUNT\"}}
  }]
}"
aws xray update-trace-segment-destination --region "$REGION" --destination CloudWatchLogs
echo "Transaction Search enabled; spans become searchable in about ten minutes."
