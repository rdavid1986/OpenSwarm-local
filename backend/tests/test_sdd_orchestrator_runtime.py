from backend.apps.swarms.sdd_orchestrator_runtime import (
    build_sdd_contract_sequence,
    build_sdd_design_contract,
    build_sdd_explorer_context,
    build_sdd_policy_review_contract,
    build_sdd_proposal,
    build_sdd_role_manifest,
    build_sdd_spec_contract,
    build_sdd_task_dag_contract,
    build_sdd_test_strategy_contract,
)


def assert_inert(contract):
    assert contract.can_execute is False
    assert getattr(contract, "can_write_files", False) is False
    assert getattr(contract, "can_activate_tools", False) is False
    assert getattr(contract, "contains_private_reasoning", False) is False


def test_sdd_role_manifest_declares_specialized_roles_without_creating_agents():
    manifest = build_sdd_role_manifest()

    assert "explorer" in manifest.role_order
    assert "spec_writer" in manifest.role_order
    assert "risk_policy_reviewer" in manifest.role_order
    assert "test_strategist" in manifest.role_order
    assert len(manifest.roles) >= 10
    assert manifest.can_create_agent is False
    assert manifest.can_create_miniagent is False
    assert_inert(manifest)


def test_explorer_context_excludes_heavy_paths_and_remains_side_effect_free():
    context = build_sdd_explorer_context(
        files_considered=["backend/apps/swarms/swarms.py", ".venv/lib/site.py", "frontend/node_modules/pkg/index.js"],
        symbols_considered=["experimental_swarm_chat"],
        missing_context=["exact endpoint range"],
    )

    assert context.files_considered == ["backend/apps/swarms/swarms.py"]
    assert ".venv/lib/site.py" in context.excluded_files
    assert "frontend/node_modules/pkg/index.js" in context.excluded_files
    assert "resolve_missing_context_before_design" in context.required_actions
    assert_inert(context)


def test_sdd_proposal_spec_design_task_contracts_are_verifiable_before_runtime():
    proposal = build_sdd_proposal(
        proposed_change="Add SDD contracts",
        user_value="Visible planning",
        technical_value="Traceable side-effect-free contracts",
        scope=["backend/contracts"],
    )
    spec = build_sdd_spec_contract(
        requirements=["Contracts expose SDD stages"],
        acceptance_criteria=["Each contract is inert", "Each contract has ProcessTrace"],
        scenarios=["Planner prepares SDD sequence"],
    )
    design = build_sdd_design_contract(
        affected_subsystems=["SwarmCore", "ProcessTrace"],
        process_trace_requirements=["show contract kind"],
    )
    dag = build_sdd_task_dag_contract(
        task_nodes=[{"task_id": "contracts", "title": "Add contracts"}],
        dependencies=[],
        assigned_roles={"contracts": "designer"},
        validation_plan=["py_compile", "pytest"],
    )

    assert proposal.blockers == []
    assert spec.verifiable is True
    assert design.approval_required is True
    assert dag.dag_ready is True
    for contract in [proposal, spec, design, dag]:
        assert_inert(contract)


def test_sdd_policy_and_test_strategy_require_gates_before_execution():
    policy = build_sdd_policy_review_contract(
        risk_level="high",
        policy_matrix_refs=["policy_matrix_runtime"],
        blocked_actions=["write_files_without_approval"],
    )
    strategy = build_sdd_test_strategy_contract(
        test_strategy="contract tests before runtime",
        test_list=["test_sdd_contracts_are_inert"],
        regression_scope=["process_trace"],
        red_phase_candidates=["missing ProcessTrace contract"],
    )

    assert policy.decision == "blocked"
    assert "remove_or_approve_blocked_actions" in policy.required_actions
    assert strategy.tdd_bridge_required is True
    assert strategy.can_write_tests is False
    assert strategy.can_execute_tests is False
    assert_inert(policy)
    assert_inert(strategy)


def test_sdd_contract_sequence_uses_correct_order_and_no_runtime_effects():
    sequence = build_sdd_contract_sequence(
        objective="Build SDD contracts",
        files_considered=["backend/apps/swarms/process_trace_builder.py"],
        requirements=["Flow roles exist"],
        acceptance_criteria=["Contracts are side-effect-free"],
        task_nodes=[{"task_id": "sdd-contracts"}],
    )

    assert [item.sdd_contract_kind for item in sequence] == [
        "sdd_role_manifest",
        "sdd_explorer_context",
        "sdd_proposal",
        "sdd_spec_contract",
        "sdd_design_contract",
        "sdd_task_dag_contract",
        "sdd_policy_review_contract",
        "sdd_test_strategy_contract",
    ]
    for item in sequence:
        assert_inert(item)
