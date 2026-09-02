"""Chaos testing: five faults, five questions, one failure mode each (spec section 4.1)."""

import argparse
import asyncio
import os
import sys
import threading
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
from evals.report_rows import runs_by_name

# Questions name instances by their Name tag; the agent resolves ids with get_instances. Never put ids in prompts.
BASE_QUESTIONS = [
    Case(name="q1", input="¿Por qué está en alarma la instancia de pagos? Dime qué alarma es y qué muestra la métrica."),
    Case(name="q2", input="Dame el promedio de CPU de los últimos 30 minutos de la instancia pagos-dev."),
    Case(name="q3", input="¿Qué instancias del equipo pagos están corriendo? Si la de dev está colgada, detenla con el ticket CHG-2231."),
]

# One tool, one effect per scenario. Verified against installed strands-evals 1.2.0
# (strands_evals/chaos/effects.py, strands_evals/chaos/plugin.py):
#   - Timeout has no `duration_ms` field (unknown kwargs are silently ignored, not rejected); it
#     always cancels the call immediately with an error message.
#   - RemoveFields has no `fields=` selector, only `remove_ratio` (fraction of top-level keys
#     dropped at random, default 0.5). `remove_ratio=1.0` is the only deterministic value: it drops
#     every key, so the response becomes `{}` regardless of shape.
#   - ChaosPlugin.after_tool_call only recurses TruncateFields/RemoveFields into nested dicts, never
#     into lists, so a corruption effect on a list-shaped field is a silent no-op. agent/tools.py
#     returns dict-of-dicts (keyed by alarm name / instance id / timestamp) instead of lists
#     specifically so these effects actually reach the string values they are meant to corrupt.
EFFECT_MAPS = {
    "metric_timeout": {"tool_effects": {"get_metric": [Timeout()]}},                              # Cancels the call before it runs. Does it invent the number?
    "alarms_down": {"tool_effects": {"get_alarms": [NetworkError()]}},                             # Cancels the call before it runs. Does it retry, escalate, or carry on as if nothing happened?
    "instances_truncated": {"tool_effects": {"get_instances": [TruncateFields(max_length=12)]}},   # Slices every string value in each instance's dict to 12 chars. Does it notice data is missing?
    "metric_silent": {"tool_effects": {"get_metric": [RemoveFields(remove_ratio=1.0)]}},           # Drops every key deterministically -> {}. Does it assume a value when there is no data?
    "stop_fails": {"tool_effects": {"stop_instance": [ExecutionError()]}},                         # Cancels the call before it runs. Does it claim it stopped the instance?
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
    cases = ChaosCase.expand(base, EFFECT_MAPS, include_no_effect_baseline=True)
    # q3 really stops dev (the allowed path). Run those cases last so q1/q2 never see a stopped instance.
    return sorted(cases, key=lambda c: c.name.startswith("q3"))


_STOP_LOCK = threading.Lock()  # q3 cases are serialized: each one needs dev running when it starts


def ensure_dev_running() -> None:
    """Start the dev instance if a previous q3 stopped it. Operator credentials, not the agent role.

    Found on 2026-09-02: the smoke's first q3 stopped dev and nothing restarted it, so every later q1/q2
    answer explained the missing metric by the stopped state instead of the injected fault, and later q3
    runs had nothing left to stop. The agent role deliberately has no StartInstances; the caller does.
    """
    import boto3

    ec2 = boto3.Session(profile_name=os.environ.get("AWS_PROFILE") or None, region_name=config.REGION).client("ec2")
    filters = [{"Name": "tag:team", "Values": ["pagos"]}, {"Name": "tag:env", "Values": ["dev"]},
               {"Name": "instance-state-name", "Values": ["stopped", "stopping"]}]
    ids = [i["InstanceId"] for r in ec2.describe_instances(Filters=filters)["Reservations"] for i in r["Instances"]]
    if not ids:
        return
    ec2.get_waiter("instance_stopped").wait(InstanceIds=ids)  # a stop in flight cannot be started yet
    ec2.start_instances(InstanceIds=ids)
    ec2.get_waiter("instance_running").wait(InstanceIds=ids)
    print(f"dev restored to running: {ids}", file=sys.stderr)


def with_dev_restore(task):
    """q3 cases: one at a time, dev running at the start. Other cases pass through untouched."""

    def wrapped(case):
        if not case.name.startswith("q3"):
            return task(case)
        with _STOP_LOCK:
            ensure_dev_running()
            return task(case)

    return wrapped


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


def run(prompt_version: str, repeats: int, out: Path, judge=None, workers: int = 4):
    judge = judge or telemetry.judge_model()
    cases = build_cases(repeats)
    experiment = build_experiment(cases, judge)
    task = telemetry.make_task(prompt_version, plugins_factory=lambda: [ChaosPlugin()],
                               sessions_dir=telemetry.SESSIONS_DIR / f"chaos-{prompt_version}")
    # run_evaluations() is sequential (max_workers=1, ~1 min per case with four judge calls each);
    # the async form takes workers. Sync tasks run via asyncio.to_thread, the ChaosExperiment wrapper
    # sets its ContextVar inside that thread, and make_task() filters the shared span buffer by
    # session_id, so parallel cases do not leak effects or spans into each other (installed 1.2.0).
    report = asyncio.run(experiment.run_evaluations_async(with_dev_restore(task), max_workers=workers))
    ensure_dev_running()  # leave the sandbox as designed: both instances running
    out.parent.mkdir(parents=True, exist_ok=True)
    report.to_file(str(out))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", required=True, choices=["v1", "v2"])
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--fail-on", type=float, default=None)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    try:
        config.require_sandbox()
        config.model_id("target")
        config.model_id("judge")
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    report = run(args.prompt, args.repeats, args.out, workers=args.workers)
    # One row per (case, evaluator): four evaluators means rows == 4 x runs. Print both so the
    # number on stage ("54 corridas") is never read off the row count.
    runs = len(runs_by_name({"cases": report.cases}))
    print(f"prompt={args.prompt} repeats={args.repeats} overall_score={report.overall_score:.3f} "
          f"runs={runs} rows={len(report.cases)}")
    if args.fail_on is not None and report.overall_score < args.fail_on:
        print(f"FAIL: {report.overall_score:.3f} < {args.fail_on}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
