import ast
import json
import inspect
import re
from types import SimpleNamespace

from evals import charts


def test_effect_of_case_name():
    assert charts.effect_of("q2-r1|metric_timeout") == "metric_timeout"
    assert charts.effect_of("q1-r3|baseline") == "baseline"
    assert charts.effect_of("q3-r2") == "baseline"


# Four evaluators, so run_evaluations emits four rows per case name (see evals/report_rows.py).
EVALUATORS = ["OutputEvaluator", "FailureCommunicationEvaluator", "PartialCompletionEvaluator",
              "RecoveryStrategyEvaluator"]


def _run_rows(name: str, passes: list[bool]) -> dict:
    """The real flattened shape: one row per (case, evaluator), each tagged with its evaluator."""
    return {
        "cases": [{"name": name, "evaluator": e, "evaluator_type": "llm_judge"} for e in EVALUATORS],
        "test_passes": list(passes),
    }


def _report(*runs: dict) -> dict:
    report = {"cases": [], "test_passes": []}
    for run in runs:
        report["cases"].extend(run["cases"])
        report["test_passes"].extend(run["test_passes"])
    return report


ALL_PASS = [True] * 4
ONE_FAILS = [True, True, False, True]


def test_pass_rate_counts_runs_not_rows():
    # Three runs, twelve rows. The middle run fails a single evaluator, so it does not count.
    report = _report(
        _run_rows("q1-r1|metric_timeout", ALL_PASS),
        _run_rows("q1-r2|metric_timeout", ONE_FAILS),
        _run_rows("q1-r1|alarms_down", ALL_PASS),
    )

    rates = charts.pass_rate_by_effect(report)

    assert rates["metric_timeout"] == 0.5  # 1 of 2 runs, not 7 of 8 rows
    assert rates["alarms_down"] == 1.0


def test_a_run_passes_only_when_every_evaluator_passes():
    rates = charts.pass_rate_by_effect(_report(_run_rows("q1-r1|metric_silent", ONE_FAILS)))

    assert rates["metric_silent"] == 0.0


def _chaos_report(effects_and_passes: list[tuple[str, bool]]) -> dict:
    return _report(*[
        _run_rows(f"q1-r{i}|{effect}", ALL_PASS if passed else ONE_FAILS)
        for i, (effect, passed) in enumerate(effects_and_passes, start=1)
    ])


def test_chart_chaos_renders_from_synthetic_reports(tmp_path):
    v1 = _chaos_report([("metric_timeout", False), ("alarms_down", True), ("baseline", True)])
    v2 = _chaos_report([("metric_timeout", True), ("alarms_down", True), ("baseline", True)])
    out = tmp_path / "chaos-v1-vs-v2.png"

    charts.chart_chaos(v1, v2, out)

    assert out.exists()
    assert out.stat().st_size > 10_000


def test_chart_layers_renders(tmp_path):
    out = tmp_path / "capas-tabla.png"

    charts.chart_layers(out)

    assert out.exists()
    assert out.stat().st_size > 10_000


def _attack(case_name: str, risk_category: str, strategy: str, score: float) -> SimpleNamespace:
    return SimpleNamespace(case_name=case_name, risk_category=risk_category, strategy=strategy, score=score)


def _eval_font_expr(node: ast.AST, env: dict) -> float:
    """Evaluate a tiny numeric expression (int literal, a known name, or name +/- int) safely.

    Deliberately not `eval()`: restricted to an allowlist of AST node types (no calls, no
    attribute access, no arbitrary names) so a static-analysis-only test never executes anything
    from the scanned source beyond basic arithmetic on known constants.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.Name):
        return env[node.id]
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub)):
        left, right = _eval_font_expr(node.left, env), _eval_font_expr(node.right, env)
        return left + right if isinstance(node.op, ast.Add) else left - right
    raise ValueError(f"unsupported fontsize/labelsize expression: {ast.dump(node)}")


def test_all_text_at_least_24pt():
    """Guard against a text-size regression: the plan's floor is 24pt, back-of-the-room readable.

    Font constants are centralized (`BASE_FONT`, `TITLE_FONT`) so every call site passes either a
    literal number or one of those names (optionally in a small expression like `BASE_FONT + 4`).
    Evaluate each `fontsize=`/`labelsize=` argument found in the source against the real constants
    and assert it clears the floor -- this catches both a stray literal below 24 and a lowered
    constant.
    """
    assert charts.BASE_FONT >= 24
    assert charts.TITLE_FONT >= 24

    source = inspect.getsource(charts)
    matches = re.findall(r"(?:fontsize|labelsize)\s*=\s*([^,)]+)", source)
    assert matches, "expected at least one fontsize=/labelsize= call site to check"
    env = {"BASE_FONT": charts.BASE_FONT, "TITLE_FONT": charts.TITLE_FONT}
    for expr in matches:
        node = ast.parse(expr.strip(), mode="eval").body
        value = _eval_font_expr(node, env)
        assert value >= 24, f"fontsize/labelsize expression {expr!r} evaluates to {value} < 24"


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


def test_refused_attacks_do_not_count_as_defended():
    refused = SimpleNamespace(case_name="x__goat", risk_category="data_exfiltration", strategy="goat", score=0.0, conversation=[])
    launched = SimpleNamespace(case_name="y__goat", risk_category="excessive_agency", strategy="goat", score=0.9,
                               conversation=[{"role": "attacker", "content": "hola"}])
    diluter = SimpleNamespace(case_name="z__goat", risk_category="excessive_agency", strategy="goat", score=0.0, conversation=[])
    worst = charts._worst_by_cell([refused, launched, diluter])
    assert worst == {("excessive_agency", "goat"): 0.9}
    assert charts._refused_cells([refused, launched, diluter]) == {("data_exfiltration", "goat")}


def test_figure_data_feeds_the_cloudscape_figures():
    v = _report(_run_rows("q1-r1|metric_timeout", ALL_PASS), _run_rows("q1-r2|metric_timeout", ONE_FAILS))
    pass1 = [_attack("a__goat", "excessive_agency", "goat", 0.9)]
    pass2 = [_attack("a__goat", "excessive_agency", "goat", 0.7)]

    d = charts.figure_data(v, v, pass1, pass2)

    assert d["chaos"]["v1"]["metric_timeout"] == 0.5 and d["chaos"]["n_per_effect"] == 2
    assert d["chaos"]["effects"][1] == {"key": "metric_timeout", "label": "timeout"}
    assert d["matrix"]["strategies"] == ["goat"]
    assert d["matrix"]["rows"][0] == {"category": "ejecuta de más", "key": "excessive_agency", "cells": [{"score": 0.8, "scores": [0.9, 0.7], "layer": "ninguna"}]}
    assert d["chaos"]["by_evaluator"]["v1"]["metric_timeout"]["PartialCompletionEvaluator"] == 1
    assert d["escena"] is None or d["escena"]["spans"]
    assert d["matrix"]["rows"][1]["cells"] == [None]
    assert json.loads(json.dumps(d)) == d
