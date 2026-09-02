"""diagnose_session over a saved session, plus our four-bucket reading next to the SDK's verbatim output.

Verified against installed strands-agents-evals 1.2.0
(.venv/lib/python3.13/site-packages/strands_evals/), not its published docs:
  - `diagnose_session` lives in strands_evals/detectors/diagnosis.py and is re-exported from
    strands_evals.detectors (strands_evals/detectors/__init__.py). Signature:
    diagnose_session(session, *, model=None, confidence_threshold=ConfidenceLevel.LOW) -> DiagnosisResult.
  - `ConfidenceLevel` lives in strands_evals/types/detector.py (also re-exported from
    strands_evals.detectors); members are LOW/MEDIUM/HIGH.
  - DiagnosisResult (strands_evals/types/detector.py) fields: session_id: str,
    failures: list[FailureItem], root_causes: list[RCAItem].
  - FailureItem fields: span_id: str, category: list[str], confidence: list[float],
    evidence: list[str] (category/confidence are lists, one entry per classification -
    not scalars, matching the brief's warning).
  - RCAItem fields: failure_span_id, location, causality (one of PRIMARY_FAILURE /
    SECONDARY_FAILURE / TERTIARY_FAILURE - a short SDK classification, not free text),
    propagation_impact, failure_detection_timing, completion_status,
    root_cause_explanation (free-text explanation - this is where keyword signal
    like "timeout" or "AccessDenied" actually shows up), fix_type (one of
    SYSTEM_PROMPT_FIX / TOOL_DESCRIPTION_FIX / OTHERS - not "tool"/"prompt" literals),
    fix_recommendation: str.
  render() therefore feeds bucket() the free-text root_cause_explanation (not the terse
  causality enum) so the keyword heuristic has something to match against; bucket()'s
  fix_type checks use startswith/substring containment so they also fire on the real
  TOOL_DESCRIPTION_FIX / SYSTEM_PROMPT_FIX values, not just the literal "tool"/"prompt"
  used in the unit tests below. See bucket()'s own docstring for details.
"""

import argparse
import re
import sys
from pathlib import Path

from strands_evals.detectors import diagnose_session
from strands_evals.types.detector import ConfidenceLevel

from agent import config
from evals import telemetry

# ponytail: keyword heuristic over the SDK's free-text fields; the slide shows SDK text on the left, this on the right
# "permisos" is our layer 3, AWS IAM authorization — not generic HTTP/app auth. A 403 from a
# tool's upstream API is a tool problem, not IAM, so "forbidden" and generic "unauthorized" are
# deliberately excluded; only AWS-shaped authorization signals qualify.
_PERMISOS = ("accessdenied", "access denied", "unauthorizedoperation", "not authorized", "explicit deny", "permission")
_TOOL = ("timeout", "network", "tool error", "tool execution", "truncat", "missing field", "unavailable")
_MODELO = ("prompt", "model", "hallucin", "invent", "asserted", "assumed", "reasoning", "instruction")


def bucket(location: str, fix_type: str, causality: str) -> str:
    """Pure keyword/fix_type heuristic mapped to modelo/tool/permisos/ejecucion.

    render() calls this with `causality` bound to RCAItem.root_cause_explanation, not
    RCAItem.causality: the SDK's own `causality` field is a closed enum
    (PRIMARY_FAILURE/SECONDARY_FAILURE/TERTIARY_FAILURE) with no keyword signal to match
    against, while `root_cause_explanation` is free text that actually contains words like
    "timeout" or "AccessDenied". `location` is kept for the brief's original signature; in
    real data it's a span id and carries no signal either.
    """
    text = f"{location} {fix_type} {causality}".lower()
    # "iam" is checked separately at a word boundary: as a plain substring it matches inside
    # unrelated words (e.g. "diamante").
    if re.search(r"\biam\b", text) or any(k in text for k in _PERMISOS):
        return "permisos"
    # Real IAM/authorization text always wins over this precedence, since the permisos check
    # above runs first: a fix_type of TOOL_DESCRIPTION_FIX doesn't mask an UnauthorizedOperation.
    if fix_type.upper().startswith("TOOL"):
        return "tool"
    if any(k in text for k in _TOOL):
        return "tool"
    if "prompt" in fix_type.lower() or any(k in text for k in _MODELO):
        return "modelo"
    return "ejecucion"


def render(result) -> str:
    lines = [f"session {result.session_id}: {len(result.failures)} failures, {len(result.root_causes)} root causes", ""]
    for f in result.failures:
        lines.append(f"- falla en span {f.span_id}: {', '.join(f.category)} (conf {', '.join(f'{c:.2f}' for c in f.confidence)})")
        for e in f.evidence:
            lines.append(f"    evidencia: {e}")
    lines.append("")
    lines.append(f"{'SDK (verbatim)':<58} | lectura")
    for rc in result.root_causes:
        b = bucket(rc.location, rc.fix_type, rc.root_cause_explanation)
        lines.append(f"{rc.location[:28]:<28} {rc.fix_type[:12]:<12} {rc.causality[:16]:<16} | {b}")
        lines.append(f"    root cause: {rc.root_cause_explanation}")
        lines.append(f"    fix: {rc.fix_recommendation}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("session", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--confidence", default="medium", choices=["low", "medium", "high"])
    args = parser.parse_args()
    try:
        config.require_sandbox()
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if not args.session.exists():
        print(f"error: session file not found: {args.session}", file=sys.stderr)
        return 2
    session = telemetry.load_session(args.session)
    result = diagnose_session(session, model=telemetry.judge_model(),
                              confidence_threshold=ConfidenceLevel[args.confidence.upper()])
    print(render(result))
    if args.out:
        args.out.write_text(result.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
