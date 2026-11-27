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
    monkeypatch.setenv("AWS_PROFILE", "test-sandbox")
    monkeypatch.setattr(config, "REGION", "us-east-1")
    monkeypatch.setattr(config, "_provide_token", lambda region: f"bedrock-api-key-{region}")
    assert config.bedrock_api_key() == "bedrock-api-key-us-east-1"


def test_bedrock_api_key_requires_sandbox(monkeypatch):
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)

    def _must_not_be_called(region):
        raise AssertionError("_provide_token must not run outside the sandbox")

    monkeypatch.setattr(config, "_provide_token", _must_not_be_called)
    with pytest.raises(RuntimeError, match="sandbox"):
        config.bedrock_api_key()


def test_require_sandbox_accepts_an_explicitly_named_profile(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setenv("AWS_PROFILE", "fv-lab")
    monkeypatch.setenv("SANDBOX_PROFILE", "fv-lab")
    config.require_sandbox()


class _Sts:
    def __init__(self, account):
        self.account = account

    def get_caller_identity(self):
        return {"Account": self.account}


class _Session:
    def __init__(self, account):
        self._sts = _Sts(account)

    def client(self, service):
        assert service == "sts"
        return self._sts


def test_verify_account_refuses_another_account_even_with_a_sandbox_named_profile(monkeypatch):
    """The incident behind WAR F01: a profile named *-sandbox pointing at someone else's account passed the name check."""
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setenv("SANDBOX_ACCOUNT_ID", "acct-mine")
    with pytest.raises(RuntimeError, match="acct-other"):
        config.verify_account(_Session("acct-other"))
    config.verify_account(_Session("acct-mine"))


def test_verify_account_requires_the_expected_account(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("SANDBOX_ACCOUNT_ID", raising=False)
    with pytest.raises(RuntimeError, match="SANDBOX_ACCOUNT_ID"):
        config.verify_account(_Session("acct-mine"))


def test_verify_account_is_not_skipped_by_a_bare_github_actions_variable(monkeypatch):
    """Exporting GITHUB_ACTIONS=true on a laptop must not turn the account check off (pre-push review)."""
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.delenv("ACTIONS_ID_TOKEN_REQUEST_URL", raising=False)
    monkeypatch.setenv("SANDBOX_ACCOUNT_ID", "acct-mine")
    with pytest.raises(RuntimeError, match="acct-other"):
        config.verify_account(_Session("acct-other"))
