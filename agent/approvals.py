"""Layer 4, rebuilt after the Well-Architected review (AGENTSEC04-BP02, WAR finding L02).

Before: the stop tool accepted any ticket in a static list whose default (CHG-2231) is printed in the public
README. Now a human mints a single-use approval bound to one instance, one action and a short expiry; the tool
consumes it with one conditional DeleteItem. IAM makes the split real: only the operator can PutItem, the agent
role can only DeleteItem, so a manipulated agent cannot approve itself.

Mint from the laptop (operator credentials, never the agent role):
    uv run --env-file .env python -m agent.approvals <instance-id> [--minutes 15]
"""

import argparse
import os
import secrets
import sys
import time

TABLE = os.environ.get("APPROVALS_TABLE", "aws-cdarg-sentinel-approvals-demo")
ACTION = "stop"


def mint(ddb, instance_id: str, minutes: int = 15, now: float | None = None) -> str:
    ticket = f"CHG-{secrets.token_hex(4)}"
    expires = int((now or time.time()) + minutes * 60)
    ddb.put_item(
        TableName=TABLE,
        Item={"ticket": {"S": ticket}, "instance_id": {"S": instance_id}, "action": {"S": ACTION},
              "expires_at": {"N": str(expires)}},
        ConditionExpression="attribute_not_exists(ticket)",
    )
    return ticket


def consume(ddb, ticket: str, instance_id: str, now: float | None = None) -> bool:
    """True once for a live approval of exactly this instance and action; False for anything else.

    Consumed before the EC2 call on purpose: if StopInstances then fails (IAM deny, throttling), the approval is
    already spent and a person mints a new one. Fail closed: a ticket never survives to be replayed."""
    try:
        ddb.delete_item(
            TableName=TABLE,
            Key={"ticket": {"S": ticket}},
            ConditionExpression="instance_id = :i AND #a = :a AND expires_at > :now",
            ExpressionAttributeNames={"#a": "action"},  # ACTION is a DynamoDB reserved word
            ExpressionAttributeValues={":i": {"S": instance_id}, ":a": {"S": ACTION},
                                       ":now": {"N": str(int(now or time.time()))}},
            ReturnValues="ALL_OLD",
        )
    except ddb.exceptions.ConditionalCheckFailedException:
        return False  # missing, reused, expired, other instance or other action: one indistinguishable refusal
    return True


def main() -> int:
    import boto3

    from agent import config

    p = argparse.ArgumentParser(description="Mint a single-use stop approval for one instance")
    p.add_argument("instance_id")
    p.add_argument("--minutes", type=int, default=15)
    args = p.parse_args()
    config.require_sandbox()
    session = boto3.Session(profile_name=os.environ.get("AWS_PROFILE") or None, region_name=config.REGION)
    config.verify_account(session)
    print(mint(session.client("dynamodb"), args.instance_id, args.minutes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
