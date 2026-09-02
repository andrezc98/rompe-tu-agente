#!/usr/bin/env bash
# Lists the Claude inference profiles and the OpenAI models in the region so the speaker can pin the three ids.
set -euo pipefail
: "${AWS_PROFILE:?set AWS_PROFILE to the sandbox profile}"
case "$AWS_PROFILE" in *sandbox*) ;; *) echo "refusing: AWS_PROFILE is not the sandbox" >&2; exit 1;; esac
REGION="${AWS_REGION:-us-east-1}"
echo "== Claude inference profiles (TARGET_MODEL_ID = Sonnet tier, JUDGE_MODEL_ID = Opus tier)"
aws bedrock list-inference-profiles --region "$REGION" \
  --query 'inferenceProfileSummaries[?contains(inferenceProfileId, `anthropic`)].[inferenceProfileId,status]' \
  --output table
echo "== OpenAI models on Bedrock Mantle (ATTACKER_MODEL_ID; expected openai.gpt-5.5)"
aws bedrock list-foundation-models --region "$REGION" \
  --query 'modelSummaries[?starts_with(modelId, `openai`)].[modelId,modelLifecycle.status]' --output table
echo
echo "Write the three ids to .env, then: uv run --env-file .env python scripts/smoke.py"
