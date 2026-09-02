"""Human overrides over LLM-judge scores. The report on stage says how many were adjusted."""

import argparse
import json
import sys
from pathlib import Path

SCORE = {"correcto": 1.0, "parcial": 0.5, "fallo": 0.0}


def apply(report_path: Path, verdicts_path: Path) -> tuple[dict, int]:
    report = json.loads(report_path.read_text())
    overrides = json.loads(verdicts_path.read_text()) if verdicts_path.exists() else {}
    adjusted = 0
    report.setdefault("reasons", [])
    # Pad reasons to match cases length so prefix is always applied
    while len(report["reasons"]) < len(report["cases"]):
        report["reasons"].append("")
    for i, case in enumerate(report["cases"]):
        verdict = overrides.get(case.get("name", ""))
        if not verdict:
            continue
        veredicto = verdict["veredicto"]
        if veredicto not in SCORE:
            name = case.get("name", "")
            raise ValueError(f"case {name}: veredicto {veredicto!r} must be one of {sorted(SCORE)}")
        report["scores"][i] = SCORE[veredicto]
        report["test_passes"][i] = report["scores"][i] >= 0.5
        report["reasons"][i] = f"[humano] {verdict.get('nota', '')} | {report['reasons'][i]}"
        adjusted += 1
    if report["scores"]:
        report["overall_score"] = sum(report["scores"]) / len(report["scores"])
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
    print(sentence(n, len(report["cases"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
