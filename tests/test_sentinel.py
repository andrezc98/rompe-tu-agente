import pytest

from agent import sentinel


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("AWS_PROFILE", "test-sandbox")
    monkeypatch.setenv("TARGET_MODEL_ID", "dummy.model")
    monkeypatch.setenv("AWS_REGION", "us-east-1")


def test_prompt_versions_differ_only_in_style_block():
    v1 = (sentinel.PROMPTS / "v1.md").read_text()
    v2 = (sentinel.PROMPTS / "v2.md").read_text()
    assert "Nunca digas que no sabes" in v1
    assert "Nunca digas que no sabes" not in v2
    assert v1.split("Estilo:")[0] == v2.split("Estilo:")[0]


def test_make_sentinel_wires_all_tools():
    agent = sentinel.make_sentinel("v2")
    assert set(sentinel.TOOL_NAMES) <= set(agent.tool_names)
    assert "Nunca digas que no sabes" not in agent.system_prompt


def test_agent_factory_reads_current():
    assert sentinel.current_prompt_version() == "v2"
    agent = sentinel.agent_factory()
    assert "no completes con suposiciones" in agent.system_prompt


def test_make_sentinel_refuses_without_sandbox_profile(monkeypatch):
    # The target BedrockModel is built inside make_sentinel, on the ambient credential chain:
    # without the sandbox profile (or CI OIDC) it must refuse before any client exists.
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    with pytest.raises(RuntimeError, match="sandbox"):
        sentinel.make_sentinel("v2")
