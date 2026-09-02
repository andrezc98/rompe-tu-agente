import subprocess
import sys

from evals import chaos


def test_effect_maps_isolate_one_failure_mode_each():
    assert list(chaos.EFFECT_MAPS) == [
        "metric_timeout", "alarms_down", "instances_truncated", "metric_silent", "stop_fails",
    ]
    for name, effect_map in chaos.EFFECT_MAPS.items():
        tools_hit = effect_map["tool_effects"]
        assert len(tools_hit) == 1, name
        assert all(len(v) == 1 for v in tools_hit.values()), name


def test_build_cases_expands_with_baseline_and_repeats():
    cases = chaos.build_cases(repeats=3)
    # 3 questions x 3 repeats x (5 effects + baseline)
    assert len(cases) == 54
    names = [c.name for c in cases]
    assert len(set(names)) == 54
    assert any("q1-r1" in n for n in names)


def test_cli_refuses_without_models(monkeypatch):
    monkeypatch.delenv("TARGET_MODEL_ID", raising=False)
    monkeypatch.setenv("AWS_PROFILE", "test-sandbox")
    proc = subprocess.run([sys.executable, "-m", "evals.chaos", "--prompt", "v2", "--repeats", "1",
                           "--out", "/dev/null"], capture_output=True, text=True)
    assert proc.returncode != 0
    assert "TARGET_MODEL_ID" in proc.stderr
