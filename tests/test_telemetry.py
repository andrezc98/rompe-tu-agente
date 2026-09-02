import json

import pytest
from strands_evals import Case

from evals import telemetry


class _FakeSpanExporter:
    def __init__(self):
        self.cleared = 0
    def clear(self):
        self.cleared += 1
    def get_finished_spans(self):
        return []


class _FakeTelemetry:
    def __init__(self):
        self.in_memory_exporter = _FakeSpanExporter()


class _FakeSession:
    def __init__(self, session_id):
        self.session_id = session_id
    def model_dump_json(self, indent=2):
        return json.dumps({"session_id": self.session_id, "spans": []}, indent=indent)


def test_task_returns_output_and_trajectory(monkeypatch, tmp_path):
    fake = _FakeTelemetry()
    monkeypatch.setattr(telemetry, "telemetry", lambda: fake)
    monkeypatch.setattr(telemetry, "make_sentinel", lambda **kw: (lambda q: f"respuesta a {q}"))
    monkeypatch.setattr(telemetry, "map_session", lambda spans, session_id: _FakeSession(session_id))

    task = telemetry.make_task("v2", sessions_dir=tmp_path)
    assert fake.in_memory_exporter.cleared == 1

    case1 = Case(name="q1", input="hola")
    case2 = Case(name="q2", input="mundo")
    case3 = Case(name="q3|baseline", input="chau")
    result1 = task(case1)
    result2 = task(case2)
    result3 = task(case3)

    assert result1["output"] == "respuesta a hola"
    assert result2["output"] == "respuesta a mundo"
    assert result1["trajectory"].session_id == case1.session_id
    assert result2["trajectory"].session_id == case2.session_id
    assert fake.in_memory_exporter.cleared == 1
    assert json.loads((tmp_path / "q1.json").read_text())["session_id"] == case1.session_id
    assert json.loads((tmp_path / "q2.json").read_text())["session_id"] == case2.session_id
    # Chaos case names contain "|" (ChaosCase.expand); the saved filename must not.
    assert json.loads((tmp_path / "q3__baseline.json").read_text())["session_id"] == case3.session_id


def test_judge_model_refuses_without_sandbox_profile(monkeypatch):
    # judge_model builds a BedrockModel on the ambient credential chain; evals.diagnose and
    # evals.chaos both reach AWS through it, so the guard belongs here, not in each caller.
    monkeypatch.setenv("JUDGE_MODEL_ID", "dummy.judge")
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    with pytest.raises(RuntimeError, match="sandbox"):
        telemetry.judge_model()
