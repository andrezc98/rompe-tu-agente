"""Environment-driven configuration and the one guard that protects the wrong AWS account."""

import os

from aws_bedrock_token_generator import provide_token as _provide_token

REGION = os.environ.get("AWS_REGION", "us-east-1")

# target and judge are Claude inference profiles on Bedrock; attacker is GPT on Bedrock Mantle
_MODEL_ENV = {
    "target": "TARGET_MODEL_ID",
    "judge": "JUDGE_MODEL_ID",
    "attacker": "ATTACKER_MODEL_ID",
    "redteam_judge": "REDTEAM_JUDGE_MODEL_ID",  # judge for attack transcripts; falls back to JUDGE_MODEL_ID
}


def require_sandbox() -> None:
    """Refuse to touch AWS unless a named sandbox profile or CI OIDC is in use. A name is only a first filter:
    verify_account() checks the real account before anything acts (WAR F01)."""
    if os.environ.get("GITHUB_ACTIONS") == "true":
        return
    profile = os.environ.get("AWS_PROFILE", "")
    if not profile or ("sandbox" not in profile and profile != os.environ.get("SANDBOX_PROFILE")):
        raise RuntimeError(
            "AWS_PROFILE must be the personal sandbox profile (name contains 'sandbox', or equals SANDBOX_PROFILE); "
            "refusing to use default credentials"
        )


def verify_account(session) -> None:
    """WAR F01 (SEC03-BP01): the profile name proved nothing. A `*-sandbox` profile pointing at another team's
    account passed the name check during this review; now the caller's real account must equal SANDBOX_ACCOUNT_ID."""
    if os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL"):
        return  # real GitHub Actions with OIDC: it holds only roles that exist in the sandbox account
    expected = os.environ.get("SANDBOX_ACCOUNT_ID")
    if not expected:
        raise RuntimeError("SANDBOX_ACCOUNT_ID is not set: refusing to act on an account nobody named")
    actual = session.client("sts").get_caller_identity()["Account"]
    if actual != expected:
        raise RuntimeError(f"credentials belong to account {actual}, not the sandbox {expected}: refusing")


def model_id(kind: str) -> str:
    key = _MODEL_ENV[kind]
    value = os.environ.get(key)
    if not value and kind == "redteam_judge":
        return model_id("judge")
    if not value:
        raise RuntimeError(f"{key} not set; run scripts/pin-models.sh and export the ids")
    return value


def agent_role_arn() -> str | None:
    """IAM role the tools assume. Required: agent/tools.py refuses to run without it (WAR F01)."""
    return os.environ.get("SENTINEL_ROLE_ARN") or None


def mantle_base_url() -> str:
    """OpenAI-compatible Bedrock endpoint. GPT models live on the /openai/v1 path (model card, 2026-09-01)."""
    return f"https://bedrock-mantle.{REGION}.api.aws/openai/v1"


def bedrock_api_key() -> str:
    """Short-term Bedrock API key (up to 12 h) minted from the current AWS credentials; never stored."""
    require_sandbox()
    return _provide_token(region=REGION)
