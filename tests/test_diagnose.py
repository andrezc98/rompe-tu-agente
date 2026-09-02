from types import SimpleNamespace

from evals import diagnose


def test_bucket_permissions_beats_tool():
    assert diagnose.bucket("stop_instance tool call", "config", "AccessDenied from EC2 StopInstances") == "permisos"


def test_bucket_tool_error():
    assert diagnose.bucket("get_metric tool", "tool", "tool timeout after 500ms") == "tool"


def test_bucket_model_when_prompt_or_reasoning():
    assert diagnose.bucket("assistant response", "prompt", "the model asserted a value not present in tool output") == "modelo"


def test_bucket_default_execution():
    assert diagnose.bucket("agent loop", "code", "exception while serializing") == "ejecucion"


def test_bucket_iam_word_boundary_does_not_match_diamante():
    # "diamante" contains "iam" as a raw substring; a naive `in` check would misread this as
    # a permissions failure. Word-boundary matching must not trigger on it.
    assert diagnose.bucket("agent loop", "code", "el cliente compro un diamante") == "ejecucion"


def _root_cause(location, fix_type, causality, root_cause_explanation, fix_recommendation):
    # Mirrors strands_evals.types.detector.RCAItem (verified in
    # .venv/lib/python3.13/site-packages/strands_evals/types/detector.py).
    return SimpleNamespace(
        failure_span_id="span-1",
        location=location,
        causality=causality,
        propagation_impact=["TASK_TERMINATION"],
        failure_detection_timing="IMMEDIATELY_AT_OCCURRENCE",
        completion_status="COMPLETE_FAILURE",
        root_cause_explanation=root_cause_explanation,
        fix_type=fix_type,
        fix_recommendation=fix_recommendation,
    )


def test_render_shows_sdk_verbatim_next_to_our_reading():
    # Mirrors strands_evals.types.detector.DiagnosisResult/FailureItem/RCAItem field names,
    # confirmed against the installed strands-agents-evals 1.2.0 (not its published docs).
    result = SimpleNamespace(
        session_id="sess-123",
        failures=[
            SimpleNamespace(
                span_id="span-1",
                category=["tool_error", "hallucination"],
                confidence=[0.9, 0.4],
                evidence=["get_metric timed out", "agent invented a CPU value"],
            )
        ],
        root_causes=[
            _root_cause(
                location="span-1",
                fix_type="TOOL_DESCRIPTION_FIX",
                causality="PRIMARY_FAILURE",
                root_cause_explanation="The get_metric tool call timed out, so the agent invented a value.",
                fix_recommendation="Add a timeout retry and require the agent to say when data is missing.",
            )
        ],
    )

    out = diagnose.render(result)

    assert "sess-123" in out
    assert "1 failures, 1 root causes" in out
    assert "falla en span span-1" in out
    assert "tool_error, hallucination" in out
    assert "conf 0.90, 0.40" in out
    assert "evidencia: get_metric timed out" in out
    assert "evidencia: agent invented a CPU value" in out
    assert "SDK (verbatim)" in out
    assert "| tool" in out  # our reading, computed by bucket()
    assert "fix: Add a timeout retry" in out
