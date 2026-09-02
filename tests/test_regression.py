import subprocess
import sys
from types import SimpleNamespace

from strands_evals.experimental.redteam import AttackGoal, RedTeamCase, RedTeamConfig

from evals import redteam, regression


def test_exit_code_zero_when_clean():
    assert regression.exit_code(SimpleNamespace(failed_cases=[])) == 0


def test_exit_code_one_on_breach():
    breach = SimpleNamespace(case_name="stop_prod_fake_ticket", score=0.9, severity="high")
    assert regression.exit_code(SimpleNamespace(failed_cases=[breach])) == 1


def test_cli_refuses_without_models(monkeypatch):
    monkeypatch.delenv("TARGET_MODEL_ID", raising=False)
    monkeypatch.setenv("AWS_PROFILE", "test-sandbox")
    proc = subprocess.run(
        [sys.executable, "-m", "evals.regression"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 2
    assert "TARGET_MODEL_ID" in proc.stderr


def _case(name: str) -> RedTeamCase:
    return RedTeamCase(
        name=name,
        input="hola",
        config=RedTeamConfig(attack_goal=AttackGoal(risk_category="excessive_agency", actor_goal="x")),
    )


def test_load_suite_round_trip_from_export(tmp_path):
    cases = [_case("a"), _case("b")]
    report = SimpleNamespace(failed_cases=[
        SimpleNamespace(case_name="a__crescendo", strategy="crescendo", score=0.9),
    ])
    path = tmp_path / "suite.json"
    redteam.export_suite(cases, report, path)

    loaded = regression.load_suite(path)

    assert [c.name for c in loaded.cases] == ["a"]
    assert [type(s).__name__ for s in loaded.attack_strategies] == ["CrescendoStrategy"]
