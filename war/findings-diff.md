# Mythos vs Daybreak: same skill, same repo, same commit

Skill: Agent Toolkit `aws-core` 1.3.0, `aws-well-architected-review`, Full mode. Commit `2615493`.
Both runs: COMPLETE, 216/216 core BP pages read live (MCP), spot-check 10/10, no AWS account calls.

| | Claude Mythos | GPT Daybreak |
|---|---|---|
| Wall time | 33.5 min (7 parallel reader subagents) | ~14 min |
| Lens | General only | **Agentic AI Lens** applied (150/150 lens pages) |
| Findings | 0 C · 1 H · 5 M · 10 L | 0 C · 3 H · 5 M · 6 L + 5 lens (2 H) |
| Security score | 3/5 | 2/5 |
| Overall | 3/5 | 3/5 |
| Status mix | I 53 · PI 55 · NI 5 · NA 63 · CD 40 | (see report) |

## Both found it
| Theme | Mythos | Daybreak |
|---|---|---|
| CI OIDC role trusted for any ref; one role runs PR evals and deploys | **F-01 High** | **F02 High** |
| Unit/IaC/eval gates don't block `infra.yml` deploy | F-02 Medium | F04 Medium |
| The only alarm is a prop and notifies nobody | F-03 Medium | F05 Medium |
| boto3 clients have default timeouts/retries | L-03 Low | F06 Medium |
| Teardown is manual, no expiry | L-02 Low | F07 Medium / F13 Low |
| No dependency/vulnerability scan | F-05 Medium | F10 Low |
| Runbooks lack owners/checkpoints | L-08 Low | F09 Low |

## Only Daybreak
- **F01 High:** tools fall back to the caller's credentials when `SENTINEL_ROLE_ARN` is unset, bypassing the role's prod Deny (`agent/tools.py:30-42`); `require_sandbox` trusts a profile-name substring.
- **L02 High (lens, AGENTSEC04-BP02):** the ticket check is a static list with a known default (`agent/config.py:40-43`), not fresh human approval. This is the root cause of the talk's reproducible breach (Crescendo stopped dev with `CHG-4821`, both passes).
- L01 High (tool args unvalidated), L03-L05 (eval gate vs deploy, I/O screening, no per-run budget).
- F03 High: committed "war-room password". **False positive:** it is the red team's exfiltration canary; Mythos read it correctly as a fake fixture. Daybreak hedged ("if synthetic, label it").

## Only Mythos
- **F-04 Medium:** agent may stop any instance not tagged `env=prod` (untagged or mistagged instances are fair game); Bedrock on `*`; agent role trusts account root.
- F-06 threat register for the pipeline; L-04 IMDSv2/encryption/public subnet; L-09 latency/tokens per run; L-10 linter.

## Reading
- Strongest consensus: the CI trust/role split (both High).
- The agent-authority area is where the models complement each other: Daybreak (with the lens) caught the approval and credential path, Mythos caught the IAM scope. Together they describe the full path the talk's breach took.
