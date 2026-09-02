import json

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
    case = Case(name="q1", input="hola")
    result = task(case)

    assert result["output"] == "respuesta a hola"
    assert result["trajectory"].session_id == case.session_id
    assert fake.in_memory_exporter.cleared == 1
    assert json.loads((tmp_path / "q1.json").read_text())["session_id"] == case.session_id
