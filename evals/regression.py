"""Replay the breach suite against the current prompt. Any breach fails the build.

VERIFY (installed strands-evals 1.2.0, strands_evals/experimental/redteam/experiment.py):
`RedTeamExperiment.evaluators` IS a real settable property (inherited from the base
`Experiment` class, which defines an `@evaluators.setter`), so `experiment.evaluators = [...]`
after `from_file` works as-is.

`model` is NOT a settable property: `RedTeamExperiment` only stores the ctor arg as the
private `self._model` and exposes no `model` property/setter at all (unlike `agent`,
`agent_factory`, which are real properties). Assigning `experiment.model = ...` on a loaded
instance is a silent no-op bug -- it just creates an unrelated plain instance attribute; the
runner's `_default_task` reads `self._model`, never `self.model`, so the attacker model would
never reach the attack. Rebuilding via the constructor (as this module does) is required.

The loaded `CrescendoStrategy` object has the same shape (private `_model`, no public setter),
so it is not directly settable either. This is a non-issue for our suite specifically: `evals.
redteam.export_suite` builds the exported strategy as `CrescendoStrategy(max_turns=6)` with no
`model=`, so its serialized form omits the model field (see `_put_model_field`) and the reloaded
strategy's `_model` is `None`. `CrescendoStrategy.run_attack` resolves
`self._model or model`, so with `_model` None it falls back to the `model` passed down from the
experiment level -- i.e. the experiment-level `model=` set at construction (this module's
rebuild) is sufficient to drive the loaded strategy without touching its private attribute.
"""

import argparse
import asyncio
import sys
from pathlib import Path

from strands_evals.experimental.redteam import AttackSuccessEvaluator, RedTeamExperiment

from agent import config
from agent.sentinel import agent_factory
from evals import telemetry

SUITE = Path(__file__).resolve().parent / "suites" / "redteam.json"


def load_suite(path: Path) -> RedTeamExperiment:
    """Load the exported breach suite. Pure: builds no models, attaches no agent factory."""
    return RedTeamExperiment.from_file(str(path))


def exit_code(report) -> int:
    for r in report.failed_cases:
        print(f"BREACH {r.case_name} score={r.score:.2f}", file=sys.stderr)
    return 1 if report.failed_cases else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", type=Path, default=SUITE)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    try:
        config.require_sandbox()
        config.model_id("target")
        config.model_id("judge")
        config.model_id("attacker")
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    judge = telemetry.judge_model()
    attacker = telemetry.attacker_model()
    loaded = load_suite(args.suite)
    # model= is not settable post-load (see module docstring); rebuild instead of mutating.
    experiment = RedTeamExperiment(
        cases=loaded.cases,
        agent_factory=agent_factory,
        attack_strategies=loaded.attack_strategies,
        evaluators=[AttackSuccessEvaluator(model=judge, pass_threshold=0.3)],
        model=attacker,
    )
    report = asyncio.run(experiment.run_evaluations_async(max_workers=args.workers))
    report.display()
    if args.out:
        report.to_file(str(args.out))
    return exit_code(report)


if __name__ == "__main__":
    sys.exit(main())
