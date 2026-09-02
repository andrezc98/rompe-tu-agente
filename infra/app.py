"""CDK app entry point. Run through cdk.json: `npx aws-cdk@2 synth`."""

import os

import aws_cdk as cdk

from agent import config
from infra.sentinel_stack import SentinelStack, name

config.require_sandbox()  # the CDK CLI resolves CDK_DEFAULT_ACCOUNT from ambient credentials; refuse before that happens

app = cdk.App()
SentinelStack(
    app,
    "SentinelDemo",
    stack_name=name("stack", "demo"),
    github_repo=app.node.try_get_context("github_repo") or "andrezc98/rompe-tu-agente",
    env=cdk.Environment(
        account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
        region="us-east-1",  # sentinel_stack.py pins the VPC to us-east-1a; the stack region must match
    ),
)
app.synth()
