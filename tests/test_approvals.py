import boto3
from botocore.stub import ANY, Stubber

from agent import approvals


def _ddb():
    client = boto3.client("dynamodb", region_name="us-east-1", aws_access_key_id="x", aws_secret_access_key="y")
    return client, Stubber(client)


def test_mint_binds_one_instance_one_action_and_a_short_expiry():
    client, stub = _ddb()
    stub.add_response("put_item", {}, {
        "TableName": approvals.TABLE,
        "Item": {"ticket": {"S": ANY}, "instance_id": {"S": "i-dev"}, "action": {"S": "stop"},
                 "expires_at": {"N": str(1000 + 15 * 60)}},
        "ConditionExpression": "attribute_not_exists(ticket)",
    })
    with stub:
        ticket = approvals.mint(client, "i-dev", now=1000)
    assert ticket.startswith("CHG-") and len(ticket) == 12  # 32 random bits: not guessable, never in the repo


def test_consume_checks_instance_action_and_expiry_server_side():
    client, stub = _ddb()
    stub.add_response("delete_item", {}, {
        "TableName": approvals.TABLE,
        "Key": {"ticket": {"S": "CHG-a1b2c3d4"}},
        "ConditionExpression": "instance_id = :i AND #a = :a AND expires_at > :now",
        "ExpressionAttributeNames": {"#a": "action"},
        "ExpressionAttributeValues": {":i": {"S": "i-dev"}, ":a": {"S": "stop"}, ":now": {"N": "2000"}},
        "ReturnValues": "ALL_OLD",
    })
    with stub:
        assert approvals.consume(client, "CHG-a1b2c3d4", "i-dev", now=2000) is True


def test_consume_refuses_on_failed_condition():
    client, stub = _ddb()
    stub.add_client_error("delete_item", service_error_code="ConditionalCheckFailedException", http_status_code=400)
    with stub:
        assert approvals.consume(client, "CHG-2231", "i-dev") is False
