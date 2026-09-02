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
                "StringLike": {"token.actions.githubusercontent.com:sub": "repo:owner/repo:*"},
            }),
        })])},
    }))


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
