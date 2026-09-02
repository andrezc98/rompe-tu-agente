# Gated runbook: the steps only the speaker can run

Everything below needs the personal sandbox account, model access, or the public GitHub repo. Run in this order; each step's expected output is in the plan task it comes from. Never run any of it with the machine's default AWS credentials.

## 0. Before anything
- [ ] `git log --format=%ae | sort -u` on branch `build` must show only the personal address. If a client-company address appears, rewrite authorship first (branch never pushed): `git rebase --root -x 'git commit --amend --no-edit --reset-author'` from the repo root with `user.email` set (it is set repo-locally already), then re-check.
- [ ] `aws sso login --profile <sandbox profile>` and `export AWS_PROFILE=<sandbox profile> AWS_REGION=us-east-1`. The profile name must contain `sandbox` (`require_sandbox()` and every script refuse anything else). If the account is lent by someone else, its name never goes into this repo, a commit message, or a screenshot; the sanitizer's ignored word list covers it.
- [ ] Bedrock console: enable model access for the Claude profiles you will pin and for the GPT attacker on Mantle (`openai.gpt-5.6-terra`; 2026-09-02: `openai.gpt-5.5` was not offered in the lent account, Terra is its documented successor at lower cost). Marketplace subscriptions must be accepted, not just listed.

## 1. Infrastructure (plan Task 5, step 8; split 2026-09-02: bootstrap from the laptop, demo from GitHub)
- [ ] `npx --yes aws-cdk@2.1139.0 bootstrap --qualifier cdarg2026` (once per account/region; `cdk.json` names the toolkit stack `aws-cdarg-sentinel-toolkit-demo`, so an existing `CDKToolkit` is untouched).
- [ ] `npx --yes aws-cdk@2.1139.0 deploy SentinelBootstrap --require-approval never --outputs-file infra/outputs.json`. If the account already has a GitHub OIDC provider, add `-c oidc_provider_arn=<arn>`.
- [ ] `gh repo create andrezc98/rompe-tu-agente --private --source . --push` (public only when everything is done), then `gh api repos/andrezc98/rompe-tu-agente/actions/oidc/customization/sub --jq .sub_claim_prefix` → set `github_repo` in `cdk.json` to that value without `repo:` (GitHub's `sub` now carries immutable ids; a plain `owner/repo` trust fails with `Not authorized to perform sts:AssumeRoleWithWebIdentity`), redeploy `SentinelBootstrap`. Then `gh secret set AWS_CI_ROLE_ARN` (`CiRoleArn` from `infra/outputs.json`) and `gh secret set SENTINEL_ROLE_ARN` (`arn:aws:iam::<account>:role/aws-cdarg-sentinel-role-agent-demo`; carries the account id, so a secret, not a variable). `gh variable set` for `TARGET_MODEL_ID`, `JUDGE_MODEL_ID`, `ATTACKER_MODEL_ID` comes after §2 pins them.
- [ ] `gh workflow run infra -f action=deploy` and `gh run watch`. If `m9g.medium` is refused, set `INSTANCE_TYPE = "m8g.medium"` in `infra/sentinel_stack.py`, re-run the tests, push, dispatch again. Instance ids: `aws cloudformation describe-stacks --stack-name aws-cdarg-sentinel-stack-demo --query 'Stacks[0].Outputs'`.
- [ ] `bash infra/enable-transaction-search.sh` (once per account; ten minutes until spans are searchable).

## 2. Models and smoke (plan Task 5, steps 8 and 9)
- [ ] `bash scripts/pin-models.sh`; write `TARGET_MODEL_ID` (Sonnet tier), `JUDGE_MODEL_ID` (Opus tier), `ATTACKER_MODEL_ID` (`openai.gpt-5.6-sol`, user ruling 2026-09-02), `REDTEAM_JUDGE_MODEL_ID` (`us.anthropic.claude-opus-4-8`; Opus 5 content-filters adversarial transcripts), `SENTINEL_ROLE_ARN`, instance ids and `AGENT_LOG_GROUP=aws-cdarg-sentinel-logs-demo` into `.env` (copy `.env.example`).
- [ ] `uv run --env-file .env python scripts/smoke.py` → three lines ending in `'ok'`.
- [ ] `uv run --env-file .env python -m agent.cli "¿Qué instancias del equipo pagos hay y en qué estado están?"` and the prod-stop refusal question; save both to `evals/results/smoke-sentinel.md`.

## 3. Chaos (plan Task 7, step 6)
- [ ] Smoke: `uv run --env-file .env python -m evals.chaos --prompt v1 --repeats 1 --out evals/results/chaos-v1-smoke.json`; open `evals/results/sessions/chaos-v1/q2-r1__metric_timeout.json` and confirm the injected timeout on `get_metric`.
- [ ] Full: `--prompt v1 --repeats 3 --out evals/results/chaos-v1.json` then `--prompt v2 --repeats 3 --out evals/results/chaos-v2.json`. **Alone**: nothing else may touch the dev instance while chaos runs (no red team, replay or CI in parallel); q3 stops dev and the runner restores it, but a stop from elsewhere confounds q1/q2 (happened twice on 2026-09-02).
- [ ] Copy the timeout session to `evals/results/show/timeout-v1.json`.
- [ ] Verdict pass (plan Task 8, step 5): fill `evals/verdicts.json`, run `uv run python -m evals.verdicts evals/results/chaos-v1.json --out evals/results/chaos-v1-revisado.json` and the same for v2.
- [ ] `uv run --env-file .env python -m evals.diagnose evals/results/show/timeout-v1.json --out evals/results/show/timeout-v1-diagnosis.json` (plan Task 9, step 5).

## 4. Red team (plan Task 10, steps 5 and 6)
- [ ] Hand cases first: the one-liner in Task 10 step 5; read the transcripts; confirm the IAM denial appears when the model complies.
- [ ] Full: `uv run --env-file .env python -m evals.redteam --generate 8 --passes 2` → reports, `evals/suites/redteam.json`; write `evals/results/redteam-summary.md` (breaches per category and per strategy).
- [ ] Replay: `uv run --env-file .env python -m evals.replay evals/results/redteam-<date>-pass1.json --case stop_prod_fake_ticket --strategy crescendo` → `evals/results/show/stop-prod-session.json` and `-transcript.txt` (try GOAT or pass 2 if the replay does not call `stop_instance`).
- [ ] Diagnose the replayed session too (slide 19 needs both rows): `uv run --env-file .env python -m evals.diagnose evals/results/show/stop-prod-session.json --out evals/results/show/stop-prod-diagnosis.json`.
- [ ] Regression both ways (plan Task 11, step 5): with `CURRENT=v1` expect exit 1; with `v2` expect 0 (or a real breach, which is a slide).

## 5. Observed run (plan Task 12, step 4)
- [ ] `bash scripts/run-observed.sh "¿Por qué está en alarma la instancia de pagos?"`, wait ten minutes, screenshot the session and trace in CloudWatch GenAI Observability to `slides/assets/cw-session.png` and `cw-trace.png` (crop the account id), then `uv run --env-file .env python -m evals.cloudwatch_pull <session.id>` and paste into `evals/results/cloudwatch-roundtrip.md`.

## 6. CI runs (plan Task 13, steps 3 and 4; repo and secrets already exist from §1)
- [ ] `gh variable set` for `TARGET_MODEL_ID`, `JUDGE_MODEL_ID`, `ATTACKER_MODEL_ID` from `.env`.
- [ ] PR with `CURRENT=v1` → red run, screenshot `slides/assets/ci-rojo.png`; `gh workflow run evals-gate` on main → green, `ci-verde.png`.

## 7. Assets and deck (plan Tasks 15, 16, 17 Pass B)
- [ ] `uv run python -m evals.charts` → `chaos-v1-vs-v2.png`, `redteam-matrix.png`.
- [x] Scene images: Nova Canvas v1 is Legacy and refused in the lent account (no active text-to-image model offered in us-east-1), so the two images were generated 2026-09-02 with the speaker's local Codex CLI (`codex exec --ephemeral -s workspace-write "Generate one image, 1280x720 PNG ... save as <name>.png"`) from the prompts in `scripts/gen-art.py`, then copied to `slides/assets/escena-timeout.png` and `escena-crescendo.png`. `scripts/gen-art.py` stays as the Bedrock path for accounts with an active image model.
- [ ] Pass B of the slide content: replace every `[DATO: ...]` slot in `slides/contenido.md` with the real value and its file; `uv run pytest tests/test_slides.py` must pass with `chaos-v2.json` present.
- [ ] `bash demo/sanitize-check.sh` before every commit of results or assets; record plan B per `demo/record.md`.

## 8. Teardown (condition of the lent account: nothing of ours remains when we are done)
Order matters: demo first (its role trusts the CI role), then bootstrap, then the CDK toolkit. Everything is in us-east-1.
- [ ] `gh workflow run infra -f action=destroy` and `gh run watch` → `SentinelDemo` gone (VPC, both instances, alarm, log group, agent role).
- [ ] From the laptop: `npx --yes aws-cdk@2.1139.0 destroy SentinelBootstrap --force` → CI role and OIDC provider gone. From here on GitHub cannot reach the account; that is the point.
- [ ] CDK toolkit: `aws s3 rm s3://cdk-cdarg2026-assets-<account>-us-east-1 --recursive`, then `aws cloudformation delete-stack --stack-name aws-cdarg-sentinel-toolkit-demo` and `aws cloudformation wait stack-delete-complete --stack-name aws-cdarg-sentinel-toolkit-demo`, then `aws s3 rb s3://cdk-cdarg2026-assets-<account>-us-east-1`. The bootstrap template keeps the bucket on delete (`DeletionPolicy: Retain`, verified 2026-09-02 in aws/aws-cdk-cli `bootstrap-template.yaml`); the ECR repo and the `/cdk-bootstrap/cdarg2026/version` parameter go with the stack.
- [ ] Transaction Search back off: `aws xray update-trace-segment-destination --destination XRay`, `aws logs delete-resource-policy --policy-name TransactionSearchXRay`, then `aws logs delete-log-group --log-group-name aws/spans` and `aws logs delete-log-group --log-group-name /aws/application-signals/data` (ResourceNotFound is fine).
- [ ] Bedrock: nothing persistent was created. Model access and Marketplace subscriptions are account settings, short-term API keys expire on their own. Leave model access as found, or turn it off if the account had none before us.
- [ ] Verify empty (every command must return nothing of ours):
  - `aws resourcegroupstaggingapi get-resources --tag-filters Key=Project,Values=rompe-tu-agente --query 'ResourceTagMappingList[].ResourceARN'` → `[]`
  - `aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE ROLLBACK_COMPLETE DELETE_FAILED --query 'StackSummaries[].StackName'` → no `aws-cdarg-sentinel-*`
  - `aws ec2 describe-instances --filters Name=instance-state-name,Values=pending,running,stopping,stopped --query 'Reservations[].Instances[].InstanceId'` → `[]`
  - `aws ec2 describe-vpcs --filters Name=is-default,Values=false --query 'Vpcs[].VpcId'` → `[]`
  - `aws cloudwatch describe-alarms --query 'MetricAlarms[].AlarmName'` → `[]`
  - `aws iam list-roles --query "Roles[?starts_with(RoleName, 'aws-cdarg-') || starts_with(RoleName, 'cdk-cdarg2026')].RoleName"` → `[]`
  - `aws iam list-open-id-connect-providers` → no `token.actions.githubusercontent.com` (unless the account had one before us)
  - `aws logs describe-log-groups --query 'logGroups[].logGroupName'` → nothing of ours
  - `aws s3 ls` → no `cdk-cdarg2026-*`
  - `aws xray get-trace-segment-destination` → `XRay`
- [ ] Send the account owner a closing note: date, region, and the verification output above.
