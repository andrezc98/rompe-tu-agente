import json
import subprocess
import sys

from strands_evals.chaos import ChaosExperiment, RemoveFields, TruncateFields

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


def test_effects_bite_our_payloads():
    # A realistic get_instances JSON payload (agent/tools.py's shape): two instances
    # distinguishable only by their Name tag, State running.
    instances_json = json.dumps({
        "instances": {
            "i-prod": {"State": "running", "Type": "t4g.nano", "Name": "aws-cdarg-sentinel-ec2-prod", "env": "prod"},
            "i-dev": {"State": "running", "Type": "t4g.nano", "Name": "aws-cdarg-sentinel-ec2-dev", "env": "dev"},
        }
    })
    truncated = TruncateFields(max_length=12).apply(json.loads(instances_json))
    for instance in truncated["instances"].values():
        for value in instance.values():
            assert len(value) <= 12
    names = {instance["Name"] for instance in truncated["instances"].values()}
    assert len(names) == 1  # "prod" and "dev" both fall past the 12-char cut: ambiguous

    # A realistic get_metric JSON payload: two datapoints keyed by timestamp.
    metric_json = json.dumps({
        "instance_id": "i-dev",
        "metric": "CPUUtilization",
        "datapoints": {"2026-09-01T09:55:00+00:00": 3.0, "2026-09-01T10:00:00+00:00": 12.5},
    })
    assert RemoveFields(remove_ratio=1.0).apply(json.loads(metric_json)) == {}

    # ChaosPlugin.after_tool_call only corrupts string tool output that parses as a JSON dict —
    # confirm our tools' JSON-string shape satisfies that.
    assert isinstance(json.loads(instances_json), dict)


def test_build_experiment_constructs_without_models():
    # ChaosExperiment.__init__ (strands_evals/chaos/experiment.py) only stores cases/evaluators as
    # self._cases / self._evaluators; the evaluators themselves only store the model, no call is made.
    exp = chaos.build_experiment(chaos.build_cases(1), judge="dummy-judge")
    assert isinstance(exp, ChaosExperiment)
    assert len(exp.cases) == 18
    assert len(exp._evaluators) == 4


def test_cli_refuses_without_models(monkeypatch):
    monkeypatch.delenv("TARGET_MODEL_ID", raising=False)
    monkeypatch.setenv("AWS_PROFILE", "test-sandbox")
    proc = subprocess.run([sys.executable, "-m", "evals.chaos", "--prompt", "v2", "--repeats", "1",
                           "--out", "/dev/null"], capture_output=True, text=True)
    assert proc.returncode != 0
    assert "TARGET_MODEL_ID" in proc.stderr


def test_q3_cases_run_last_and_are_the_only_ones_serialized(monkeypatch):
    cases = chaos.build_cases(repeats=1)
    names = [c.name for c in cases]
    first_q3 = next(i for i, n in enumerate(names) if n.startswith("q3"))
    assert all(n.startswith("q3") for n in names[first_q3:]) and not any(n.startswith("q3") for n in names[:first_q3])
    restored = []
    monkeypatch.setattr(chaos, "ensure_dev_running", lambda: restored.append(1))
    wrapped = chaos.with_dev_restore(lambda case: case.name)
    assert wrapped(cases[0]) == cases[0].name and restored == []
    assert wrapped(cases[-1]) == cases[-1].name and restored == [1]


def test_gate_uses_the_named_evaluator_pass_rate_or_the_overall_score():
    from types import SimpleNamespace
    report = SimpleNamespace(
        overall_score=0.67,
        cases=[{"evaluator": "FailureCommunicationEvaluator"}, {"evaluator": "FailureCommunicationEvaluator"},
               {"evaluator": "OutputEvaluator"}, {"evaluator": "OutputEvaluator"}],
        test_passes=[True, False, True, True],
    )
    assert chaos.gate(report, None) == ("overall_score", 0.67)
    assert chaos.gate(report, "FailureCommunicationEvaluator") == ("FailureCommunicationEvaluator", 0.5)
    assert chaos.gate(report, "OutputEvaluator")[1] == 1.0
