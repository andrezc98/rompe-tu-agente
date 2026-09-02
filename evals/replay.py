"""Replay the user turns of a saved red-team attack through a traced Sentinel, producing a Session for the trace slide."""

import argparse
import sys
import uuid
from pathlib import Path

from strands_evals.experimental.redteam import RedTeamReport

from agent import config
from agent.sentinel import make_sentinel
from evals import telemetry
from evals.redteam import _base_case_name

SHOW = Path(__file__).resolve().parent / "results" / "show"


def user_turns(report: RedTeamReport, case_name: str, strategy_label: str) -> list[str]:
    """Extract the attacker's messages of one attack, in order.

    VERIFIED against installed strands-evals 1.2.0 (strands_evals/experimental/redteam/report.py
    `AttackResult`, strategies/base.py `AttackRunResult`, and every strategy's `run_attack`):
    - The field is `AttackResult.conversation` (`list[dict]`), not `.transcript`.
    - Each turn is a plain dict with "role"/"content" keys, not an object with attributes.
    - The attacker-side role is "attacker" (not "user"); the target-side role is "target".
      Every strategy (Crescendo/GOAT) emits only these two roles.
    - `AttackResult.case_name` carries the "{case}__{strategy_label}" cross-product suffix
      `RedTeamExperiment._expand_cross_product` appends, so it is stripped before matching
      against the bare case name the caller passes.
    """
    for result in report.attack_results():
        if result.strategy == strategy_label and _base_case_name(result) == case_name:
            return [turn["content"] for turn in result.conversation if turn["role"] == "attacker"]
    raise SystemExit(f"attack {case_name}/{strategy_label} not found in report")


def replay(turns: list[str], out_stem: str) -> None:
    session_id = str(uuid.uuid4())
    telemetry.telemetry().in_memory_exporter.clear()
    agent = make_sentinel(session_id=session_id)
    transcript = []
    for turn in turns:
        response = agent(turn)  # the Strands Agent keeps the conversation across calls
        transcript.append(f"USER: {turn}\nSENTINEL: {response}\n")
    spans = telemetry.telemetry().in_memory_exporter.get_finished_spans()
    session = telemetry.map_session(spans, session_id)
    SHOW.mkdir(parents=True, exist_ok=True)
    telemetry.save_session(session, SHOW / f"{out_stem}-session.json")
    (SHOW / f"{out_stem}-transcript.txt").write_text("\n".join(transcript))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("--case", required=True)
    parser.add_argument("--strategy", required=True)
    parser.add_argument("--out", default="stop-prod")
    args = parser.parse_args()
    config.require_sandbox()
    report = RedTeamReport.from_file(str(args.report))
    replay(user_turns(report, args.case, args.strategy), args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
