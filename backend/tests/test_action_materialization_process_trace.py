from backend.apps.swarms.action_materialization_runtime import (
    build_action_materialization_request,
    build_action_materialization_sequence,
    decide_action_materialization,
)
from backend.apps.swarms.process_trace_builder import build_process_trace_item_from_source, normalize_process_trace_source_kind


def assert_action_materialization_trace(source):
    assert normalize_process_trace_source_kind(source) == "action_materialization_runtime"
    item = build_process_trace_item_from_source(source)
    assert item["metadata"]["source_kind"] == "action_materialization_runtime"
    assert item["subsystem"] == "ActionCore"
    assert item["details"]["can_execute"] is False
    assert item["details"]["can_write_files"] is False
    assert item["details"]["can_apply_patch"] is False
    assert item["details"]["can_execute_commands"] is False
    assert item["details"]["can_activate_tools"] is False
    assert item["details"]["can_activate_mcp"] is False
    assert item["details"]["can_write_memory"] is False
    assert item["details"]["contains_private_reasoning"] is False
    return item


def test_materialization_sequence_process_trace_is_visible_and_safe():
    sequence = build_action_materialization_sequence(
        candidate_id="candidate-trace",
        requested_operations=[{"path": "backend/example.py", "operation": "patch"}],
        requested_commands=["python -m pytest -q backend/tests/test_example.py"],
        validation_commands=["python -m pytest -q backend/tests/test_example.py"],
        workspace_id="candidate-workspace",
        cwd=".",
    )
    items = [assert_action_materialization_trace(source) for source in sequence]

    assert [item["details"]["contract_kind"] for item in items] == [
        "action_materialization_request",
        "action_materialization_policy_gate",
        "patch_materialization_plan",
        "command_materialization_plan",
        "action_materialization_evidence_plan",
        "action_rollback_plan",
        "action_materialization_decision",
    ]


def test_materialization_decision_trace_blocks_without_policy_approval_and_evidence():
    request = build_action_materialization_request(candidate_id="blocked")
    decision = decide_action_materialization(request=request)
    item = assert_action_materialization_trace(decision)

    assert item["status"] == "blocked"
    assert "missing_human_approval" in item["details"]["blockers"]
    assert "missing_policy_matrix_ref" in item["details"]["blockers"]
    assert "missing_validation_commands" in item["details"]["blockers"]


def test_materialization_trace_redacts_sensitive_values():
    request = build_action_materialization_request(
        candidate_id="secret-test",
        requested_commands=["echo api_key=secret"],
    )
    item = assert_action_materialization_trace(request)
    rendered = str(item).lower()

    assert "api_key=secret" not in rendered
