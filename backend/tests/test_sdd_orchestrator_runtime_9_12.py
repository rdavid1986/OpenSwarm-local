from backend.apps.swarms.sdd_orchestrator_runtime import (
    build_sdd_delegation_decision,
    build_sdd_evidence_trace,
    build_sdd_implementation_candidate,
    build_sdd_runtime_9_12_sequence,
    build_sdd_verification_report,
)


def assert_inert(contract):
    assert contract.can_execute is False
    assert getattr(contract, "can_write_files", False) is False
    assert getattr(contract, "can_apply_patch", False) is False
    assert getattr(contract, "can_execute_commands", False) is False
    assert getattr(contract, "contains_private_reasoning", False) is False


def test_sdd_implementation_candidate_uses_action_materialization_without_runtime_execution():
    candidate = build_sdd_implementation_candidate(
        candidate_id="candidate-1",
        task_id="task-1",
        patch_candidate={"diff_summary": "Add implementation"},
        touched_files=["backend/apps/example.py"],
        validation_commands=["python -m pytest -q backend/tests/test_example.py"],
        workspace_id="candidate-workspace",
        cwd=".",
    )

    assert candidate.sdd_contract_kind == "sdd_implementation_candidate"
    assert candidate.materialization_required is True
    assert candidate.materialization_request["candidate_id"] == "candidate-1"
    assert candidate.materialization_decision["decision"] == "blocked"
    assert "missing_human_approval" in candidate.blockers
    assert candidate.can_materialize is False
    assert_inert(candidate)


def test_sdd_verification_report_blocks_completion_without_full_evidence():
    report = build_sdd_verification_report(
        candidate_id="candidate-2",
        spec_compliance="passed",
        acceptance_result="passed",
        test_results=[{"command": "pytest", "status": "passed"}],
        regression_result="unmeasured",
        design_compliance="passed",
        evidence_quality="missing",
    )

    assert report.can_mark_verified is False
    assert report.can_mark_completed is False
    assert "regression_not_confirmed" in report.blockers
    assert "evidence_quality_insufficient" in report.blockers
    assert_inert(report)


def test_sdd_verification_report_can_be_verified_but_not_completed_by_contract_alone():
    report = build_sdd_verification_report(
        candidate_id="candidate-3",
        spec_compliance="passed",
        acceptance_result="passed",
        test_results=[{"command": "pytest", "status": "passed"}],
        regression_result="passed",
        design_compliance="passed",
        evidence_quality="sufficient",
    )

    assert report.can_mark_verified is True
    assert report.can_mark_completed is False
    assert report.blockers == []
    assert_inert(report)


def test_sdd_evidence_trace_requires_real_refs_before_completion():
    trace = build_sdd_evidence_trace(candidate_id="candidate-4")
    complete_like = build_sdd_evidence_trace(
        candidate_id="candidate-4",
        evidence_refs=["evidence:1"],
        validation_refs=["validation:1"],
        materialization_refs=["materialization:1"],
        process_trace_refs=["trace:1"],
        changed_files=["backend/apps/example.py"],
    )

    assert trace.evidence_quality == "missing"
    assert "attach_evidence_refs" in trace.required_actions
    assert complete_like.evidence_quality == "sufficient"
    assert complete_like.can_mark_complete is False
    assert_inert(trace)
    assert_inert(complete_like)


def test_sdd_delegation_decision_routes_stage_without_executing_handoff():
    decision = build_sdd_delegation_decision(
        current_stage="implementation",
        input_contract_kind="sdd_task_dag_contract",
        context_packet_refs=["ctx:1"],
        handoff_payload={"task_id": "task-1"},
    )

    assert decision.next_role == "implementer"
    assert decision.expected_output_contract_kind == "sdd_implementation_candidate"
    assert decision.can_delegate is False
    assert decision.can_execute_handoffs is False
    assert_inert(decision)


def test_sdd_runtime_9_12_sequence_order_is_correct_and_inert():
    sequence = build_sdd_runtime_9_12_sequence(
        candidate_id="candidate-5",
        task_id="task-5",
        patch_candidate={"diff_summary": "candidate"},
        touched_files=["backend/apps/example.py"],
        validation_commands=["python -m pytest -q backend/tests/test_example.py"],
        workspace_id="candidate-workspace",
        cwd=".",
    )

    assert [item.sdd_contract_kind for item in sequence] == [
        "sdd_implementation_candidate",
        "sdd_verification_report",
        "sdd_evidence_trace",
        "sdd_delegation_decision",
    ]
    for item in sequence:
        assert_inert(item)
