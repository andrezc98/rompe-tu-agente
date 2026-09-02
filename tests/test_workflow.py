from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="PyYAML not available")

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "evals.yml"


@pytest.fixture(scope="module")
def workflow() -> dict:
    """Parsing it is the YAML-validity check; every other test reads the parsed tree."""
    return yaml.safe_load(WORKFLOW.read_text())


def test_workflow_structure(workflow):
    """Verify workflow has required jobs and dependencies."""
    assert "chaos" in workflow["jobs"]
    assert "redteam-regression" in workflow["jobs"]
    assert "deploy" in workflow["jobs"]

    deploy_needs = workflow["jobs"]["deploy"]["needs"]
    assert "chaos" in deploy_needs
    assert "redteam-regression" in deploy_needs


def test_workflow_permissions(workflow):
    assert workflow["permissions"]["id-token"] == "write"


def test_workflow_chaos_fail_threshold(workflow):
    """The gate runs the module entrypoint (it owns the ChaosPlugin wiring), with the 0.8 floor."""
    steps = workflow["jobs"]["chaos"]["steps"]
    chaos_run_step = next((s for s in steps if "run" in s and "evals.chaos" in s["run"]), None)

    assert chaos_run_step is not None, "Chaos run step not found"
    assert "--fail-on 0.8" in chaos_run_step["run"]


def test_workflow_env_variables(workflow):
    env = workflow["env"]
    assert "TARGET_MODEL_ID" in env
    assert "JUDGE_MODEL_ID" in env
    assert "ATTACKER_MODEL_ID" in env
    assert "SENTINEL_ROLE_ARN" in env


def test_role_arn_comes_from_secrets_not_variables(workflow):
    # The role ARN carries the account id, and repository variables are readable by anyone who
    # can read the repo. It has to be a secret.
    assert workflow["env"]["SENTINEL_ROLE_ARN"] == "${{ secrets.SENTINEL_ROLE_ARN }}"
