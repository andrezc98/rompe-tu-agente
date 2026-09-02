"""One chaos run is several report rows. Group them back, once, for every consumer.

`Experiment.run_evaluations` builds one `EvaluationReport` per evaluator and flattens them
(strands_evals/experiment.py:693-716), tagging each row with the evaluator that produced it
(`{**case_data, "evaluator": eval_name, "evaluator_type": ...}`, experiment.py:685-687). So a
54-run chaos experiment with four evaluators writes 216 rows and every case name appears four
times. Anything that counts runs -- pass rates, human verdicts -- has to group first.
"""


def runs_by_name(report: dict) -> dict[str, list[int]]:
    """Row indexes of each run, keyed by case name, in report order."""
    runs: dict[str, list[int]] = {}
    for i, case in enumerate(report.get("cases", [])):
        runs.setdefault(case.get("name", ""), []).append(i)
    return runs
