import json
import os
import subprocess
import sys
from pathlib import Path

import aws_cdk as cdk
from aws_cdk.assertions import Match, Template

from infra.sentinel_stack import CDK_BOOTSTRAP_ROLES, INSTANCE_TYPE, STANDARD_TAGS, BootstrapStack, SentinelStack, name


def _demo() -> Template:
    return Template.from_stack(SentinelStack(cdk.App(), "SentinelDemoTest"))


def _bootstrap(**kwargs) -> Template:
    return Template.from_stack(BootstrapStack(cdk.App(), "SentinelBootstrapTest", github_repo="owner/repo", **kwargs))


def test_two_graviton_bottlerocket_instances_with_team_and_env_tags():
    t = _demo()
    t.resource_count_is("AWS::EC2::Instance", 2)
    for env_name in ("prod", "dev"):
        t.has_resource_properties("AWS::EC2::Instance", Match.object_like({
            "InstanceType": INSTANCE_TYPE,
            # Pattern order matches CDK's rendered order (tags are always
            # locale-sorted by key by TagManager, not insertion order):
            # "env" sorts before "Name" ("env" is a prefix of "environment").
            "Tags": Match.array_with([
                {"Key": "env", "Value": env_name},
                {"Key": "Name", "Value": name("ec2", env_name)},
                {"Key": "team", "Value": "pagos"},
            ]),
        }))


def test_instances_use_bottlerocket_arm64_ssm_parameter():
    t = _demo()
    params = t.to_json()["Parameters"]
    assert any("bottlerocket/aws-ecs-2/arm64/latest/image_id" in str(p.get("Default", "")) for p in params.values())


def test_sentinel_role_denies_stop_on_prod():
    t = _demo()
    t.has_resource_properties("AWS::IAM::Policy", Match.object_like({
        "PolicyDocument": {"Statement": Match.array_with([Match.object_like({
            "Sid": "NeverProd",
            "Effect": "Deny",
            "Action": "ec2:StopInstances",
            "Condition": {"StringEquals": {"ec2:ResourceTag/env": "prod"}},
        })])},
    }))


def _role_id(t: Template, role: str) -> str:
    return next(
        k for k, r in t.to_json()["Resources"].items()
        if r["Type"] == "AWS::IAM::Role" and r["Properties"].get("RoleName") == name(role, "demo")
    )


def _role(t: Template, role: str) -> dict:
    return t.to_json()["Resources"][_role_id(t, role)]


def _statements(t: Template, role: str) -> list[dict]:
    """Every inline policy statement attached to the named role (CDK renders them as AWS::IAM::Policy)."""
    logical = _role_id(t, role)
    return [
        st for r in t.to_json()["Resources"].values() if r["Type"] == "AWS::IAM::Policy"
        and {"Ref": logical} in r["Properties"]["Roles"] for st in r["Properties"]["PolicyDocument"]["Statement"]
    ]


def test_ci_role_trusts_only_pull_requests_and_main_of_this_repo():
    """WAR F-01/F02 (SEC11-BP08): no more `repo:<repo>:*`; the eval role is not reachable from other refs."""
    trust = _role(_bootstrap(), "role-ci")["Properties"]["AssumeRolePolicyDocument"]["Statement"][0]
    assert trust["Action"] == "sts:AssumeRoleWithWebIdentity"
    assert trust["Condition"] == {"StringEquals": {
        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
        "token.actions.githubusercontent.com:sub": ["repo:owner/repo:pull_request", "repo:owner/repo:ref:refs/heads/main"],
    }}


def test_deploy_role_trusts_only_the_demo_environment():
    trust = _role(_bootstrap(), "role-deploy")["Properties"]["AssumeRolePolicyDocument"]["Statement"][0]
    assert trust["Condition"] == {"StringEquals": {
        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
        "token.actions.githubusercontent.com:sub": "repo:owner/repo:environment:demo",
    }}


def test_eval_role_cannot_deploy_and_deploy_role_can_only_deploy():
    t = _bootstrap()
    assert "CdkDeploy" not in {st.get("Sid") for st in _statements(t, "role-ci")}
    assert [st["Sid"] for st in _statements(t, "role-deploy")] == ["CdkDeploy"]


def test_oidc_provider_is_native_not_a_custom_resource():
    t = _bootstrap()
    t.resource_count_is("AWS::IAM::OIDCProvider", 1)
    assert not [r for r in t.to_json()["Resources"].values() if r["Type"].startswith("Custom::")]


def test_existing_oidc_provider_can_be_imported():
    t = _bootstrap(oidc_provider_arn="arn:aws:iam::000000000000:oidc-provider/token.actions.githubusercontent.com")
    t.resource_count_is("AWS::IAM::OIDCProvider", 0)
    t.resource_count_is("AWS::IAM::Role", 2)


def test_deploy_role_can_assume_cdk_bootstrap_roles():
    # The policy the CDK guide prescribes for deployers (best-practices-security): tag-based,
    # so it holds for any bootstrap qualifier.
    t = _bootstrap()
    t.has_resource_properties("AWS::IAM::Policy", Match.object_like({
        "PolicyDocument": {"Statement": Match.array_with([Match.object_like({
            "Sid": "CdkDeploy",
            "Action": "sts:AssumeRole",
            "Resource": "*",
            "Condition": {"StringEquals": {"iam:ResourceTag/aws-cdk:bootstrap-role": CDK_BOOTSTRAP_ROLES}},
        })])},
    }))


def test_agent_role_trusts_account_root_and_ci_role_by_arn():
    t = _demo()
    role = next(
        r for r in t.to_json()["Resources"].values()
        if r["Type"] == "AWS::IAM::Role" and r["Properties"].get("RoleName") == name("role-agent", "demo")
    )
    statements = role["Properties"]["AssumeRolePolicyDocument"]["Statement"]
    assert len(statements) == 3
    assert statements[2]["Action"] == ["sts:SetSourceIdentity", "sts:TagSession"]  # Roles Anywhere role chaining
    # The CI role lives in the bootstrap stack: trusted by deterministic ARN, never by GetAtt/Export.
    assert name("role-ci", "demo") in json.dumps(statements)
    assert "Fn::GetAtt" not in json.dumps(statements)


def test_ci_role_can_assume_sentinel_by_arn_and_mint_bedrock_api_keys():
    t = _bootstrap()
    t.has_resource_properties("AWS::IAM::Policy", Match.object_like({
        "PolicyDocument": {"Statement": Match.array_with([
            Match.object_like({"Sid": "Bedrock", "Action": Match.array_with(["bedrock:CallWithBearerToken"])}),
            Match.object_like({"Sid": "AssumeSentinel", "Action": "sts:AssumeRole"}),
        ])},
    }))
    assert name("role-agent", "demo") in json.dumps(t.to_json()["Resources"])


def test_no_cross_stack_exports():
    for t in (_demo(), _bootstrap()):
        assert not [o for o in t.to_json().get("Outputs", {}).values() if "Export" in o]


def test_standard_tags_on_taggable_resources():
    expected = [{"Key": k, "Value": v} for k, v in STANDARD_TAGS.items()]
    t = _demo()
    for resource_type in ("AWS::EC2::Instance", "AWS::IAM::Role", "AWS::Logs::LogGroup", "AWS::CloudWatch::Alarm"):
        t.has_resource_properties(resource_type, Match.object_like({"Tags": Match.array_with(expected)}))
    _bootstrap().has_resource_properties("AWS::IAM::Role", Match.object_like({"Tags": Match.array_with(expected)}))


def test_instances_have_no_public_ip_and_no_open_egress():
    t = _demo()
    t.has_resource_properties("AWS::EC2::Instance", Match.object_like({
        "NetworkInterfaces": Match.array_with([Match.object_like({"AssociatePublicIpAddress": False})]),
    }))
    # CDK's placeholder for allow_all_outbound=False is a rule that can never match
    # any real traffic; anything else here would be a real open-egress rule.
    placeholder = [{
        "CidrIp": "255.255.255.255/32",
        "Description": "Disallow all traffic",
        "FromPort": 252,
        "IpProtocol": "icmp",
        "ToPort": 86,
    }]
    tj = t.to_json()
    for resource in tj["Resources"].values():
        if resource["Type"] == "AWS::EC2::SecurityGroup":
            egress = resource["Properties"].get("SecurityGroupEgress")
            assert egress is None or egress == placeholder


def test_outputs_are_exactly_the_expected_ones():
    assert set(_demo().to_json()["Outputs"]) == {
        "DevInstanceId", "ProdInstanceId", "SentinelRoleArn", "LogGroupName", "ApprovalsTableName"}
    assert set(_bootstrap().to_json()["Outputs"]) == {"CiRoleArn", "DeployRoleArn"}


def test_alarm_thresholds_and_breaching_behavior():
    t = _demo()
    tj = t.to_json()
    dev_tag = {"Key": "Name", "Value": name("ec2", "dev")}
    dev_instance_id = next(
        logical_id
        for logical_id, resource in tj["Resources"].items()
        if resource["Type"] == "AWS::EC2::Instance" and dev_tag in resource["Properties"]["Tags"]
    )
    t.has_resource_properties("AWS::CloudWatch::Alarm", Match.object_like({
        "Threshold": 101,
        "ComparisonOperator": "LessThanThreshold",
        "Dimensions": Match.array_with([{"Name": "InstanceId", "Value": {"Ref": dev_instance_id}}]),
        "TreatMissingData": "breaching",
    }))


def test_app_refuses_without_sandbox_profile():
    # Do not run with a sandbox profile here (that would synth for real); the
    # in-process Template.from_stack tests above already cover synthesis.
    env = os.environ.copy()
    env.pop("AWS_PROFILE", None)
    env.pop("GITHUB_ACTIONS", None)
    result = subprocess.run(
        [sys.executable, "-m", "infra.app"],
        env=env,
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "sandbox" in result.stderr


def test_ci_role_can_only_start_dev_instances():
    t = _bootstrap()
    t.has_resource_properties("AWS::IAM::Policy", Match.object_like({
        "PolicyDocument": {"Statement": Match.array_with([Match.object_like({
            "Sid": "RestoreDevOnly",
            "Action": "ec2:StartInstances",
            "Condition": {"StringEquals": {"ec2:ResourceTag/env": "dev"}},
        })])},
    }))


def test_ci_role_can_call_the_mantle_endpoint():
    t = _bootstrap()
    t.has_resource_properties("AWS::IAM::Policy", Match.object_like({
        "PolicyDocument": {"Statement": Match.array_with([Match.object_like({
            "Sid": "MantleInference", "Action": "bedrock-mantle:CreateInference",
        })])},
    }))


def test_agent_role_may_stop_only_pagos_dev_and_never_prod():
    """WAR F-04 (SEC03-BP01): no more StopInstances on `*` minus prod; an untagged instance is not fair game."""
    sts = {st.get("Sid"): st for st in _statements(_demo(), "role-agent")}
    assert "StopAny" not in sts
    assert sts["StopPagosDev"]["Effect"] == "Allow" and sts["StopPagosDev"]["Action"] == "ec2:StopInstances"
    assert sts["StopPagosDev"]["Condition"] == {
        "StringEquals": {"ec2:ResourceTag/team": "pagos", "ec2:ResourceTag/env": "dev"}}
    assert sts["NeverProd"]["Effect"] == "Deny"


def test_approvals_table_expires_items_and_no_ci_role_can_approve():
    """WAR L02 (AGENTSEC04-BP02): the agent consumes approvals (DeleteItem) and can never create one."""
    demo = _demo()
    demo.has_resource_properties("AWS::DynamoDB::Table", Match.object_like({
        "TableName": name("approvals", "demo"),
        "KeySchema": [{"AttributeName": "ticket", "KeyType": "HASH"}],
        "TimeToLiveSpecification": {"AttributeName": "expires_at", "Enabled": True},
        "BillingMode": "PAY_PER_REQUEST",
    }))
    agent_ddb = [st for st in _statements(demo, "role-agent") if "dynamodb" in json.dumps(st["Action"])]
    assert [st["Action"] for st in agent_ddb] == ["dynamodb:DeleteItem"]
    # CI (assumable from pull requests) can never approve a stop: no DynamoDB access at all (re-review finding)
    for role in ("role-ci", "role-deploy"):
        assert not [st for st in _statements(_bootstrap(), role) if "dynamodb" in json.dumps(st["Action"])]
