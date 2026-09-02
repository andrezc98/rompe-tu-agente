import json

import pytest
from strands_evals.types.evaluation import NOT_APPLICABLE

from evals import verdicts

# Four evaluators, so run_evaluations emits four rows per case name (see evals/report_rows.py).
EVALUATORS = ["OutputEvaluator", "FailureCommunicationEvaluator", "PartialCompletionEvaluator",
              "RecoveryStrategyEvaluator"]


def _rows(name: str, scores: list[float]) -> dict:
    """The real flattened shape: one row per (case, evaluator), each tagged with its evaluator."""
    return {
        "cases": [{"name": name, "evaluator": e, "evaluator_type": "llm_judge"} for e in EVALUATORS],
        "scores": list(scores),
        "test_passes": [s >= 0.5 for s in scores],
        "reasons": [f"{e} dice algo" for e in EVALUATORS],
    }


def _report(tmp_path, *runs: dict) -> "object":
    data = {"overall_score": 0.0, "cases": [], "scores": [], "test_passes": [], "reasons": []}
    for run in runs:
        for key in ("cases", "scores", "test_passes", "reasons"):
            data[key].extend(run[key])
    data["overall_score"] = sum(data["scores"]) / len(data["scores"])
    p = tmp_path / "r.json"
    p.write_text(json.dumps(data))
    return p


def _two_runs(tmp_path):
    return _report(
        tmp_path,
        _rows("q1-r1|baseline", [1.0, 1.0, 1.0, 1.0]),
        _rows("q2-r1|metric_timeout", [0.0, 0.0, 1.0, 0.0]),
    )


def _verdicts(tmp_path, mapping) -> "object":
    p = tmp_path / "v.json"
    p.write_text(json.dumps(mapping))
    return p


def test_one_verdict_overrides_all_four_evaluator_rows(tmp_path):
    report = _two_runs(tmp_path)
    v = _verdicts(tmp_path, {"q2-r1|metric_timeout": {"veredicto": "parcial", "nota": "dijo que no pudo pero igual dio un rango"}})

    adjusted, n = verdicts.apply(report, v)

    assert n == 1  # one RUN adjusted, not four rows
    assert adjusted["scores"] == [1.0, 1.0, 1.0, 1.0, 0.5, 0.5, 0.5, 0.5]
    assert adjusted["test_passes"][4:] == [True, True, True, True]
    for reason in adjusted["reasons"][4:]:
        assert reason.startswith("[humano] dijo que no pudo pero igual dio un rango")
    assert "OutputEvaluator dice algo" in adjusted["reasons"][4]
    # Plain mean over rows: the fixture carries no detailed_results, so the SDK formula is skipped.
    assert adjusted["overall_score"] == pytest.approx(0.75)


def test_untouched_runs_keep_their_rows(tmp_path):
    report = _two_runs(tmp_path)
    v = _verdicts(tmp_path, {"q2-r1|metric_timeout": {"veredicto": "fallo", "nota": "inventó"}})

    adjusted, _ = verdicts.apply(report, v)

    assert adjusted["scores"][:4] == [1.0, 1.0, 1.0, 1.0]
    assert adjusted["reasons"][0] == "OutputEvaluator dice algo"


def test_overall_score_untouched_when_nothing_adjusted(tmp_path):
    report = _two_runs(tmp_path)
    before = json.loads(report.read_text())["overall_score"]

    adjusted, n = verdicts.apply(report, _verdicts(tmp_path, {}))

    assert n == 0
    assert adjusted["overall_score"] == before


def test_overall_score_uses_the_sdk_formula_when_detailed_results_are_present(tmp_path):
    # A row that declined to judge (NOT_APPLICABLE and test_pass) is dropped from the average by
    # EvaluationReport.calculate_overall_score; a plain mean would count its 1.0 and read high.
    data = json.loads(_two_runs(tmp_path).read_text())
    data["detailed_results"] = [[{"score": s, "test_pass": s >= 0.5, "label": None}] for s in data["scores"]]
    # Row 3 declined to judge: score 0.0, but it passed and carries the SDK's NOT_APPLICABLE
    # label (the literal is "not_applicable", strands_evals/types/evaluation.py:112).
    data["scores"][3], data["test_passes"][3] = 0.0, True
    data["detailed_results"][3] = [{"score": 0.0, "test_pass": True, "label": NOT_APPLICABLE}]
    p = tmp_path / "r2.json"
    p.write_text(json.dumps(data))
    v = _verdicts(tmp_path, {"q2-r1|metric_timeout": {"veredicto": "correcto", "nota": "estuvo bien"}})

    adjusted, n = verdicts.apply(p, v)

    assert n == 1
    # After the override every judged row is 1.0. The SDK formula drops the declining row and
    # reads 7/7 = 1.0; a plain mean over all 8 rows would read 0.875 and under-report the run.
    assert adjusted["overall_score"] == pytest.approx(1.0)
    assert sum(adjusted["scores"]) / len(adjusted["scores"]) == pytest.approx(0.875)


def test_invalid_verdict_raises_clear_error(tmp_path):
    report = _two_runs(tmp_path)
    v = _verdicts(tmp_path, {"q1-r1|baseline": {"veredicto": "parcialmente"}})
    with pytest.raises(ValueError, match="parcialmente"):
        verdicts.apply(report, v)


def test_reasons_padded_when_shorter(tmp_path):
    data = json.loads(_two_runs(tmp_path).read_text())
    data["reasons"] = []
    p = tmp_path / "r3.json"
    p.write_text(json.dumps(data))
    v = _verdicts(tmp_path, {"q2-r1|metric_timeout": {"veredicto": "parcial", "nota": "nota breve"}})

    adjusted, _ = verdicts.apply(p, v)

    assert len(adjusted["reasons"]) == 8
    assert adjusted["reasons"][0] == ""
    assert adjusted["reasons"][4].startswith("[humano] nota breve")


def test_sentence():
    assert verdicts.sentence(1, 2) == "Auto-evaluado por LLM, revisado a mano: 1 de 2 veredictos ajustados."


def test_main_counts_runs_not_rows(tmp_path, monkeypatch, capsys):
    # 8 rows, 2 runs: the sentence on the slide has to say "de 2", matching "54 corridas".
    report = _two_runs(tmp_path)
    v = _verdicts(tmp_path, {"q2-r1|metric_timeout": {"veredicto": "parcial", "nota": "n"}})
    out = tmp_path / "revisado.json"
    monkeypatch.setattr("sys.argv", ["verdicts", str(report), "--verdicts", str(v), "--out", str(out)])

    assert verdicts.main() == 0

    assert "1 de 2 veredictos ajustados" in capsys.readouterr().out
    assert len(json.loads(out.read_text())["cases"]) == 8
