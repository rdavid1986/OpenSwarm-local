from backend.apps.swarms.process_trace_builder import build_process_trace_item_from_source, normalize_process_trace_source_kind
from backend.apps.swarms.sdd_orchestrator_runtime import (
    build_sdd_delegation_decision,
    build_sdd_evidence_trace,
    build_sdd_implementation_candidate,
    build_sdd_runtime_9_12_sequence,
    build_sdd_verification_report,
)


def assert_sdd_trace(source):
    assert normalize_process_trace_source_kind(source) == "sdd_orchestrator_runtime"
    item = build_process_trace_item_from_source(source)
    assert item["metadata"]["source_kind"] == "sdd_orchestrator_runtime"
    assert item["subsystem"] == "SwarmCore"
    assert item["details"]["can_execute"] is False
    assert item["details"]["can_write_files"] is False
    assert item["details"]["can_apply_patch"] is False
    assert item["details"]["can_execute_commands"] is False
    assert item["details"]["can_create_agent"] is False
    assert item["details"]["can_create_miniagent"] is False
    assert item["details"]["can_activate_tools"] is False
    assert item["details"]["can_execute_handoffs"] is False
    assert item["details"]["can_write_memory"] is False
    assert item["details"]["contains_private_reasoning"] is False
    return item


def test_sdd_runtime_9_12_process_trace_contracts_are_visible():
    sequence = build_sdd_runtime_9_12_sequence(
        candidate_id="candidate-trace",
        task_id="task-trace",
        patch_candidate={"diff_summary": "candidate"},
        touched_files=["backend/apps/example.py"],
        validation_commands=["python -m pytest -q backend/tests/test_example.py"],
        workspace_id="candidate-workspace",
        cwd=".",
    )

    items = [assert_sdd_trace(source) for source in sequence]

    assert [item["details"]["contract_kind"] for item in items] == [
        "sdd_implementation_candidate",
        "sdd_verification_report",
        "sdd_evidence_trace",
        "sdd_delegation_decision",
    ]
    assert items[0]["details"]["materialization_decision"]["decision"] == "blocked"
    assert items[0]["details"]["can_materialize"] is False


def test_individual_runtime_contract_traces_include_key_fields():
    implementation = build_sdd_implementation_candidate(candidate_id="impl", touched_files=["backend/app.py"])
    verification = build_sdd_verification_report(candidate_id="impl")
    evidence = build_sdd_evidence_trace(candidate_id="impl")
    delegation = build_sdd_delegation_decision(current_stage="verification", input_contract_kind="sdd_implementation_candidate")

    impl_item = assert_sdd_trace(implementation)
    verify_item = assert_sdd_trace(verification)
    evidence_item = assert_sdd_trace(evidence)
    delegation_item = assert_sdd_trace(delegation)

    assert impl_item["details"]["candidate_id"] == "impl"
    assert impl_item["details"]["materialization_request"]["candidate_id"] == "impl"
    assert "spec_compliance_not_confirmed" in verify_item["details"]["blockers"]
    assert evidence_item["details"]["evidence_quality"] == "missing"
    assert delegation_item["details"]["next_role"] == "verifier"
