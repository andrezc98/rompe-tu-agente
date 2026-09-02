import subprocess
import sys
from types import SimpleNamespace

from strands_evals.experimental.redteam import AttackGoal, RedTeamCase, RedTeamConfig, RedTeamExperiment

from evals import redteam


def test_hand_cases_cover_shell_escape_and_prod_stop():
    names = {c.name for c in redteam.HAND_CASES}
    assert {"shell_escape_internal", "stop_prod_fake_ticket"} <= names
    for c in redteam.HAND_CASES:
        assert c.config.attack_goal.risk_category in redteam.RISKS


def test_risks_are_the_four_layers():
    assert redteam.RISKS == ["excessive_agency", "data_exfiltration", "system_prompt_leak", "guideline_bypass"]


def test_strategies_have_bounded_turns():
    s = redteam.strategies()
    assert len(s) == 2
    assert {type(x).__name__ for x in s} == {"CrescendoStrategy", "GoatStrategy"}  # SequentialBreak dropped 2026-09-02


def test_cli_refuses_without_models(monkeypatch):
    monkeypatch.delenv("TARGET_MODEL_ID", raising=False)
    monkeypatch.setenv("AWS_PROFILE", "test-sandbox")
    proc = subprocess.run(
        [sys.executable, "-m", "evals.redteam", "--generate", "0", "--passes", "1"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 2
    assert "TARGET_MODEL_ID" in proc.stderr


def test_cli_refuses_without_attacker_model(monkeypatch):
    monkeypatch.setenv("TARGET_MODEL_ID", "dummy-target")
    monkeypatch.setenv("JUDGE_MODEL_ID", "dummy-judge")
    monkeypatch.delenv("ATTACKER_MODEL_ID", raising=False)
    monkeypatch.setenv("AWS_PROFILE", "test-sandbox")
    proc = subprocess.run(
        [sys.executable, "-m", "evals.redteam", "--generate", "0", "--passes", "1"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 2
    assert "ATTACKER_MODEL_ID" in proc.stderr


def _case(name: str) -> RedTeamCase:
    return RedTeamCase(
        name=name,
        input="hola",
        config=RedTeamConfig(attack_goal=AttackGoal(risk_category="excessive_agency", actor_goal="x")),
    )


def test_export_suite_strips_strategy_suffix_and_dedupes(tmp_path):
    cases = [_case("a"), _case("b")]
    report = SimpleNamespace(failed_cases=[
        SimpleNamespace(case_name="a__crescendo", strategy="crescendo", score=0.9),
        SimpleNamespace(case_name="a__goat", strategy="goat", score=0.8),
    ])
    path = tmp_path / "suite.json"

    n = redteam.export_suite(cases, report, path)

    assert n == 1
    reloaded = RedTeamExperiment.from_file(str(path))
    assert [c.name for c in reloaded.cases] == ["a"]
    assert [type(s).__name__ for s in reloaded.attack_strategies] == ["CrescendoStrategy"]


def test_export_suite_ignores_attacks_the_attacker_never_launched(tmp_path):
    cases = [redteam.RedTeamCase(name=n, input="x", config=redteam.HAND_CASES[0].config) for n in ("a", "b")]
    report = SimpleNamespace(failed_cases=[
        SimpleNamespace(case_name="a__crescendo", strategy="crescendo", conversation=[{"role": "attacker", "content": "hola"}]),
        SimpleNamespace(case_name="b__goat", strategy="goat", conversation=[]),  # provider refused the attacker: 0 turns
    ])
    n = redteam.export_suite(cases, report, tmp_path / "suite.json")
    assert n == 1


def test_generate_splits_the_total_across_risk_categories(monkeypatch):
    seen = {}

    class FakeGen:
        def __init__(self, model): pass
        def generate_cases(self, agent, risk_categories, num_cases):
            seen["per_category"] = num_cases; seen["categories"] = list(risk_categories); return []

    monkeypatch.setattr(redteam, "AdversarialCaseGenerator", FakeGen)
    monkeypatch.setattr(redteam, "make_sentinel", lambda v: object())
    redteam.generate(judge=None, num_cases=8)
    assert seen["per_category"] == 8 // len(redteam.RISKS) == 2 and len(seen["categories"]) == 4
