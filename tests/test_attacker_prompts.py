import inspect

from strands_evals.experimental.redteam.strategies import crescendo
from strands_evals.experimental.redteam.strategies.crescendo import crescendo_v0
from strands_evals.experimental.redteam.strategies.goat import goat_v0

from evals import attacker_prompts


def test_apply_replaces_the_adversarial_framing_and_keeps_the_placeholders():
    attacker_prompts.apply()
    for mod in (goat_v0, crescendo_v0):
        assert "Adversarial Actor Simulation" not in mod.ATTACKER_SYSTEM_PROMPT
        assert "{actor_goal}" in mod.ATTACKER_SYSTEM_PROMPT
    assert "authorized" in goat_v0.ATTACKER_SYSTEM_PROMPT and "authorized" in crescendo_v0.ATTACKER_SYSTEM_PROMPT
    assert "{actor_goal}" in goat_v0.INITIAL_TURN_PROMPT and "{last_reply}" in goat_v0.FOLLOWUP_TURN_PROMPT
    assert crescendo.gen_escalating_question is attacker_prompts.gen_escalating_question
    assert "Begin the attack" not in inspect.getsource(crescendo.gen_escalating_question)


def test_importing_redteam_and_regression_applies_the_override():
    import evals.redteam  # noqa: F401
    import evals.regression  # noqa: F401

    assert crescendo.gen_escalating_question is attacker_prompts.gen_escalating_question
