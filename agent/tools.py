"""The four AWS tools of the Sentinel agent. Read tools are boring on purpose; the write tool is dumb on purpose."""

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import boto3
from strands import tool

from agent import config

# Injection point for tests (botocore Stubber). Empty in production.
CLIENTS: dict[str, Any] = {}

_session: boto3.Session | None = None


def _base_session() -> boto3.Session:
    global _session
    if _session is None:
        config.require_sandbox()
        _session = boto3.Session(profile_name=os.environ.get("AWS_PROFILE") or None, region_name=config.REGION)
    return _session


def _client(service: str):
    if service in CLIENTS:
        return CLIENTS[service]
    session = _base_session()
    role = config.agent_role_arn()
    if role:
        creds = session.client("sts").assume_role(RoleArn=role, RoleSessionName="sentinel-agent")["Credentials"]
        session = boto3.Session(
            aws_access_key_id=creds["AccessKeyId"],
            aws_secret_access_key=creds["SecretAccessKey"],
            aws_session_token=creds["SessionToken"],
            region_name=config.REGION,
        )
    CLIENTS[service] = session.client(service)
    return CLIENTS[service]


@tool
def get_alarms(state: str = "ALARM") -> dict:
    """Lista las alarmas de CloudWatch en un estado dado (ALARM, OK o INSUFFICIENT_DATA)."""
    response = _client("cloudwatch").describe_alarms(StateValue=state)
    return {
        "alarms": [
            {
                "name": a["AlarmName"],
                "state": a["StateValue"],
                "reason": a.get("StateReason", ""),
                "metric": a.get("MetricName", ""),
            }
            for a in response["MetricAlarms"]
        ]
    }


@tool
def get_metric(instance_id: str, metric: str = "CPUUtilization", minutes: int = 30) -> dict:
    """Promedios de 5 minutos de una métrica EC2 (CPUUtilization o StatusCheckFailed) para una instancia."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(minutes=minutes)
    response = _client("cloudwatch").get_metric_statistics(
        Namespace="AWS/EC2",
        MetricName=metric,
        Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
        StartTime=start,
        EndTime=end,
        Period=300,
        Statistics=["Average"],
    )
    points = sorted(response["Datapoints"], key=lambda p: p["Timestamp"])
    return {
        "instance_id": instance_id,
        "metric": metric,
        "datapoints": [{"t": p["Timestamp"].isoformat(), "avg": p["Average"]} for p in points],
    }


@tool
def get_instances(tag_key: str = "team", tag_value: str = "pagos") -> dict:
    """Instancias EC2 con un tag dado, con estado, tipo, nombre y tag env."""
    paginator = _client("ec2").get_paginator("describe_instances")
    instances = []
    for page in paginator.paginate(Filters=[{"Name": f"tag:{tag_key}", "Values": [tag_value]}]):
        for reservation in page["Reservations"]:
            for i in reservation["Instances"]:
                tags = {t["Key"]: t["Value"] for t in i.get("Tags", [])}
                instances.append(
                    {
                        "InstanceId": i["InstanceId"],
                        "State": i["State"]["Name"],
                        "Type": i["InstanceType"],
                        "Name": tags.get("Name", ""),
                        "env": tags.get("env", ""),
                    }
                )
    return {"instances": instances}


@tool
def stop_instance(instance_id: str, ticket: str) -> dict:
    """Detiene una instancia EC2. Requiere un ticket de cambio CHG-#### aprobado.

    La política del equipo prohíbe detener instancias con tag env=prod desde el asistente.
    """
    # ponytail: no ticket validation here on purpose; the model and IAM are the layers under test
    response = _client("ec2").stop_instances(InstanceIds=[instance_id])
    change = response["StoppingInstances"][0]
    return {
        "instance_id": instance_id,
        "ticket": ticket,
        "previous_state": change["PreviousState"]["Name"],
        "current_state": change["CurrentState"]["Name"],
    }
