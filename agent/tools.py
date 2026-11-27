"""The four AWS tools of the Sentinel agent. Read tools are boring on purpose; the write tool is dumb on purpose."""

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import boto3
from strands import tool

from agent import approvals, config

# Injection point for tests (botocore Stubber). Empty in production.
CLIENTS: dict[str, Any] = {}

_session: boto3.Session | None = None


def _base_session() -> boto3.Session:
    global _session
    if _session is None:
        config.require_sandbox()
        session = boto3.Session(profile_name=os.environ.get("AWS_PROFILE") or None, region_name=config.REGION)
        config.verify_account(session)
        _session = session
    return _session


def _client(service: str):
    if service in CLIENTS:
        return CLIENTS[service]
    session = _base_session()
    role = config.agent_role_arn()
    if not role:  # WAR F01 (SEC03-BP01): the caller's own credentials would skip the agent role's prod Deny
        raise RuntimeError("SENTINEL_ROLE_ARN is not set: the tools only run as the agent role, never as the caller")
    sts = CLIENTS.get("sts") or session.client("sts")
    creds = sts.assume_role(RoleArn=role, RoleSessionName="sentinel-agent")["Credentials"]
    session = boto3.Session(
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"],
        region_name=config.REGION,
    )
    CLIENTS[service] = session.client(service)
    return CLIENTS[service]


@tool
def get_alarms(state: str = "ALARM") -> str:
    """Lista las alarmas de CloudWatch en un estado dado (ALARM, OK o INSUFFICIENT_DATA). Devuelve JSON."""
    response = _client("cloudwatch").describe_alarms(StateValue=state)
    payload = {
        "alarms": {
            a["AlarmName"]: {
                "state": a["StateValue"],
                "reason": a.get("StateReason", ""),
                "metric": a.get("MetricName", ""),
            }
            for a in response["MetricAlarms"]
        }
    }
    return json.dumps(payload, ensure_ascii=False, default=str)


@tool
def get_metric(instance_id: str, metric: str = "CPUUtilization", minutes: int = 30) -> str:
    """Promedios de 5 minutos de una métrica EC2 (CPUUtilization o StatusCheckFailed) para una instancia. Devuelve JSON."""
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
    # Two datapoints sharing the same ISO timestamp would collapse into one key; impossible at the
    # 300s period requested above, so accepted rather than guarded against.
    payload = {
        "instance_id": instance_id,
        "metric": metric,
        "datapoints": {p["Timestamp"].isoformat(): p["Average"] for p in points},
    }
    return json.dumps(payload, ensure_ascii=False, default=str)


@tool
def get_instances(tag_key: str = "team", tag_value: str = "pagos") -> str:
    """Instancias EC2 con un tag dado, con estado, tipo, nombre y tag env. Devuelve JSON."""
    paginator = _client("ec2").get_paginator("describe_instances")
    instances: dict[str, dict] = {}
    for page in paginator.paginate(Filters=[{"Name": f"tag:{tag_key}", "Values": [tag_value]}]):
        for reservation in page["Reservations"]:
            for i in reservation["Instances"]:
                tags = {t["Key"]: t["Value"] for t in i.get("Tags", [])}
                instances[i["InstanceId"]] = {
                    "State": i["State"]["Name"],
                    "Type": i["InstanceType"],
                    "Name": tags.get("Name", ""),
                    "env": tags.get("env", ""),
                }
    return json.dumps({"instances": instances}, ensure_ascii=False, default=str)


@tool
def stop_instance(instance_id: str, ticket: str) -> str:
    """Detiene una instancia EC2. Requiere el ticket de una aprobación humana emitida para esa misma instancia. Devuelve JSON.

    La política del equipo prohíbe detener instancias con tag env=prod desde el asistente.
    """
    # Layer 4. Talk version: a static list of tickets (the default was public in the README). After the
    # Well-Architected review (AGENTSEC04-BP02): a single-use approval a human minted for this instance, consumed
    # here in one conditional delete. The model may still decide to call; it cannot approve itself (IAM: the agent
    # role can delete approvals, never create them). IAM (layer 3) still guards env=prod below.
    if not approvals.consume(_client("dynamodb"), ticket, instance_id):
        raise ValueError(f"no hay una aprobación vigente para el ticket {ticket} sobre {instance_id}: no se detiene")
    response = _client("ec2").stop_instances(InstanceIds=[instance_id])
    change = response["StoppingInstances"][0]
    payload = {
        "instance_id": instance_id,
        "ticket": ticket,
        "previous_state": change["PreviousState"]["Name"],
        "current_state": change["CurrentState"]["Name"],
    }
    return json.dumps(payload, ensure_ascii=False, default=str)
