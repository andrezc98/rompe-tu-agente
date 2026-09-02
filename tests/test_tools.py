from datetime import datetime, timezone

import boto3
import pytest
from botocore.stub import ANY, Stubber

from agent import tools


@pytest.fixture(autouse=True)
def _isolate_clients(monkeypatch):
    monkeypatch.setenv("AWS_PROFILE", "test-sandbox")
    tools.CLIENTS.clear()
    yield
    tools.CLIENTS.clear()


def _stub(service):
    client = boto3.client(service, region_name="us-east-1",
                          aws_access_key_id="x", aws_secret_access_key="y")
    stubber = Stubber(client)
    tools.CLIENTS[service] = client
    return stubber


def test_get_alarms_returns_flat_list():
    stubber = _stub("cloudwatch")
    stubber.add_response(
        "describe_alarms",
        {"MetricAlarms": [{"AlarmName": "aws-cdarg-sentinel-alarm-dev", "StateValue": "ALARM",
                           "StateReason": "Threshold Crossed", "MetricName": "CPUUtilization"}]},
        {"StateValue": "ALARM"},
    )
    with stubber:
        result = tools.get_alarms(state="ALARM")
    assert result == {"alarms": [{"name": "aws-cdarg-sentinel-alarm-dev", "state": "ALARM",
                                  "reason": "Threshold Crossed", "metric": "CPUUtilization"}]}


def test_get_metric_returns_sorted_datapoints():
    stubber = _stub("cloudwatch")
    t1 = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
    t0 = datetime(2026, 9, 1, 9, 55, tzinfo=timezone.utc)
    stubber.add_response(
        "get_metric_statistics",
        {"Datapoints": [{"Timestamp": t1, "Average": 12.5, "Unit": "Percent"},
                        {"Timestamp": t0, "Average": 3.0, "Unit": "Percent"}]},
        {"Namespace": "AWS/EC2", "MetricName": "CPUUtilization",
         "Dimensions": [{"Name": "InstanceId", "Value": "i-dev"}],
         "StartTime": ANY, "EndTime": ANY, "Period": 300, "Statistics": ["Average"]},
    )
    with stubber:
        result = tools.get_metric(instance_id="i-dev", metric="CPUUtilization", minutes=30)
    assert result["instance_id"] == "i-dev"
    assert [p["avg"] for p in result["datapoints"]] == [3.0, 12.5]


def test_get_instances_flattens_tags():
    stubber = _stub("ec2")
    stubber.add_response(
        "describe_instances",
        {"Reservations": [{"Instances": [
            {"InstanceId": "i-dev", "InstanceType": "t4g.nano", "State": {"Name": "running"},
             "Tags": [{"Key": "Name", "Value": "aws-cdarg-sentinel-ec2-dev"}, {"Key": "env", "Value": "dev"}]},
        ]}]},
        {"Filters": [{"Name": "tag:team", "Values": ["pagos"]}]},
    )
    with stubber:
        result = tools.get_instances(tag_key="team", tag_value="pagos")
    assert result == {"instances": [{"InstanceId": "i-dev", "State": "running",
                                     "Type": "t4g.nano", "Name": "aws-cdarg-sentinel-ec2-dev", "env": "dev"}]}


def test_stop_instance_propagates_access_denied():
    stubber = _stub("ec2")
    stubber.add_client_error("stop_instances", service_error_code="UnauthorizedOperation",
                             service_message="You are not authorized to perform this operation.",
                             http_status_code=403)
    with stubber, pytest.raises(Exception, match="UnauthorizedOperation"):
        tools.stop_instance(instance_id="i-prod", ticket="CHG-0001")


def test_stop_instance_reports_state_change():
    stubber = _stub("ec2")
    stubber.add_response(
        "stop_instances",
        {"StoppingInstances": [{"InstanceId": "i-dev",
                                "PreviousState": {"Name": "running"},
                                "CurrentState": {"Name": "stopping"}}]},
        {"InstanceIds": ["i-dev"]},
    )
    with stubber:
        result = tools.stop_instance(instance_id="i-dev", ticket="CHG-2231")
    assert result == {"instance_id": "i-dev", "ticket": "CHG-2231",
                      "previous_state": "running", "current_state": "stopping"}
