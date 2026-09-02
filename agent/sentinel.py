"""Sentinel: the on-call assistant under test. One factory, two prompt versions."""

from pathlib import Path

from strands import Agent
from strands.models import BedrockModel

from agent import config
from agent.shell_tool import run_shell
from agent.tools import get_alarms, get_instances, get_metric, stop_instance

PROMPTS = Path(__file__).resolve().parent / "prompts"
TOOLS = [get_alarms, get_metric, get_instances, stop_instance, run_shell]
TOOL_NAMES = ["get_alarms", "get_metric", "get_instances", "stop_instance", "run_shell"]


def current_prompt_version() -> str:
    return (PROMPTS / "CURRENT").read_text().strip()


def make_sentinel(
    prompt_version: str | None = None,
    plugins: list | None = None,
    session_id: str | None = None,
) -> Agent:
    version = prompt_version or current_prompt_version()
    model = BedrockModel(model_id=config.model_id("target"), region_name=config.REGION, temperature=0.0)
    kwargs: dict = {
        "model": model,
        "system_prompt": (PROMPTS / f"{version}.md").read_text(),
        "tools": TOOLS,
        "callback_handler": None,
    }
    if plugins:
        kwargs["plugins"] = plugins
    if session_id:
        kwargs["trace_attributes"] = {"session.id": session_id, "gen_ai.conversation.id": session_id}
    return Agent(**kwargs)


def agent_factory() -> Agent:
    """Zero-arg factory for Strands Evals red teaming (fresh agent per worker)."""
    return make_sentinel()
