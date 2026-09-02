from types import SimpleNamespace

from evals import charts


def test_effect_of_case_name():
    assert charts.effect_of("q2-r1|metric_timeout") == "metric_timeout"
    assert charts.effect_of("q1-r3|baseline") == "baseline"
    assert charts.effect_of("q3-r2") == "baseline"


def test_pass_rate_by_effect():
    report = {"cases": [{"name": "q1-r1|metric_timeout"}, {"name": "q1-r2|metric_timeout"}, {"name": "q1-r1|alarms_down"}],
              "test_passes": [True, False, True]}
    rates = charts.pass_rate_by_effect(report)
    assert rates["metric_timeout"] == 0.5
    assert rates["alarms_down"] == 1.0


def _chaos_report(effects_and_passes: list[tuple[str, bool]]) -> dict:
    return {
        "cases": [{"name": f"q1-r1|{effect}"} for effect, _ in effects_and_passes],
        "test_passes": [passed for _, passed in effects_and_passes],
    }


def test_chart_chaos_renders_from_synthetic_reports(tmp_path):
    v1 = _chaos_report([("metric_timeout", False), ("alarms_down", True), ("baseline", True)])
    v2 = _chaos_report([("metric_timeout", True), ("alarms_down", True), ("baseline", True)])
    out = tmp_path / "chaos-v1-vs-v2.png"

    charts.chart_chaos(v1, v2, out)

    assert out.exists()
    assert out.stat().st_size > 10_000


def test_chart_layers_renders(tmp_path):
    out = tmp_path / "capas.png"

    charts.chart_layers(out)

    assert out.exists()
    assert out.stat().st_size > 10_000


def _attack(case_name: str, risk_category: str, strategy: str, score: float) -> SimpleNamespace:
    return SimpleNamespace(case_name=case_name, risk_category=risk_category, strategy=strategy, score=score)


def test_chart_redteam_renders_from_synthetic(tmp_path):
    # One defended case (low score -> annotated with its backstop layer) and one breached case
    # (score at/above the threshold -> annotated "ninguna"), each hit by two strategies.
    pass1 = [
        _attack("stop_prod__crescendo", "excessive_agency", "crescendo", 0.1),
        _attack("stop_prod__goat", "excessive_agency", "goat", 0.2),
        _attack("leak_prompt__crescendo", "system_prompt_leak", "crescendo", 0.8),
        _attack("leak_prompt__goat", "system_prompt_leak", "goat", 0.6),
    ]
    pass2 = [
        _attack("stop_prod__crescendo", "excessive_agency", "crescendo", 0.15),
        _attack("stop_prod__goat", "excessive_agency", "goat", 0.25),
        _attack("leak_prompt__crescendo", "system_prompt_leak", "crescendo", 0.7),
        _attack("leak_prompt__goat", "system_prompt_leak", "goat", 0.5),
    ]
    out = tmp_path / "redteam-matrix.png"

    charts.chart_redteam_from(pass1, pass2, out)

    assert out.exists()
    assert out.stat().st_size > 10_000
