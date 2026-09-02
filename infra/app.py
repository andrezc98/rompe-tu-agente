"""CDK app entry point. Run through cdk.json: `npx aws-cdk@2 <cmd> <stack>`.

SentinelBootstrap is deployed once from the laptop; SentinelDemo from GitHub Actions (infra workflow).
"""

import os

import aws_cdk as cdk

from agent import config
from infra.sentinel_stack import BootstrapStack, SentinelStack, name

config.require_sandbox()  # the CDK CLI resolves CDK_DEFAULT_ACCOUNT from ambient credentials; refuse before that happens

app = cdk.App()
# No fallback literal: this value ends up in the CI role's trust policy, and a stale default
# would silently trust the wrong repository. cdk.json sets it; -c github_repo=... overrides.
# Format = GitHub's OIDC subject prefix without `repo:`, which since 2026 carries immutable ids:
# `owner@<owner_id>/repo@<repo_id>` (gh api repos/<owner>/<repo>/actions/oidc/customization/sub).
github_repo = app.node.try_get_context("github_repo")
if not github_repo:
    raise SystemExit("error: missing context 'github_repo'; set it in cdk.json or pass -c github_repo=owner/repo")

env = cdk.Environment(
    account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
    region="us-east-1",  # sentinel_stack.py pins the VPC to us-east-1a; the stack region must match
)
BootstrapStack(
    app,
    "SentinelBootstrap",
    stack_name=name("bootstrap", "demo"),
    github_repo=github_repo,
    oidc_provider_arn=app.node.try_get_context("oidc_provider_arn"),  # -c oidc_provider_arn=... if the account has one
    env=env,
)
SentinelStack(app, "SentinelDemo", stack_name=name("stack", "demo"), env=env)
app.synth()
