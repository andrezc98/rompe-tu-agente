import subprocess
import sys

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
    assert len(s) == 3
    assert {type(x).__name__ for x in s} == {"CrescendoStrategy", "GoatStrategy", "SequentialBreakStrategy"}


def test_cli_refuses_without_models(monkeypatch):
    monkeypatch.delenv("TARGET_MODEL_ID", raising=False)
    monkeypatch.setenv("AWS_PROFILE", "test-sandbox")
    proc = subprocess.run(
        [sys.executable, "-m", "evals.redteam", "--generate", "0", "--passes", "1"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 2
    assert "TARGET_MODEL_ID" in proc.stderr
