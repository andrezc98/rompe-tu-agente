"""SentinelDemo: the sandbox the Sentinel agent operates on. Small on purpose; every name follows aws-cdarg-sentinel-<resource>-<env>."""

import aws_cdk as cdk
from aws_cdk import aws_cloudwatch as cw
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_logs as logs
from constructs import Construct

NAMING = "aws-cdarg-sentinel"  # aws-<event>-<codename>; the codename is the agent under test
INSTANCE_TYPE = "m9g.medium"  # Graviton5; use m8g.medium if the region does not offer m9g
BOTTLEROCKET_ARM64 = "/aws/service/bottlerocket/aws-ecs-2/arm64/latest/image_id"
STANDARD_TAGS = {
    # Alphabetical: CDK's TagManager always renders tags sorted by key
    # (aws_cdk.core.TagManager.sortedTags uses localeCompare), regardless of
    # insertion order. Keeping this dict pre-sorted keeps it a 1:1 mirror of
    # what actually lands in the CloudFormation template.
    "Environment": "demo",
    "ManagedBy": "cdk",
    "Owner": "andres-zeballos",
    "Project": "rompe-tu-agente",
}
GITHUB_OIDC = "token.actions.githubusercontent.com"


def name(resource: str, env: str) -> str:
    """The one place resource names are built: aws-cdarg-sentinel-<resource>-<env>."""
    return f"{NAMING}-{resource}-{env}"


class SentinelStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, *, github_repo: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        for key, value in STANDARD_TAGS.items():
            cdk.Tags.of(self).add(key, value)

        vpc = ec2.Vpc(
            self,
            "Vpc",
            vpc_name=name("vpc", "demo"),
            # ponytail: hardcoded single AZ, not max_azs=1. VpcProps says
            # availability_zones and max_azs are mutually exclusive; max_azs
            # triggers a live AVAILABILITY_ZONE_PROVIDER context lookup
            # (an AWS call) whenever the stack env is concrete, which real
            # ambient credentials on the synth machine can satisfy even for
            # an offline `cdk synth`. This repo is us-east-1-only (see
            # agent/config.py REGION default and .env.example), so pinning
            # the AZ literal is correct, not just a synth-time workaround.
            availability_zones=["us-east-1a"],
            nat_gateways=0,
            subnet_configuration=[
                ec2.SubnetConfiguration(name="public", subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=24)
            ],
        )
        image = ec2.MachineImage.from_ssm_parameter(BOTTLEROCKET_ARM64, os=ec2.OperatingSystemType.LINUX)

        instances: dict[str, ec2.Instance] = {}
        for env_name in ("prod", "dev"):
            instance = ec2.Instance(
                self,
                f"Pagos{env_name.capitalize()}",
                instance_name=name("ec2", env_name),
                vpc=vpc,
                vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
                instance_type=ec2.InstanceType(INSTANCE_TYPE),
                machine_image=image,
                associate_public_ip_address=False,
                allow_all_outbound=False,
            )
            cdk.Tags.of(instance).add("team", "pagos")
            cdk.Tags.of(instance).add("env", env_name)
            instances[env_name] = instance

        # Demo alarm: always ALARM while dev runs (CPU is always below 101).
        cw.Alarm(
            self,
            "DevCpuAlarm",
            alarm_name=name("alarm", "dev"),
            alarm_description="Alarma de demo del equipo de pagos",
            metric=cw.Metric(
                namespace="AWS/EC2",
                metric_name="CPUUtilization",
                dimensions_map={"InstanceId": instances["dev"].instance_id},
                statistic="Average",
                period=cdk.Duration.minutes(5),
            ),
            threshold=101,
            comparison_operator=cw.ComparisonOperator.LESS_THAN_THRESHOLD,
            evaluation_periods=1,
            treat_missing_data=cw.TreatMissingData.BREACHING,  # ALARM from the first period, not INSUFFICIENT_DATA
        )

        log_group = logs.LogGroup(
            self,
            "AgentLogs",
            log_group_name=name("logs", "demo"),
            retention=logs.RetentionDays.TWO_WEEKS,
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        # --- CI role: GitHub OIDC, scoped to this repo ---
        provider = iam.OpenIdConnectProvider(
            self, "GitHubOidc", url=f"https://{GITHUB_OIDC}", client_ids=["sts.amazonaws.com"]
        )
        ci_role = iam.Role(
            self,
            "CiRole",
            role_name=name("role-ci", "demo"),
            assumed_by=iam.OpenIdConnectPrincipal(provider).with_conditions(
                {
                    "StringEquals": {f"{GITHUB_OIDC}:aud": "sts.amazonaws.com"},
                    "StringLike": {f"{GITHUB_OIDC}:sub": f"repo:{github_repo}:*"},
                }
            ),
        )

        # --- sentinel-agent: the principal the tools run as. The Deny is the whole point. ---
        sentinel_role = iam.Role(
            self,
            "SentinelRole",
            role_name=name("role-agent", "demo"),
            assumed_by=iam.CompositePrincipal(iam.AccountRootPrincipal(), ci_role),
        )
        sentinel_role.add_to_policy(
            iam.PolicyStatement(
                sid="Read",
                actions=["cloudwatch:DescribeAlarms", "cloudwatch:GetMetricStatistics", "ec2:DescribeInstances"],
                resources=["*"],
            )
        )
        sentinel_role.add_to_policy(iam.PolicyStatement(sid="StopAny", actions=["ec2:StopInstances"], resources=["*"]))
        sentinel_role.add_to_policy(
            iam.PolicyStatement(
                sid="NeverProd",
                effect=iam.Effect.DENY,
                actions=["ec2:StopInstances"],
                resources=["*"],
                conditions={"StringEquals": {"ec2:ResourceTag/env": "prod"}},
            )
        )

        ci_role.add_to_policy(
            iam.PolicyStatement(
                sid="Bedrock",
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                    "bedrock:Converse",
                    "bedrock:ConverseStream",
                    "bedrock:CallWithBearerToken",
                ],
                resources=["*"],
            )
        )
        ci_role.add_to_policy(
            iam.PolicyStatement(sid="AssumeSentinel", actions=["sts:AssumeRole"], resources=[sentinel_role.role_arn])
        )
        ci_role.add_to_policy(
            iam.PolicyStatement(
                sid="Telemetry",
                actions=[
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "logs:DescribeLogGroups",
                    "logs:DescribeLogStreams",
                    "xray:PutTraceSegments",
                    "xray:PutSpans",
                    "xray:PutSpansForIndexing",
                ],
                resources=["*"],
            )
        )

        cdk.CfnOutput(self, "DevInstanceId", value=instances["dev"].instance_id)
        cdk.CfnOutput(self, "ProdInstanceId", value=instances["prod"].instance_id)
        cdk.CfnOutput(self, "SentinelRoleArn", value=sentinel_role.role_arn)
        cdk.CfnOutput(self, "CiRoleArn", value=ci_role.role_arn)
        cdk.CfnOutput(self, "LogGroupName", value=log_group.log_group_name)
