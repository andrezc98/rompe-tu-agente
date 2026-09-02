"""In-memory OpenTelemetry capture around one agent run, so trace-level evaluators get a Session."""

from collections.abc import Callable
from pathlib import Path

from strands.models import BedrockModel
from strands.models.openai_responses import OpenAIResponsesModel
from strands_evals import Case
from strands_evals.mappers import StrandsInMemorySessionMapper
from strands_evals.telemetry import StrandsEvalsTelemetry
from strands_evals.types.trace import Session

from agent import config
from agent.sentinel import make_sentinel

SESSIONS_DIR = Path(__file__).resolve().parent / "results" / "sessions"

_telemetry: StrandsEvalsTelemetry | None = None


def telemetry() -> StrandsEvalsTelemetry:
    global _telemetry
    if _telemetry is None:
        _telemetry = StrandsEvalsTelemetry().setup_in_memory_exporter()
    return _telemetry


def map_session(spans, session_id: str) -> Session:
    return StrandsInMemorySessionMapper().map_to_session(spans, session_id=session_id)


def save_session(session: Session, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(session.model_dump_json(indent=2))


def load_session(path: Path) -> Session:
    return Session.model_validate_json(path.read_text())


def judge_model() -> BedrockModel:
    # Builds a Bedrock client on the ambient credential chain, so it is a place AWS gets touched.
    config.require_sandbox()
    return BedrockModel(model_id=config.model_id("judge"), region_name=config.REGION)  # no temperature: see agent/sentinel.py


def attacker_model() -> OpenAIResponsesModel:
    """GPT on Bedrock Mantle. The key is short-term (max 12 h): mint it per process, never persist it."""
    return OpenAIResponsesModel(
        model_id=config.model_id("attacker"),
        client_args={"api_key": config.bedrock_api_key(), "base_url": config.mantle_base_url()},
    )


def make_task(
    prompt_version: str,
    plugins_factory: Callable[[], list] = list,
    sessions_dir: Path = SESSIONS_DIR,
) -> Callable[[Case], dict]:
    # Clear once per experiment, not per case: a per-case clear races concurrent workers and drops spans (strands_evals.cli._agent_task); map_session filters the shared buffer by session_id instead.
    telemetry().in_memory_exporter.clear()

    def task(case: Case) -> dict:
        agent = make_sentinel(prompt_version=prompt_version, plugins=plugins_factory(), session_id=case.session_id)
        response = agent(case.input)
        spans = telemetry().in_memory_exporter.get_finished_spans()
        session = map_session(spans, case.session_id)
        # Chaos case names are "<base>|<condition>" (ChaosCase.expand); "|" breaks shell globs/quoting on stage.
        save_session(session, sessions_dir / f"{case.name.replace('|', '__')}.json")
        return {"output": str(response), "trajectory": session}

    return task
