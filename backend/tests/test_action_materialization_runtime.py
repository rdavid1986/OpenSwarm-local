from backend.apps.swarms.action_materialization_runtime import (
    build_action_materialization_evidence_plan,
    build_action_materialization_policy_gate,
    build_action_materialization_request,
    build_action_materialization_sequence,
    build_action_rollback_plan,
    build_command_materialization_plan,
    build_patch_materialization_plan,
    decide_action_materialization,
)


def assert_inert(contract):
    assert contract.can_execute is False
    assert getattr(contract, "can_write_files", False) is False
    assert getattr(contract, "can_apply_patch", False) is False
    assert getattr(contract, "can_execute_commands", False) is False
    assert getattr(contract, "contains_private_reasoning", False) is False


def test_materialization_request_normalizes_operations_and_commands_without_execution():
    request = build_action_materialization_request(
        candidate_id="candidate-1",
        source_contract_kind="tdd_green_patch_candidate",
        requested_operations=[{"path": "backend/app.py", "operation": "patch"}],
        requested_commands=["python -m pytest -q backend/tests/test_app.py"],
    )

    assert request.candidate_id == "candidate-1"
    assert request.requested_operations[0]["can_write"] is False
    assert request.requested_commands[0]["can_execute"] is False
    assert request.approval_required is True
    assert request.policy_matrix_required is True
    assert request.safeshell_required is True
    assert_inert(request)


def test_policy_gate_blocks_missing_approval_and_dangerous_commands():
    request = build_action_materialization_request(
        candidate_id="candidate-2",
        requested_commands=["rm -rf ."],
    )
    gate = build_action_materialization_policy_gate(request, policy_matrix_ref="", approval_id="", risk_level="high")

    assert gate.decision == "blocked"
    assert "missing_human_approval" in gate.blockers
    assert "missing_policy_matrix_ref" in gate.blockers
    assert "dangerous_command_detected" in gate.blockers
    assert gate.can_materialize is False
    assert_inert(gate)


def test_patch_and_command_plans_require_workspace_safeshell_and_approval():
    request = build_action_materialization_request(
        candidate_id="candidate-3",
        requested_operations=[{"path": "backend/example.py", "operation": "patch"}],
        requested_commands=["python -m pytest -q backend/tests/test_example.py"],
    )
    patch = build_patch_materialization_plan(request, workspace_id="candidate-workspace")
    command = build_command_materialization_plan(request, cwd=".", timeout_seconds=30)

    assert patch.workspace_id == "candidate-workspace"
    assert patch.file_operations[0]["operation"] == "patch"
    assert patch.can_apply_patch is False
    assert command.cwd == "."
    assert command.timeout_seconds == 30
    assert command.safeshell_required is True
    assert command.can_execute_commands is False
    assert_inert(patch)
    assert_inert(command)


def test_evidence_and_rollback_plans_are_required_before_materialization():
    request = build_action_materialization_request(candidate_id="candidate-4")
    evidence = build_action_materialization_evidence_plan(
        request,
        validation_commands=["python -m pytest -q backend/tests/test_example.py"],
    )
    rollback = build_action_rollback_plan(request)

    assert "diff_summary" in evidence.required_evidence
    assert evidence.validation_commands[0]["can_execute"] is False
    assert rollback.rollback_steps
    assert rollback.can_execute_rollback is False
    assert_inert(evidence)
    assert_inert(rollback)


def test_materialization_decision_stays_blocked_until_policy_and_evidence_are_complete():
    request = build_action_materialization_request(candidate_id="candidate-5")
    decision = decide_action_materialization(request=request)

    assert decision.decision == "blocked"
    assert "missing_human_approval" in decision.blockers
    assert "missing_policy_matrix_ref" in decision.blockers
    assert "missing_validation_commands" in decision.blockers
    assert decision.can_materialize is False
    assert_inert(decision)


def test_materialization_sequence_order_is_complete_and_inert():
    sequence = build_action_materialization_sequence(
        candidate_id="candidate-6",
        source_contract_kind="sdd_implementation_candidate",
        requested_operations=[{"path": "backend/example.py", "operation": "patch"}],
        requested_commands=["python -m pytest -q backend/tests/test_example.py"],
        validation_commands=["python -m pytest -q backend/tests/test_example.py"],
        workspace_id="candidate-workspace",
        cwd=".",
    )

    assert [item.materialization_kind for item in sequence] == [
        "action_materialization_request",
        "action_materialization_policy_gate",
        "patch_materialization_plan",
        "command_materialization_plan",
        "action_materialization_evidence_plan",
        "action_rollback_plan",
        "action_materialization_decision",
    ]
    for item in sequence:
        assert_inert(item)
