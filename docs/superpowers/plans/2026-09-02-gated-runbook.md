# Gated runbook: the steps only the speaker can run

Everything below needs the personal sandbox account, model access, or the public GitHub repo. Run in this order; each step's expected output is in the plan task it comes from. Never run any of it with the machine's default AWS credentials.

## 0. Before anything
- [ ] `git log --format=%ae | sort -u` on branch `build` must show only the personal address. If a client-company address appears, rewrite authorship first (branch never pushed): `git rebase --root -x 'git commit --amend --no-edit --reset-author'` from the repo root with `user.email` set (it is set repo-locally already), then re-check.
- [ ] `aws sso login --profile awsbyandres-sandbox` and `export AWS_PROFILE=awsbyandres-sandbox AWS_REGION=us-east-1`.
- [ ] Bedrock console: enable model access for the Claude profiles you will pin and for `openai.gpt-5.5` (Mantle). Marketplace subscriptions must be accepted, not just listed.

## 1. Infrastructure (plan Task 5, step 8)
- [ ] `npx --yes aws-cdk@2.1139.0 bootstrap` (once per account/region).
- [ ] `npx --yes aws-cdk@2.1139.0 deploy SentinelDemo --require-approval never --outputs-file infra/outputs.json`. If `m9g.medium` is refused, set `INSTANCE_TYPE = "m8g.medium"` in `infra/sentinel_stack.py`, re-run the tests, redeploy. If the account already has a GitHub OIDC provider, import it (README note).
- [ ] `bash infra/enable-transaction-search.sh` (once per account; ten minutes until spans are searchable).

## 2. Models and smoke (plan Task 5, steps 8 and 9)
- [ ] `bash scripts/pin-models.sh`; write `TARGET_MODEL_ID` (Sonnet tier), `JUDGE_MODEL_ID` (Opus tier), `ATTACKER_MODEL_ID` (expected `openai.gpt-5.5`), `SENTINEL_ROLE_ARN`, instance ids and `AGENT_LOG_GROUP=aws-cdarg-sentinel-logs-demo` into `.env` (copy `.env.example`).
- [ ] `uv run --env-file .env python scripts/smoke.py` → three lines ending in `'ok'`.
- [ ] `uv run --env-file .env python -m agent.cli "¿Qué instancias del equipo pagos hay y en qué estado están?"` and the prod-stop refusal question; save both to `evals/results/smoke-sentinel.md`.

## 3. Chaos (plan Task 7, step 6)
- [ ] Smoke: `uv run --env-file .env python -m evals.chaos --prompt v1 --repeats 1 --out evals/results/chaos-v1-smoke.json`; open `evals/results/sessions/chaos-v1/q2-r1__metric_timeout.json` and confirm the injected timeout on `get_metric`.
- [ ] Full: `--prompt v1 --repeats 3 --out evals/results/chaos-v1.json` then `--prompt v2 --repeats 3 --out evals/results/chaos-v2.json`.
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

## 6. GitHub and CI (plan Task 13, steps 3 and 4)
- [ ] `gh repo create andrezc98/rompe-tu-agente --public --source . --push` (after the authorship rewrite), then `gh variable set` for `TARGET_MODEL_ID`, `JUDGE_MODEL_ID`, `ATTACKER_MODEL_ID` and `gh secret set` for `AWS_CI_ROLE_ARN` and `SENTINEL_ROLE_ARN` (the role ARN carries the account id, so it is a secret, not a variable) from `infra/outputs.json`.
- [ ] PR with `CURRENT=v1` → red run, screenshot `slides/assets/ci-rojo.png`; `gh workflow run evals-gate` on main → green, `ci-verde.png`.

## 7. Assets and deck (plan Tasks 15, 16, 17 Pass B)
- [ ] `uv run python -m evals.charts` → `chaos-v1-vs-v2.png`, `redteam-matrix.png`.
- [ ] `uv run --env-file .env python scripts/gen-art.py` → the two scene images (regenerate with another seed if text artifacts appear).
- [ ] Pass B of the slide content: replace every `[DATO: ...]` slot in `slides/contenido.md` with the real value and its file; `uv run pytest tests/test_slides.py` must pass with `chaos-v2.json` present.
- [ ] `bash demo/sanitize-check.sh` before every commit of results or assets; record plan B per `demo/record.md`.
