import pytest


def test_workflow_yaml_parses():
    """Verify that evals.yml is valid YAML."""
    try:
        import yaml
    except ImportError:
        pytest.skip("PyYAML not available")

    with open(".github/workflows/evals.yml") as f:
        yaml.safe_load(f)


def test_workflow_structure():
    """Verify workflow has required jobs and dependencies."""
    try:
        import yaml
    except ImportError:
        pytest.skip("PyYAML not available")

    with open(".github/workflows/evals.yml") as f:
        workflow = yaml.safe_load(f)

    # Check three jobs exist
    assert "chaos" in workflow["jobs"]
    assert "redteam-regression" in workflow["jobs"]
    assert "deploy" in workflow["jobs"]

    # Check deploy depends on both other jobs
    deploy_needs = workflow["jobs"]["deploy"]["needs"]
    assert "chaos" in deploy_needs
    assert "redteam-regression" in deploy_needs


def test_workflow_permissions():
    """Verify workflow has correct permissions."""
    try:
        import yaml
    except ImportError:
        pytest.skip("PyYAML not available")

    with open(".github/workflows/evals.yml") as f:
        workflow = yaml.safe_load(f)

    # Check id-token permission
    assert workflow["permissions"]["id-token"] == "write"


def test_workflow_chaos_fail_threshold():
    """Verify chaos job has correct fail-on threshold."""
    try:
        import yaml
    except ImportError:
        pytest.skip("PyYAML not available")

    with open(".github/workflows/evals.yml") as f:
        workflow = yaml.safe_load(f)

    # Find the chaos run step
    steps = workflow["jobs"]["chaos"]["steps"]
    chaos_run_step = None
    for step in steps:
        if "run" in step and "evals.chaos" in step["run"]:
            chaos_run_step = step
            break

    assert chaos_run_step is not None, "Chaos run step not found"
    assert "--fail-on 0.8" in chaos_run_step["run"]


def test_workflow_env_variables():
    """Verify workflow defines required environment variables."""
    try:
        import yaml
    except ImportError:
        pytest.skip("PyYAML not available")

    with open(".github/workflows/evals.yml") as f:
        workflow = yaml.safe_load(f)

    env = workflow["env"]
    assert "TARGET_MODEL_ID" in env
    assert "JUDGE_MODEL_ID" in env
    assert "ATTACKER_MODEL_ID" in env
    assert "SENTINEL_ROLE_ARN" in env
