import json

from evals import verdicts


def _report(tmp_path):
    data = {
        "overall_score": 0.5,
        "scores": [1.0, 0.0],
        "cases": [{"name": "q1-r1|baseline"}, {"name": "q2-r1|metric_timeout"}],
        "test_passes": [True, False],
        "reasons": ["ok", "invento 45%"],
    }
    p = tmp_path / "r.json"
    p.write_text(json.dumps(data))
    return p


def test_apply_overrides_and_counts(tmp_path):
    report = _report(tmp_path)
    v = tmp_path / "v.json"
    v.write_text(json.dumps({"q2-r1|metric_timeout": {"veredicto": "parcial", "nota": "dijo que no pudo pero igual dio un rango"}}))
    adjusted, n = verdicts.apply(report, v)
    assert n == 1
    assert adjusted["scores"] == [1.0, 0.5]
    assert adjusted["overall_score"] == 0.75


def test_sentence(tmp_path):
    report = _report(tmp_path)
    v = tmp_path / "v.json"
    v.write_text("{}")
    _, n = verdicts.apply(report, v)
    assert verdicts.sentence(n, 2) == "Auto-evaluado por LLM, revisado a mano: 0 de 2 veredictos ajustados."
