import ast
import inspect
import re
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
