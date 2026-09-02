"""Environment-driven configuration and the one guard that protects the wrong AWS account."""

import os

from aws_bedrock_token_generator import provide_token as _provide_token

REGION = os.environ.get("AWS_REGION", "us-east-1")

# target and judge are Claude inference profiles on Bedrock; attacker is GPT on Bedrock Mantle
_MODEL_ENV = {"target": "TARGET_MODEL_ID", "judge": "JUDGE_MODEL_ID", "attacker": "ATTACKER_MODEL_ID"}


def require_sandbox() -> None:
    """Refuse to touch AWS unless the personal sandbox profile or CI OIDC is in use."""
    if os.environ.get("GITHUB_ACTIONS") == "true":
        return
    profile = os.environ.get("AWS_PROFILE", "")
    if "sandbox" not in profile:
        raise RuntimeError(
            "AWS_PROFILE must be the personal sandbox profile (name contains 'sandbox'); "
            "refusing to use default credentials"
        )


def model_id(kind: str) -> str:
    key = _MODEL_ENV[kind]
    value = os.environ.get(key)
    if not value:
        raise RuntimeError(f"{key} not set; run scripts/pin-models.sh and export the ids")
    return value


def agent_role_arn() -> str | None:
    """IAM role the tools assume. None means run tools with the caller's own credentials."""
    return os.environ.get("SENTINEL_ROLE_ARN") or None


def mantle_base_url() -> str:
    """OpenAI-compatible Bedrock endpoint. GPT models live on the /openai/v1 path (model card, 2026-09-01)."""
    return f"https://bedrock-mantle.{REGION}.api.aws/openai/v1"


def bedrock_api_key() -> str:
    """Short-term Bedrock API key (up to 12 h) minted from the current AWS credentials; never stored."""
    require_sandbox()
    return _provide_token(region=REGION)
