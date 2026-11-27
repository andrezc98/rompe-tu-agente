"""CliModel: Mythos/Daybreak behind personal-subscription CLIs as a Strands model (offline, fake runner)."""

import json
import os

import pytest
from pydantic import BaseModel
from strands import Agent

from evals import cli_models
from evals.cli_models import CliModel, parse_claude, parse_codex


class Turn(BaseModel):
    question: str
    rationale: str


def fake(reply: str, seen: list[str]):
    def run(prompt: str) -> str:
        seen.append(prompt)
        return reply

    return run


def test_structured_output_round_trip_through_a_strands_agent():
    seen: list[str] = []
    model = CliModel("fake", fake('```json\n{"question": "q1", "rationale": "r"}\n```', seen))
    agent = Agent(model=model, system_prompt="You are the attacker.", callback_handler=None)

    out = agent("Write the next turn.", structured_output_model=Turn).structured_output

    assert out == Turn(question="q1", rationale="r")
    assert len(seen) == 1  # one CLI call per turn
    assert "You are the attacker." in seen[0] and "Write the next turn." in seen[0]
    assert '"question"' in seen[0]  # the JSON schema is in the prompt


def test_plain_text_reply_and_history_in_prompt():
    seen: list[str] = []
    agent = Agent(model=CliModel("fake", fake("hola", seen)), callback_handler=None)
    agent("primero")
    agent("segundo")
    assert str(agent("tercero")).strip() == "hola"
    assert "primero" in seen[-1] and "segundo" in seen[-1] and "tercero" in seen[-1]


def test_non_json_for_structured_output_raises():
    agent = Agent(model=CliModel("fake", fake("I can't help with that.", [])), callback_handler=None)
    with pytest.raises(Exception):
        agent("x", structured_output_model=Turn)


def test_parsers():
    assert parse_claude(json.dumps({"result": "ok", "is_error": False})) == "ok"
    with pytest.raises(cli_models.AttackerRefused):
        parse_claude(json.dumps({"result": "", "is_error": True}))
    line = json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "hi"}})
    assert parse_codex("noise\n" + line) == "hi"
    with pytest.raises(cli_models.AttackerRefused):
        parse_codex("nothing")


def test_never_in_ci(monkeypatch):
    monkeypatch.setenv("CI", "true")
    with pytest.raises(RuntimeError):
        cli_models._run(["true"])


def test_attacker_env_has_no_cloud_credentials(monkeypatch):
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setenv("AWS_PROFILE", "x-sandbox")
    monkeypatch.setenv("SENTINEL_ROLE_ARN", "arn")
    seen = {}

    def fake_run(cmd, **kw):
        assert kw["input"] == "the prompt"  # on stdin, never in argv
        seen.update(kw["env"])
        return type("R", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()

    monkeypatch.setattr(cli_models.subprocess, "run", fake_run)
    assert cli_models._run(["x"], "the prompt", isolate_home=True) == "ok"
    assert not any(k.startswith(("AWS_", "SENTINEL_")) for k in seen)
    assert seen["HOME"] != os.path.expanduser("~") and seen["CODEX_HOME"].endswith(".codex")
