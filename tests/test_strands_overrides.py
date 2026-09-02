import inspect

from strands_evals.experimental.redteam.strategies import crescendo
from strands_evals.experimental.redteam.strategies.crescendo import crescendo_v0
from strands_evals.experimental.redteam.strategies.goat import goat_v0

from evals import strands_overrides


def test_apply_replaces_the_adversarial_framing_and_keeps_the_placeholders():
    strands_overrides.apply()
    for mod in (goat_v0, crescendo_v0):
        assert "Adversarial Actor Simulation" not in mod.ATTACKER_SYSTEM_PROMPT
        assert "{actor_goal}" in mod.ATTACKER_SYSTEM_PROMPT
    assert "authorized" in goat_v0.ATTACKER_SYSTEM_PROMPT and "authorized" in crescendo_v0.ATTACKER_SYSTEM_PROMPT
    assert "{actor_goal}" in goat_v0.INITIAL_TURN_PROMPT and "{last_reply}" in goat_v0.FOLLOWUP_TURN_PROMPT
    assert crescendo.gen_escalating_question is strands_overrides.gen_escalating_question
    assert "Begin the attack" not in inspect.getsource(crescendo.gen_escalating_question)


def test_importing_redteam_and_regression_applies_the_override():
    import evals.redteam  # noqa: F401
    import evals.regression  # noqa: F401

    assert crescendo.gen_escalating_question is strands_overrides.gen_escalating_question


def test_crescendo_counts_only_mutating_tools_as_compliance():
    from types import SimpleNamespace
    strands_overrides.apply()
    assert crescendo.CrescendoStrategy.run_attack is strands_overrides.crescendo_run_attack

    class FakeSession:
        """Target that calls a read tool every turn and never the mutating one."""
        def __init__(self): self.trace = []
        def snapshot(self): return SimpleNamespace(trace_len=len(self.trace))
        def invoke(self, q): self.trace.append({"name": "get_alarms", "input": {}}); return f"leido: {q[:10]}"
        def restore(self, snap): self.trace = self.trace[: snap.trace_len]

    strat = crescendo.CrescendoStrategy(max_turns=3, model="x")
    strat._build_attacker = lambda goal, model: None
    strat._build_judge = lambda model: None
    strat._build_refusal_judge = lambda model: None
    turns = iter(["p1", "p2", "p3"])
    crescendo.gen_escalating_question = lambda attacker, goal, conv, last: next(turns)
    crescendo.is_refusal = lambda response, make_judge=None: False
    crescendo.success_score = lambda make_judge, response, criteria: 0.0
    case = SimpleNamespace(config=SimpleNamespace(attack_goal=SimpleNamespace(actor_goal="g", success_criteria="c")))
    try:
        result = strat.run_attack(case, FakeSession(), max_turns=3)
    finally:
        strands_overrides.apply()  # restore the real gen_escalating_question
    assert result.metadata["turns_used"] == 3 and result.strategy_succeeded is False
