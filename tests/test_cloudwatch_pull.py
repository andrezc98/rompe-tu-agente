from types import SimpleNamespace

from evals import cloudwatch_pull


def _fake_provider_factory(session_id_seen):
    """Returns a fake CloudWatchProvider class shaped like strands_evals' real one."""

    class _FakeProvider:
        def __init__(self, region=None, log_group=None):
            self.region = region
            self.log_group = log_group

        def get_evaluation_data(self, session_id):
            session_id_seen.append(session_id)
            # Mirrors the real TaskOutput: a dict with "output" (str) and "trajectory"
            # (strands_evals.types.trace.Session: {traces: [Trace, ...]}, spans live per-trace).
            trajectory = SimpleNamespace(traces=[
                SimpleNamespace(spans=[object(), object()]),
                SimpleNamespace(spans=[object()]),
            ])
            return {"output": "la instancia esta en alarma por CPU alta", "trajectory": trajectory}

    return _FakeProvider


def test_main_prints_output_and_span_count(monkeypatch, capsys):
    seen = []
    monkeypatch.setattr(cloudwatch_pull, "CloudWatchProvider", _fake_provider_factory(seen))
    monkeypatch.setenv("AWS_PROFILE", "test-sandbox")
    monkeypatch.setenv("AGENT_LOG_GROUP", "aws-cdarg-sentinel-logs-demo")
    monkeypatch.setattr(cloudwatch_pull.sys, "argv", ["cloudwatch_pull", "session-123"])

    assert cloudwatch_pull.main() == 0

    out = capsys.readouterr().out
    assert "output: la instancia esta en alarma por CPU alta" in out
    assert "spans: 3" in out
    assert seen == ["session-123"]


def test_main_returns_usage_error_without_session_id(monkeypatch, capsys):
    monkeypatch.setattr(cloudwatch_pull.sys, "argv", ["cloudwatch_pull"])

    assert cloudwatch_pull.main() == 2

    assert "usage: python -m evals.cloudwatch_pull SESSION_ID" in capsys.readouterr().err
