import pytest

from agent import config


def test_require_sandbox_refuses_default_profile(monkeypatch):
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    with pytest.raises(RuntimeError, match="sandbox"):
        config.require_sandbox()


def test_require_sandbox_accepts_sandbox_profile(monkeypatch):
    monkeypatch.setenv("AWS_PROFILE", "awsbyandres-sandbox")
    config.require_sandbox()


def test_require_sandbox_accepts_ci(monkeypatch):
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    config.require_sandbox()


def test_model_id_requires_env(monkeypatch):
    monkeypatch.delenv("TARGET_MODEL_ID", raising=False)
    with pytest.raises(RuntimeError, match="TARGET_MODEL_ID"):
        config.model_id("target")
    monkeypatch.setenv("JUDGE_MODEL_ID", "x.judge")
    monkeypatch.setenv("ATTACKER_MODEL_ID", "openai.gpt-x")
    assert config.model_id("judge") == "x.judge"
    assert config.model_id("attacker") == "openai.gpt-x"


def test_mantle_base_url_uses_region(monkeypatch):
    monkeypatch.setattr(config, "REGION", "us-east-2")
    assert config.mantle_base_url() == "https://bedrock-mantle.us-east-2.api.aws/openai/v1"


def test_bedrock_api_key_mints_short_term_token(monkeypatch):
    monkeypatch.setattr(config, "REGION", "us-east-1")
    monkeypatch.setattr(config, "_provide_token", lambda region: f"bedrock-api-key-{region}")
    assert config.bedrock_api_key() == "bedrock-api-key-us-east-1"
