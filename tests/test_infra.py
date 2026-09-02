import os
import subprocess
import sys
from pathlib import Path

import aws_cdk as cdk
from aws_cdk.assertions import Match, Template

from infra.sentinel_stack import INSTANCE_TYPE, STANDARD_TAGS, SentinelStack, name


def _template() -> Template:
    app = cdk.App()
    stack = SentinelStack(app, "SentinelDemoTest", github_repo="owner/repo")
    return Template.from_stack(stack)


def test_two_graviton_bottlerocket_instances_with_team_and_env_tags():
    t = _template()
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
    t = _template()
    params = t.to_json()["Parameters"]
    assert any("bottlerocket/aws-ecs-2/arm64/latest/image_id" in str(p.get("Default", "")) for p in params.values())


def test_sentinel_role_denies_stop_on_prod():
    t = _template()
    t.has_resource_properties("AWS::IAM::Policy", Match.object_like({
        "PolicyDocument": {"Statement": Match.array_with([Match.object_like({
            "Sid": "NeverProd",
            "Effect": "Deny",
            "Action": "ec2:StopInstances",
            "Condition": {"StringEquals": {"ec2:ResourceTag/env": "prod"}},
        })])},
    }))


def test_ci_role_trusts_only_this_repo():
    t = _template()
    t.has_resource_properties("AWS::IAM::Role", Match.object_like({
        "RoleName": name("role-ci", "demo"),
        "AssumeRolePolicyDocument": {"Statement": Match.array_with([Match.object_like({
            "Action": "sts:AssumeRoleWithWebIdentity",
            "Condition": Match.object_like({
                "StringEquals": {"token.actions.githubusercontent.com:aud": "sts.amazonaws.com"},
                "StringLike": {"token.actions.githubusercontent.com:sub": "repo:owner/repo:*"},
            }),
        })])},
    }))


def test_agent_role_trusts_account_root_and_ci_role():
    t = _template()
    t.has_resource_properties("AWS::IAM::Role", Match.object_like({
        "RoleName": name("role-agent", "demo"),
        "AssumeRolePolicyDocument": Match.object_like({
            "Statement": Match.array_with([
                Match.object_like({"Principal": {"AWS": Match.any_value()}}),
                Match.object_like({"Principal": {"AWS": {"Fn::GetAtt": Match.any_value()}}}),
            ]),
        }),
    }))
    tj = t.to_json()
    for resource in tj["Resources"].values():
        if resource["Type"] == "AWS::IAM::Role" and resource["Properties"].get("RoleName") == name("role-agent", "demo"):
            assert len(resource["Properties"]["AssumeRolePolicyDocument"]["Statement"]) == 2
            break
    else:
        raise AssertionError("SentinelRole not found in template")


def test_ci_role_can_mint_bedrock_api_keys_for_mantle():
    t = _template()
    t.has_resource_properties("AWS::IAM::Policy", Match.object_like({
        "PolicyDocument": {"Statement": Match.array_with([Match.object_like({
            "Sid": "Bedrock",
            "Action": Match.array_with(["bedrock:CallWithBearerToken"]),
        })])},
    }))


def test_standard_tags_on_taggable_resources():
    t = _template()
    expected = [{"Key": k, "Value": v} for k, v in STANDARD_TAGS.items()]
    for resource_type in ("AWS::EC2::Instance", "AWS::IAM::Role", "AWS::Logs::LogGroup", "AWS::CloudWatch::Alarm"):
        t.has_resource_properties(resource_type, Match.object_like({"Tags": Match.array_with(expected)}))


def test_instances_have_no_public_ip_and_no_open_egress():
    t = _template()
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


def test_outputs_are_exactly_the_five_expected():
    t = _template()
    assert set(t.to_json()["Outputs"].keys()) == {
        "DevInstanceId", "ProdInstanceId", "SentinelRoleArn", "CiRoleArn", "LogGroupName",
    }


def test_alarm_thresholds_and_breaching_behavior():
    t = _template()
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
