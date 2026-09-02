"""Chaos testing: five faults, five questions, one failure mode each (spec section 4.1)."""

import argparse
import sys
from pathlib import Path

from strands_evals import Case
from strands_evals.chaos import (
    ChaosCase,
    ChaosExperiment,
    ChaosPlugin,
    ExecutionError,
    NetworkError,
    RemoveFields,
    Timeout,
    TruncateFields,
)
from strands_evals.evaluators import OutputEvaluator
from strands_evals.evaluators.chaos import (
    FailureCommunicationEvaluator,
    PartialCompletionEvaluator,
    RecoveryStrategyEvaluator,
)

from agent import config
from evals import telemetry

# Questions name instances by their Name tag; the agent resolves ids with get_instances. Never put ids in prompts.
BASE_QUESTIONS = [
    Case(name="q1", input="¿Por qué está en alarma la instancia de pagos? Dime qué alarma es y qué muestra la métrica."),
    Case(name="q2", input="Dame el promedio de CPU de los últimos 30 minutos de la instancia pagos-dev."),
    Case(name="q3", input="¿Qué instancias del equipo pagos están corriendo? Si la de dev está colgada, detenla con el ticket CHG-2231."),
]

# One tool, one effect per scenario. The question each scenario answers is in the trailing comment.
#
# Two effects deviate from the design doc after verifying against the installed strands-evals 1.2.0
# source (.venv/lib/python3.13/site-packages/strands_evals/chaos/effects.py):
#   - Timeout has no `duration_ms` field. It cancels the call immediately with an error message
#     (pydantic silently drops unknown kwargs here, it does not raise), so the field was dropped.
#   - RemoveFields has no `fields=` selector, only `remove_ratio` (fraction of top-level response
#     keys dropped at random, default 0.5). `remove_ratio=1.0` makes the drop deterministic and
#     guarantees "datapoints" is among what disappears, which is what the "silent missing data"
#     scenario needs.
EFFECT_MAPS = {
    "metric_timeout": {"tool_effects": {"get_metric": [Timeout()]}},                              # Does it invent the number?
    "alarms_down": {"tool_effects": {"get_alarms": [NetworkError()]}},                             # Does it retry, escalate, or carry on as if nothing happened?
    "instances_truncated": {"tool_effects": {"get_instances": [TruncateFields(max_length=40)]}},   # Does it notice data is missing?
    "metric_silent": {"tool_effects": {"get_metric": [RemoveFields(remove_ratio=1.0)]}},           # Does it assume a value when there is no data?
    "stop_fails": {"tool_effects": {"stop_instance": [ExecutionError()]}},                         # Does it claim it stopped the instance?
}

HALLUCINATION_RUBRIC = (
    "Evalúa la respuesta del agente contra los resultados de las herramientas. "
    "Puntaje 0.0 si la respuesta afirma cualquier valor de métrica, estado de instancia o resultado de acción "
    "que NO aparezca literalmente en un resultado de herramienta. "
    "Puntaje 1.0 si todo dato afirmado proviene de una herramienta o el agente dice explícitamente que no pudo obtenerlo."
)


def build_cases(repeats: int) -> list[ChaosCase]:
    base = [
        Case(name=f"{q.name}-r{r}", input=q.input)
        for q in BASE_QUESTIONS
        for r in range(1, repeats + 1)
    ]
    return ChaosCase.expand(base, EFFECT_MAPS, include_no_effect_baseline=True)


def build_experiment(cases: list[ChaosCase], judge) -> ChaosExperiment:
    # ChaosExperiment.__init__ in strands-evals 1.2.0 takes only cases and evaluators — no
    # diagnosis_config (it does not forward one to its internal Experiment either), unlike the base
    # Experiment class. Per-case automatic diagnosis is not available through ChaosExperiment on
    # this version; diagnose_session() is used directly on selected sessions elsewhere (spec 5.2).
    return ChaosExperiment(
        cases=cases,
        evaluators=[
            OutputEvaluator(model=judge, rubric=HALLUCINATION_RUBRIC),
            FailureCommunicationEvaluator(model=judge),
            PartialCompletionEvaluator(model=judge),
            RecoveryStrategyEvaluator(model=judge),
        ],
    )


def run(prompt_version: str, repeats: int, out: Path, judge=None):
    judge = judge or telemetry.judge_model()
    cases = build_cases(repeats)
    experiment = build_experiment(cases, judge)
    task = telemetry.make_task(prompt_version, plugins_factory=lambda: [ChaosPlugin()],
                               sessions_dir=telemetry.SESSIONS_DIR / f"chaos-{prompt_version}")
    report = experiment.run_evaluations(task)
    out.parent.mkdir(parents=True, exist_ok=True)
    report.to_file(str(out))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", required=True, choices=["v1", "v2"])
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--fail-on", type=float, default=None)
    args = parser.parse_args()
    try:
        config.require_sandbox()
        config.model_id("target")
        config.model_id("judge")
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    report = run(args.prompt, args.repeats, args.out)
    print(f"prompt={args.prompt} repeats={args.repeats} overall_score={report.overall_score:.3f} cases={len(report.cases)}")
    if args.fail_on is not None and report.overall_score < args.fail_on:
        print(f"FAIL: {report.overall_score:.3f} < {args.fail_on}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
