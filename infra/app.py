"""CDK app entry point. Run through cdk.json: `npx aws-cdk@2 synth`."""

import os

import aws_cdk as cdk

from agent import config
from infra.sentinel_stack import SentinelStack, name

config.require_sandbox()  # the CDK CLI resolves CDK_DEFAULT_ACCOUNT from ambient credentials; refuse before that happens

app = cdk.App()
# No fallback literal: this value ends up in the CI role's trust policy, and a stale default
# would silently trust the wrong repository. cdk.json sets it; -c github_repo=owner/repo overrides.
github_repo = app.node.try_get_context("github_repo")
if not github_repo:
    raise SystemExit("error: missing context 'github_repo'; set it in cdk.json or pass -c github_repo=owner/repo")

SentinelStack(
    app,
    "SentinelDemo",
    stack_name=name("stack", "demo"),
    github_repo=github_repo,
    env=cdk.Environment(
        account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
        region="us-east-1",  # sentinel_stack.py pins the VPC to us-east-1a; the stack region must match
    ),
)
app.synth()
