from backend.apps.swarms.tdd_agent_runtime import (
    build_tdd_agent_manifest_role,
    build_tdd_contract_sequence,
    build_tdd_evidence_report,
    build_tdd_green_patch_candidate,
    build_tdd_red_phase_contract,
    build_tdd_refactor_contract,
    build_tdd_test_list_contract,
)


def assert_inert(contract):
    assert contract.can_execute is False
    assert getattr(contract, "can_write_files", False) is False
    assert getattr(contract, "can_write_tests", False) is False
    assert getattr(contract, "can_apply_patch", False) is False
    assert getattr(contract, "contains_private_reasoning", False) is False


def test_tdd_agent_manifest_role_is_declared_but_not_materialized():
    role = build_tdd_agent_manifest_role()

    assert role.aliases == ["@tdd", "@tester", "@qa"]
    assert "red_green_refactor" in role.capabilities
    assert "no_green_without_evidence" in role.boundaries
    assert role.policy_matrix_required is True
    assert role.can_create_agent is False
    assert role.can_create_miniagent is False
    assert_inert(role)


def test_tdd_test_list_contract_is_reviewable_without_writing_tests():
    plan = build_tdd_test_list_contract(
        feature_under_test="Agent mention routing",
        acceptance_criteria=["Unknown agents are blocked"],
        test_cases=[{"name": "blocks unknown mention", "expected": "blocked"}],
        edge_cases=["multiple mentions"],
        fixtures_needed=["manifest"],
        files_likely_touched=["backend/tests/test_agent_mention_routing.py"],
    )

    assert plan.feature_under_test == "Agent mention routing"
    assert plan.acceptance_criteria == ["Unknown agents are blocked"]
    assert plan.test_cases[0]["name"] == "blocks unknown mention"
    assert plan.test_plan_hash != "unknown"
    assert_inert(plan)


def test_red_phase_contract_requires_dry_run_and_test_runner_gate():
    red = build_tdd_red_phase_contract(
        target_test_file="backend/tests/test_example.py",
        test_name="test_red_first",
        behavior_under_test="Missing feature fails",
        expected_failure_reason="Implementation missing",
        command_to_run="python -m pytest -q backend/tests/test_example.py",
    )

    assert red.dry_run_only is True
    assert red.safeshell_required is True
    assert red.test_runner_required is True
    assert red.can_execute_tests is False
    assert "failing_test_output" in red.evidence_required
    assert_inert(red)


def test_green_patch_candidate_never_applies_patch_without_materialization():
    green = build_tdd_green_patch_candidate(
        minimal_patch_candidate={"diff_summary": "Add minimal branch"},
        touched_files=["backend/apps/example.py"],
        expected_test_command="python -m pytest -q backend/tests/test_example.py",
        expected_pass_condition="Target red test passes.",
        regression_scope=["backend/tests/test_example.py"],
    )

    assert green.materialization_required is True
    assert green.approval_required is True
    assert "request_action_materialization_before_patch" in green.required_actions
    assert green.can_apply_patch is False
    assert green.can_execute_tests is False
    assert_inert(green)


def test_refactor_contract_requires_green_state_and_regression_evidence():
    refactor = build_tdd_refactor_contract(
        refactor_intent="Extract helper without behavior change",
        invariant_tests=["python -m pytest -q backend/tests/test_example.py"],
        affected_symbols=["ExampleService"],
    )

    assert refactor.no_behavior_change_claim is True
    assert refactor.pre_refactor_green_required is True
    assert refactor.post_refactor_green_required is True
    assert "confirm_pre_refactor_green_state" in refactor.required_actions
    assert_inert(refactor)


def test_evidence_report_cannot_mark_green_without_passing_and_regression_refs():
    missing = build_tdd_evidence_report(phase="green", passing_output_ref="", regression_coverage=[])
    sufficient = build_tdd_evidence_report(
        phase="green",
        test_command="python -m pytest -q backend/tests/test_example.py",
        passing_output_ref="evidence:pytest-pass",
        regression_coverage=["backend/tests/test_example.py"],
    )

    assert missing.can_mark_green is False
    assert "attach_passing_test_output" in missing.required_actions
    assert sufficient.can_mark_green is True
    assert sufficient.can_execute_tests is False
    assert_inert(sufficient)


def test_tdd_contract_sequence_order_is_red_green_refactor_ready_without_runtime_effects():
    sequence = build_tdd_contract_sequence(
        feature_under_test="TDD contracts",
        acceptance_criteria=["contracts are inert"],
        test_cases=[{"name": "contracts are inert"}],
        target_test_file="backend/tests/test_tdd_agent_runtime.py",
        test_name="test_contracts_are_inert",
        command_to_run="python -m pytest -q backend/tests/test_tdd_agent_runtime.py",
    )

    assert [item.tdd_contract_kind for item in sequence] == [
        "tdd_agent_manifest_role",
        "tdd_test_list_contract",
        "tdd_red_phase_contract",
        "tdd_green_patch_candidate",
        "tdd_refactor_contract",
        "tdd_evidence_report",
    ]
    for item in sequence:
        assert_inert(item)
