"""Human overrides over LLM-judge scores. The report on stage says how many were adjusted."""

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError
from strands_evals.types.evaluation import EvaluationOutput
from strands_evals.types.evaluation_report import EvaluationReport

from evals.report_rows import runs_by_name

SCORE = {"correcto": 1.0, "parcial": 0.5, "fallo": 0.0}


def overall_score(report: dict) -> float:
    """The SDK's own average (EvaluationReport.calculate_overall_score), not a plain mean.

    It drops rows whose judge declined to judge (label NOT_APPLICABLE *and* test_pass true) and
    keeps rows that failed to judge, so overriding a verdict by hand cannot silently change which
    rows count. It needs one `EvaluationOutput` list per row; a report JSON that does not carry a
    matching `detailed_results` (older runs, hand-written fixtures) falls back to the plain mean.
    """
    scores = report["scores"]
    if not scores:
        return 0.0
    detailed = report.get("detailed_results") or []
    if len(detailed) == len(scores):
        try:
            rows = [[EvaluationOutput.model_validate(o) for o in row] for row in detailed]
            return EvaluationReport.calculate_overall_score(scores, rows)
        except ValidationError:
            pass  # not the SDK's row shape; the mean below is the honest reading
    return sum(scores) / len(scores)


def apply(report_path: Path, verdicts_path: Path) -> tuple[dict, int]:
    """Apply human verdicts run by run. Returns the report and the count of RUNS overridden.

    A run is every row sharing a case name (one per evaluator, see evals/report_rows.py), so one
    verdict rewrites all four of its rows: a human who says "this run was partial" is judging the
    run, not one evaluator's opinion of it.
    """
    report = json.loads(report_path.read_text())
    overrides = json.loads(verdicts_path.read_text()) if verdicts_path.exists() else {}
    adjusted = 0
    report.setdefault("reasons", [])
    # Pad reasons to match cases length so prefix is always applied
    while len(report["reasons"]) < len(report["cases"]):
        report["reasons"].append("")
    for name, rows in runs_by_name(report).items():
        verdict = overrides.get(name)
        if not verdict:
            continue
        veredicto = verdict["veredicto"]
        if veredicto not in SCORE:
            raise ValueError(f"case {name}: veredicto {veredicto!r} must be one of {sorted(SCORE)}")
        for i in rows:
            report["scores"][i] = SCORE[veredicto]
            report["test_passes"][i] = report["scores"][i] >= 0.5
            report["reasons"][i] = f"[humano] {verdict.get('nota', '')} | {report['reasons'][i]}"
        adjusted += 1
    if adjusted:
        report["overall_score"] = overall_score(report)
    return report, adjusted


def sentence(adjusted: int, total: int) -> str:
    return f"Auto-evaluado por LLM, revisado a mano: {adjusted} de {total} veredictos ajustados."


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("--verdicts", type=Path, default=Path(__file__).with_name("verdicts.json"))
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    report, n = apply(args.report, args.verdicts)
    if args.out:
        args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"overall_score={report['overall_score']:.3f}")
    # Runs, not rows: the deck's "N de M" has to match the "54 corridas" on the same slide.
    print(sentence(n, len(runs_by_name(report))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
