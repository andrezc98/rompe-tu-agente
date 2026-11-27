"""Claude Mythos and GPT Daybreak as Strands models, through the local CLIs of personal subscriptions.

Each model call is one stateless CLI call: the system
prompt and the whole conversation are rendered into one prompt. Structured output (how the red-team strategies
talk to their attacker) arrives in Strands as a forced tool call; we ask the CLI for JSON matching the tool's
schema and hand it back as that tool call. Never runs in CI: the subscriptions live on the speaker's laptop.
"""

import asyncio
import json
import os
import re
import subprocess
import tempfile
import uuid
from collections.abc import AsyncIterable, Callable
from typing import Any

from strands.models.model import Model

MYTHOS = "claude-mythos-5-2"
DAYBREAK = "gpt-6-sol"  # with -c daybreak=true


class AttackerRefused(Exception):
    """Empty, non-JSON or refusing CLI output: recorded as an attacker refusal, never as a defence."""


def _run(cmd: list[str], prompt: str = "", isolate_home: bool = False) -> str:
    """Run one attacker CLI call. The prompt goes on stdin (long conversations would hit ARG_MAX as an argument).

    Limits, stated plainly: the attacker only needs to write text. It gets an empty cwd and an environment without
    AWS/GitHub variables; Claude runs with no tools at all; Codex runs read-only with an empty HOME (CODEX_HOME keeps
    its own login) and browser/computer use off, but its shell can still read files by absolute path. Run attackers
    on a machine whose readable files you accept a red-team model seeing."""
    if os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"):
        raise RuntimeError("Mythos/Daybreak run locally only (personal subscriptions)")
    env = {k: v for k, v in os.environ.items() if not k.startswith(("AWS_", "GITHUB_", "GH_", "SENTINEL_"))}
    with tempfile.TemporaryDirectory() as cwd:
        if isolate_home:
            env["CODEX_HOME"] = os.environ.get("CODEX_HOME") or os.path.expanduser("~/.codex")
            env["HOME"] = cwd
        r = subprocess.run(cmd, cwd=cwd, env=env, input=prompt, capture_output=True, text=True, timeout=300,
                           check=False)
    if r.returncode != 0:  # auth, quota or crash: operational, not a refusal
        raise RuntimeError(f"{cmd[0]} exited {r.returncode}: {(r.stderr.strip() or r.stdout.strip())[-500:]}")
    return r.stdout


def parse_claude(stdout: str) -> str:
    line = next((x for x in stdout.splitlines() if x.startswith("{")), "")
    try:
        env = json.loads(line)
    except json.JSONDecodeError as e:
        raise AttackerRefused(stdout[:200]) from e
    if env.get("is_error") or not env.get("result"):
        raise AttackerRefused(str(env.get("result"))[:200])
    return env["result"]


def parse_codex(stdout: str) -> str:
    texts = []
    for line in stdout.splitlines():
        if line.startswith("{"):
            ev = json.loads(line)
            item = ev.get("item") or {}
            if ev.get("type") == "item.completed" and item.get("type") == "agent_message":
                texts.append(item.get("text", ""))
    if not texts:
        raise AttackerRefused(stdout[-200:])
    return texts[-1]


def mythos_run(prompt: str) -> str:
    # --tools "" and --strict-mcp-config: no built-in tools and no MCP servers, so a prompt cannot induce tool use
    cmd = ["claude", "-p", "--model", MYTHOS, "--output-format", "json", "--tools", "", "--strict-mcp-config"]
    return parse_claude(_run(cmd, prompt))


def daybreak_run(prompt: str) -> str:
    cmd = ["codex", "exec", "-m", DAYBREAK, "-c", "daybreak=true", "-s", "read-only", "--ephemeral", "--json",
           "--skip-git-repo-check", "--disable", "browser_use", "--disable", "computer_use", "-"]  # "-": prompt on stdin
    return parse_codex(_run(cmd, prompt, isolate_home=True))


def _render(messages: list[dict], system_prompt: str | None) -> str:
    parts = [f"# Instructions\n{system_prompt}"] if system_prompt else []
    for m in messages:
        for block in m.get("content", []):
            if "text" in block:
                parts.append(f"## {m['role']}\n{block['text']}")
            elif "toolUse" in block:
                parts.append(f"## {m['role']} (structured reply)\n{json.dumps(block['toolUse'].get('input'))}")
            elif "toolResult" in block:
                parts.append(f"## tool result\n{json.dumps(block['toolResult'].get('content'), default=str)}")
    return "\n\n".join(parts)


def _json_object(text: str) -> dict:
    body = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        out = json.loads(body)
    except json.JSONDecodeError as e:
        raise AttackerRefused(text[:200]) from e
    if not isinstance(out, dict):
        raise AttackerRefused(text[:200])
    return out


class CliModel(Model):
    def __init__(self, model_id: str, run: Callable[[str], str]):
        self.config: dict[str, Any] = {"model_id": model_id}
        self._run = run

    def update_config(self, **model_config: Any) -> None:
        self.config.update(model_config)

    def get_config(self) -> dict[str, Any]:
        return self.config

    def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):  # pragma: no cover
        raise NotImplementedError("Strands drives structured output through stream() tool calls")

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs: Any) -> AsyncIterable[dict]:
        prompt = _render(messages, system_prompt)
        yield {"messageStart": {"role": "assistant"}}
        if tool_specs:  # the strategies only ever pass the one structured-output tool
            spec = tool_specs[0]
            schema = json.dumps(spec["inputSchema"].get("json", spec["inputSchema"]))
            prompt += f"\n\nReply with only one JSON object that matches this JSON schema, nothing else:\n{schema}"
            args = _json_object(await asyncio.to_thread(self._run, prompt))  # off the loop: --workers stay parallel
            yield {"contentBlockStart": {"start": {"toolUse": {"toolUseId": uuid.uuid4().hex, "name": spec["name"]}}}}
            yield {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(args)}}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "tool_use"}}
            return
        yield {"contentBlockDelta": {"delta": {"text": await asyncio.to_thread(self._run, prompt)}}}
        yield {"contentBlockStop": {}}
        yield {"messageStop": {"stopReason": "end_turn"}}


def mythos() -> CliModel:
    return CliModel(MYTHOS, mythos_run)


def daybreak() -> CliModel:
    return CliModel(f"{DAYBREAK}+daybreak", daybreak_run)
