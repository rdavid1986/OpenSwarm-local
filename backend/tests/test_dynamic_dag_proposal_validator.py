from backend.apps.agents.orchestration.models import AgentContract, SwarmState, TaskNode
from backend.apps.agents.orchestration.orchestrator import SwarmOrchestrator
from backend.apps.agents.runtime.experimental_task_type_registry import classify_experimental_task, get_experimental_task_spec


def _contract_for(task_type: str, *, role: str) -> AgentContract:
    spec = get_experimental_task_spec(task_type)
    return AgentContract(
        role=role,
        objective=f"Contract for {task_type}",
        allowed_tools=list(spec.allowed_tools),
        output_contract=dict(spec.output_contract),
    )


def _assert_only_base_coordinator_contracts(contracts):
    assert all(contract.role == "CoordinatorAgent" for contract in contracts)


def test_dag_proposal_validator_accepts_known_task_with_valid_contract():
    orchestrator = SwarmOrchestrator()
    contract = _contract_for("create_readme", role="DocumentationAgent")
    task = TaskNode(
        title="Create implementation brief README.md",
        objective="Create README.md",
        assigned_contract_id=contract.id,
    )
    swarm = SwarmState(
        title="Test",
        user_prompt="Test",
        contracts=[contract],
        tasks=[task],
    )

    assert orchestrator._validate_dag_proposal_state(swarm) == []


def test_dag_proposal_validator_rejects_unknown_dependency():
    orchestrator = SwarmOrchestrator()
    contract = _contract_for("create_readme", role="DocumentationAgent")
    task = TaskNode(
        title="Create implementation brief README.md",
        objective="Create README.md",
        assigned_contract_id=contract.id,
        depends_on=["missing-task"],
    )
    swarm = SwarmState(
        title="Test",
        user_prompt="Test",
        contracts=[contract],
        tasks=[task],
    )

    errors = orchestrator._validate_dag_proposal_state(swarm)

    assert any(error["error"] == "unknown_dependency" for error in errors)


def test_dag_proposal_validator_rejects_contract_with_extra_tools():
    orchestrator = SwarmOrchestrator()
    spec = get_experimental_task_spec("create_readme")
    contract = AgentContract(
        role="DocumentationAgent",
        objective="Contract with unsafe extra tool",
        allowed_tools=[*spec.allowed_tools, "SafeShell"],
        output_contract=dict(spec.output_contract),
    )
    task = TaskNode(
        title="Create implementation brief README.md",
        objective="Create README.md",
        assigned_contract_id=contract.id,
    )
    swarm = SwarmState(
        title="Test",
        user_prompt="Test",
        contracts=[contract],
        tasks=[task],
    )

    errors = orchestrator._validate_dag_proposal_state(swarm)

    assert any(error.get("code") == "allowed_tools_exceed_task_type" for error in errors)


def test_record_dag_proposal_decision_marks_accepted_or_rejected():
    orchestrator = SwarmOrchestrator()
    swarm = SwarmState(title="Test", user_prompt="Test")

    accepted = orchestrator._record_dag_proposal_decision(
        swarm=swarm,
        source="planner_model",
        proposal_kind="model_generated_dag",
        validation_errors=[],
        metadata={"template": "dynamic"},
    )
    rejected = orchestrator._record_dag_proposal_decision(
        swarm=accepted,
        source="planner_model",
        proposal_kind="model_generated_dag",
        validation_errors=[{"error": "unknown_dependency"}],
    )

    assert rejected.decisions[-2]["kind"] == "dag_proposal_validation"
    assert rejected.decisions[-2]["status"] == "accepted"
    assert rejected.decisions[-2]["metadata"]["template"] == "dynamic"
    assert rejected.decisions[-1]["status"] == "rejected"
    assert rejected.decisions[-1]["validation_errors"][0]["error"] == "unknown_dependency"


def test_materialize_dag_proposal_uses_registry_tools_and_contract():
    orchestrator = SwarmOrchestrator()
    base = SwarmState(title="Test", user_prompt="Test")

    materialized = orchestrator._materialize_dag_proposal_state(
        base_swarm=base,
        proposal={
            "tasks": [
                {
                    "id": "create-readme",
                    "task_type": "create_readme",
                    "role": "DocumentationAgent",
                    "title": "Create implementation brief README.md",
                    "objective": "Create README.md from the model generated DAG proposal.",
                    "allowed_tools": ["SafeShell"],
                    "output_contract": {"unsafe": True},
                }
            ]
        },
    )

    assert len(materialized.tasks) == 1
    assert len(materialized.contracts) == 1
    contract = materialized.contracts[0]
    spec = get_experimental_task_spec("create_readme")
    assert contract.allowed_tools == spec.allowed_tools
    assert contract.output_contract == spec.output_contract
    assert "SafeShell" not in contract.allowed_tools
    assert orchestrator._validate_dag_proposal_state(materialized) == []


def test_materialize_dag_proposal_preserves_declared_dependencies():
    orchestrator = SwarmOrchestrator()
    base = SwarmState(title="Test", user_prompt="Test")

    materialized = orchestrator._materialize_dag_proposal_state(
        base_swarm=base,
        proposal={
            "tasks": [
                {
                    "id": "architecture",
                    "task_type": "architecture_plan_execute",
                    "role": "ArchitectAgent",
                    "title": "Execute architecture plan",
                    "objective": "Plan architecture.",
                },
                {
                    "id": "frontend",
                    "task_type": "frontend_plan_execute",
                    "role": "FrontendAgent",
                    "title": "Execute frontend plan",
                    "objective": "Plan frontend.",
                    "depends_on": ["architecture"],
                },
            ]
        },
    )

    tasks_by_id = {task.id: task for task in materialized.tasks}
    assert tasks_by_id["frontend"].depends_on == ["architecture"]
    assert orchestrator._validate_dag_proposal_state(materialized) == []


def test_template_dag_proposal_static_app_materializes_and_validates():
    orchestrator = SwarmOrchestrator()
    base = SwarmState(title="Test", user_prompt="Test")
    proposal = orchestrator._build_template_dag_proposal(
        template="static_app",
        generated_plan={
            "app_type": "static tutorial",
            "frontend": "HTML/CSS",
            "backend": "no backend",
            "database": "no database",
        },
    )

    materialized = orchestrator._materialize_dag_proposal_state(base_swarm=base, proposal=proposal)

    assert proposal["template"] == "static_app"
    assert [task.id for task in materialized.tasks] == [
        "architecture",
        "frontend_plan",
        "backend_plan",
        "security_review",
        "create_static_app",
        "review_static_app",
        "validation",
        "consolidate",
    ]
    assert orchestrator._validate_dag_proposal_state(materialized) == []


def test_template_dag_proposal_implementation_brief_materializes_and_validates():
    orchestrator = SwarmOrchestrator()
    base = SwarmState(title="Test", user_prompt="Test")
    proposal = orchestrator._build_template_dag_proposal(
        template="implementation_brief",
        generated_plan={
            "app_type": "web app",
            "frontend": "React",
            "backend": "FastAPI",
            "database": "PostgreSQL",
        },
    )

    materialized = orchestrator._materialize_dag_proposal_state(base_swarm=base, proposal=proposal)

    assert proposal["template"] == "implementation_brief"
    assert [task.id for task in materialized.tasks] == [
        "architecture",
        "frontend_plan",
        "backend_plan",
        "security_review",
        "create_readme",
        "review_readme",
        "validation",
        "consolidate",
    ]
    assert orchestrator._validate_dag_proposal_state(materialized) == []


def test_validated_template_dag_pipeline_records_accepted_decision():
    orchestrator = SwarmOrchestrator()
    base = SwarmState(title="Test", user_prompt="Test")

    materialized, errors = orchestrator._build_validated_template_dag_state(
        base_swarm=base,
        template="implementation_brief",
        generated_plan={
            "app_type": "web app",
            "frontend": "React",
            "backend": "FastAPI",
            "database": "PostgreSQL",
        },
    )

    assert errors == []
    assert materialized.decisions[-1]["kind"] == "dag_proposal_validation"
    assert materialized.decisions[-1]["status"] == "accepted"
    assert materialized.decisions[-1]["metadata"]["template"] == "implementation_brief"
    assert [task.id for task in materialized.tasks][-2:] == ["validation", "consolidate"]


def test_ensure_template_proposal_dag_persists_validated_template_tasks(tmp_path):
    orchestrator = SwarmOrchestrator()
    orchestrator.store.root = tmp_path

    swarm = orchestrator.create_swarm(
        user_prompt="crear app con backend",
        dashboard_id="dashboard-test",
        intent="chat",
    )

    updated, errors = orchestrator.ensure_template_proposal_dag(
        swarm_id=swarm.id,
        template="implementation_brief",
        generated_plan={
            "app_type": "web app",
            "frontend": "React",
            "backend": "FastAPI",
            "database": "PostgreSQL",
        },
    )

    assert errors == []
    assert updated.intent == "task"
    assert updated.coordinator_contract_id
    assert [task.id for task in updated.tasks] == [
        "architecture",
        "frontend_plan",
        "backend_plan",
        "security_review",
        "create_readme",
        "review_readme",
        "validation",
        "consolidate",
    ]
    assert updated.decisions[-1]["kind"] == "dag_proposal_validation"
    assert updated.decisions[-1]["status"] == "accepted"
    assert updated.messages[-1].payload["message"] == "implementation_dag_created"
    assert updated.messages[-1].payload["source"] == "template_proposal_pipeline"


def test_ensure_template_proposal_dag_is_idempotent_when_tasks_exist(tmp_path):
    orchestrator = SwarmOrchestrator()
    orchestrator.store.root = tmp_path

    swarm = orchestrator.create_swarm(
        user_prompt="crear app estática",
        dashboard_id="dashboard-test",
        intent="chat",
    )

    first, first_errors = orchestrator.ensure_template_proposal_dag(
        swarm_id=swarm.id,
        template="static_app",
        generated_plan={
            "app_type": "static tutorial",
            "frontend": "HTML/CSS",
            "backend": "no backend",
            "database": "no database",
        },
    )
    second, second_errors = orchestrator.ensure_template_proposal_dag(
        swarm_id=swarm.id,
        template="static_app",
        generated_plan={
            "app_type": "static tutorial",
            "frontend": "HTML/CSS",
            "backend": "no backend",
            "database": "no database",
        },
    )

    assert first_errors == []
    assert second_errors == []
    assert [task.id for task in second.tasks] == [task.id for task in first.tasks]
    assert len(second.tasks) == len(first.tasks)


def test_parse_model_dag_proposal_accepts_direct_json():
    proposal, error = SwarmOrchestrator._parse_model_dag_proposal(
        '{"kind":"model_generated_dag","tasks":[{"id":"architecture","task_type":"architecture_plan_execute","role":"ArchitectAgent"}]}'
    )

    assert error is None
    assert proposal["kind"] == "model_generated_dag"
    assert proposal["tasks"][0]["task_type"] == "architecture_plan_execute"


def test_parse_model_dag_proposal_accepts_embedded_json():
    proposal, error = SwarmOrchestrator._parse_model_dag_proposal(
        'Texto antes {"kind":"model_generated_dag","tasks":[{"id":"architecture","task_type":"architecture_plan_execute","role":"ArchitectAgent"}]} texto después'
    )

    assert error is None
    assert proposal["kind"] == "model_generated_dag"


def test_parse_model_dag_proposal_rejects_invalid_json():
    proposal, error = SwarmOrchestrator._parse_model_dag_proposal("no hay json válido")

    assert proposal is None
    assert error["error"] == "model_dag_proposal_response_not_json"


def test_parse_model_dag_proposal_rejects_missing_tasks():
    proposal, error = SwarmOrchestrator._parse_model_dag_proposal('{"kind":"model_generated_dag","tasks":[]}')

    assert proposal is None
    assert error["error"] == "model_dag_proposal_missing_tasks"


def test_parse_model_dag_proposal_accepts_wrapped_dag_proposal():
    proposal, error = SwarmOrchestrator._parse_model_dag_proposal(
        '{"dag_proposal":{"kind":"model_generated_dag","tasks":[{"id":"architecture","task_type":"architecture_plan_execute","role":"ArchitectAgent"}]}}'
    )

    assert error is None
    assert proposal["kind"] == "model_generated_dag"


def test_validated_model_dag_proposal_accepts_valid_model_output_without_mutating_base():
    orchestrator = SwarmOrchestrator()
    base = SwarmState(title="Test", user_prompt="Test")
    output = {
        "content": """
        {
          "kind": "model_generated_dag",
          "tasks": [
            {
              "id": "architecture",
              "task_type": "architecture_plan_execute",
              "role": "ArchitectAgent",
              "title": "Execute architecture plan",
              "objective": "Plan architecture."
            },
            {
              "id": "create_readme",
              "task_type": "create_readme",
              "role": "DocumentationAgent",
              "title": "Create implementation brief README.md",
              "objective": "Create README.md.",
              "depends_on": ["architecture"]
            }
          ]
        }
        """
    }

    materialized, errors = orchestrator._build_validated_model_dag_proposal_state(
        base_swarm=base,
        final_message=output,
    )

    assert errors == []
    assert base.tasks == []
    assert base.contracts == []
    assert [task.id for task in materialized.tasks] == ["architecture", "create_readme"]
    assert materialized.decisions[-1]["source"] == "model_dag_proposal"
    assert materialized.decisions[-1]["status"] == "accepted"
    assert materialized.decisions[-1]["metadata"]["parse_status"] == "accepted"


def test_validated_model_dag_proposal_rejects_parse_error_without_tasks():
    orchestrator = SwarmOrchestrator()
    base = SwarmState(title="Test", user_prompt="Test")

    materialized, errors = orchestrator._build_validated_model_dag_proposal_state(
        base_swarm=base,
        final_message="no hay json",
    )

    assert errors[0]["error"] == "model_dag_proposal_response_not_json"
    assert materialized.tasks == []
    assert materialized.contracts == []
    assert materialized.decisions[-1]["source"] == "model_dag_proposal"
    assert materialized.decisions[-1]["status"] == "rejected"
    assert materialized.decisions[-1]["metadata"]["parse_status"] == "failed"


def test_validated_model_dag_proposal_rejects_unknown_dependency():
    orchestrator = SwarmOrchestrator()
    base = SwarmState(title="Test", user_prompt="Test")
    output = {
        "content": """
        {
          "kind": "model_generated_dag",
          "tasks": [
            {
              "id": "create_readme",
              "task_type": "create_readme",
              "role": "DocumentationAgent",
              "title": "Create implementation brief README.md",
              "objective": "Create README.md.",
              "depends_on": ["missing"]
            }
          ]
        }
        """
    }

    materialized, errors = orchestrator._build_validated_model_dag_proposal_state(
        base_swarm=base,
        final_message=output,
    )

    assert any(error["error"] == "unknown_dependency" for error in errors)
    assert materialized.decisions[-1]["status"] == "rejected"


def test_record_model_dag_proposal_preview_persists_only_decisions(tmp_path):
    orchestrator = SwarmOrchestrator()
    orchestrator.store.root = tmp_path

    swarm = orchestrator.create_swarm(
        user_prompt="crear app desde propuesta modelo",
        dashboard_id="dashboard-test",
        intent="chat",
    )

    saved, errors = orchestrator.record_model_dag_proposal_preview(
        swarm_id=swarm.id,
        final_message={
            "content": """
            {
              "kind": "model_generated_dag",
              "tasks": [
                {
                  "id": "architecture",
                  "task_type": "architecture_plan_execute",
                  "role": "ArchitectAgent",
                  "title": "Execute architecture plan",
                  "objective": "Plan architecture."
                },
                {
                  "id": "create_readme",
                  "task_type": "create_readme",
                  "role": "DocumentationAgent",
                  "title": "Create implementation brief README.md",
                  "objective": "Create README.md.",
                  "depends_on": ["architecture"]
                }
              ]
            }
            """
        },
    )

    assert errors == []
    assert saved.tasks == []
    _assert_only_base_coordinator_contracts(saved.contracts)
    assert saved.decisions[-1]["kind"] == "dag_proposal_validation"
    assert saved.decisions[-1]["source"] == "model_dag_proposal"
    assert saved.decisions[-1]["status"] == "accepted"


def test_record_model_dag_proposal_preview_persists_rejection_without_tasks(tmp_path):
    orchestrator = SwarmOrchestrator()
    orchestrator.store.root = tmp_path

    swarm = orchestrator.create_swarm(
        user_prompt="crear app desde propuesta inválida",
        dashboard_id="dashboard-test",
        intent="chat",
    )

    saved, errors = orchestrator.record_model_dag_proposal_preview(
        swarm_id=swarm.id,
        final_message="no hay json",
    )

    assert errors[0]["error"] == "model_dag_proposal_response_not_json"
    assert saved.tasks == []
    _assert_only_base_coordinator_contracts(saved.contracts)
    assert saved.decisions[-1]["status"] == "rejected"
    assert saved.decisions[-1]["metadata"]["parse_status"] == "failed"


def test_build_model_dag_proposal_prompt_contains_guardrails_and_plan_context():
    orchestrator = SwarmOrchestrator()
    prompt = orchestrator._build_model_dag_proposal_prompt(
        generated_plan={
            "summary": "Plan de prueba",
            "app_type": "web app",
            "main_goal": "crear dashboard",
            "frontend": "React",
            "backend": "FastAPI",
            "database": "PostgreSQL",
            "mvp_priority": "login y dashboard",
            "out_of_scope": "pagos",
            "visual_style": "clean UI",
        }
    )

    assert "Return JSON only" in prompt
    assert "model_generated_dag" in prompt
    assert "architecture_plan_execute" in prompt
    assert "validation_execute" in prompt
    assert "CoordinatorAgent" in prompt
    assert "allowed_tools" in prompt
    assert "output_contract" in prompt
    assert "backend derives those from TASK_TYPE_REGISTRY" in prompt
    assert "React" in prompt
    assert "FastAPI" in prompt
    assert "PostgreSQL" in prompt
    assert "pagos" in prompt


def test_build_model_dag_proposal_prompt_contains_guardrails_and_plan_context():
    orchestrator = SwarmOrchestrator()
    prompt = orchestrator._build_model_dag_proposal_prompt(
        generated_plan={
            "summary": "Plan de prueba",
            "app_type": "web app",
            "main_goal": "crear dashboard",
            "frontend": "React",
            "backend": "FastAPI",
            "database": "PostgreSQL",
            "mvp_priority": "login y dashboard",
            "out_of_scope": "pagos",
            "visual_style": "clean UI",
        }
    )

    assert "Return JSON only" in prompt
    assert "model_generated_dag" in prompt
    assert "architecture_plan_execute" in prompt
    assert "validation_execute" in prompt
    assert "CoordinatorAgent" in prompt
    assert "allowed_tools" in prompt
    assert "output_contract" in prompt
    assert "backend derives those from TASK_TYPE_REGISTRY" in prompt
    assert "React" in prompt
    assert "FastAPI" in prompt
    assert "PostgreSQL" in prompt
    assert "pagos" in prompt


def test_model_dag_prompt_to_preview_decision_flow_without_persisting_tasks(tmp_path):
    orchestrator = SwarmOrchestrator()
    orchestrator.store.root = tmp_path

    swarm = orchestrator.create_swarm(
        user_prompt="crear app con backend",
        dashboard_id="dashboard-test",
        intent="chat",
    )

    prompt = orchestrator._build_model_dag_proposal_prompt(
        generated_plan={
            "app_type": "web app",
            "main_goal": "crear dashboard",
            "frontend": "React",
            "backend": "FastAPI",
            "database": "PostgreSQL",
        }
    )
    assert "model_generated_dag" in prompt
    assert "Return JSON only" in prompt

    saved, errors = orchestrator.record_model_dag_proposal_preview(
        swarm_id=swarm.id,
        final_message={
            "content": """
            {
              "kind": "model_generated_dag",
              "tasks": [
                {
                  "id": "architecture",
                  "task_type": "architecture_plan_execute",
                  "role": "ArchitectAgent",
                  "title": "Execute architecture plan",
                  "objective": "Plan architecture."
                },
                {
                  "id": "frontend_plan",
                  "task_type": "frontend_plan_execute",
                  "role": "FrontendAgent",
                  "title": "Execute frontend plan",
                  "objective": "Plan frontend.",
                  "depends_on": ["architecture"]
                },
                {
                  "id": "create_readme",
                  "task_type": "create_readme",
                  "role": "DocumentationAgent",
                  "title": "Create implementation brief README.md",
                  "objective": "Create README.",
                  "depends_on": ["frontend_plan"]
                }
              ]
            }
            """
        },
    )

    assert errors == []
    assert saved.tasks == []
    _assert_only_base_coordinator_contracts(saved.contracts)
    assert saved.decisions[-1]["kind"] == "dag_proposal_validation"
    assert saved.decisions[-1]["source"] == "model_dag_proposal"
    assert saved.decisions[-1]["status"] == "accepted"
    assert saved.decisions[-1]["metadata"]["task_ids"] == ["architecture", "frontend_plan", "create_readme"]


def test_model_dag_prompt_to_preview_decision_flow_without_persisting_tasks(tmp_path):
    orchestrator = SwarmOrchestrator()
    orchestrator.store.root = tmp_path

    swarm = orchestrator.create_swarm(
        user_prompt="crear app con backend",
        dashboard_id="dashboard-test",
        intent="chat",
    )

    prompt = orchestrator._build_model_dag_proposal_prompt(
        generated_plan={
            "app_type": "web app",
            "main_goal": "crear dashboard",
            "frontend": "React",
            "backend": "FastAPI",
            "database": "PostgreSQL",
        }
    )
    assert "model_generated_dag" in prompt
    assert "Return JSON only" in prompt

    saved, errors = orchestrator.record_model_dag_proposal_preview(
        swarm_id=swarm.id,
        final_message={
            "content": """
            {
              "kind": "model_generated_dag",
              "tasks": [
                {
                  "id": "architecture",
                  "task_type": "architecture_plan_execute",
                  "role": "ArchitectAgent",
                  "title": "Execute architecture plan",
                  "objective": "Plan architecture."
                },
                {
                  "id": "frontend_plan",
                  "task_type": "frontend_plan_execute",
                  "role": "FrontendAgent",
                  "title": "Execute frontend plan",
                  "objective": "Plan frontend.",
                  "depends_on": ["architecture"]
                },
                {
                  "id": "create_readme",
                  "task_type": "create_readme",
                  "role": "DocumentationAgent",
                  "title": "Create implementation brief README.md",
                  "objective": "Create README.",
                  "depends_on": ["frontend_plan"]
                }
              ]
            }
            """
        },
    )

    assert errors == []
    assert saved.tasks == []
    _assert_only_base_coordinator_contracts(saved.contracts)
    assert saved.decisions[-1]["kind"] == "dag_proposal_validation"
    assert saved.decisions[-1]["source"] == "model_dag_proposal"
    assert saved.decisions[-1]["status"] == "accepted"
    assert saved.decisions[-1]["metadata"]["task_ids"] == ["architecture", "frontend_plan", "create_readme"]


def test_materialize_dag_proposal_uses_registry_title_instead_of_model_title():
    orchestrator = SwarmOrchestrator()
    base = SwarmState(title="Test", user_prompt="Test")

    materialized = orchestrator._materialize_dag_proposal_state(
        base_swarm=base,
        proposal={
            "kind": "model_generated_dag",
            "tasks": [
                {
                    "id": "architecture",
                    "task_type": "architecture_plan_execute",
                    "role": "ArchitectAgent",
                    "title": "Architecture Design",
                    "objective": "Plan architecture from model proposal.",
                },
                {
                    "id": "frontend_plan",
                    "task_type": "frontend_plan_execute",
                    "role": "FrontendAgent",
                    "title": "Frontend Development Plan",
                    "objective": "Plan frontend from model proposal.",
                    "depends_on": ["architecture"],
                },
            ],
        },
    )

    assert [task.title for task in materialized.tasks] == [
        get_experimental_task_spec("architecture_plan_execute").title,
        get_experimental_task_spec("frontend_plan_execute").title,
    ]
    assert orchestrator._validate_dag_proposal_state(materialized) == []


def test_model_dag_semantic_policy_rejects_static_app_for_backend_database_plan():
    orchestrator = SwarmOrchestrator()
    base = SwarmState(title="Test", user_prompt="Test")
    output = {
        "content": """
        {
          "kind": "model_generated_dag",
          "tasks": [
            {
              "id": "architecture",
              "task_type": "architecture_plan_execute",
              "role": "ArchitectAgent",
              "title": "Architecture",
              "objective": "Plan architecture."
            },
            {
              "id": "create_static",
              "task_type": "create_static_app",
              "role": "FrontendAgent",
              "title": "Create Static App",
              "objective": "Create static app.",
              "depends_on": ["architecture"]
            }
          ]
        }
        """
    }

    materialized, errors = orchestrator._build_validated_model_dag_proposal_state(
        base_swarm=base,
        final_message=output,
        generated_plan={
            "backend": "FastAPI",
            "database": "PostgreSQL",
        },
    )

    assert any(error["error"] == "semantically_incompatible_task_type" for error in errors)
    assert materialized.decisions[-1]["status"] == "rejected"


def test_model_dag_semantic_policy_allows_static_app_for_static_plan():
    orchestrator = SwarmOrchestrator()
    base = SwarmState(title="Test", user_prompt="Test")
    output = {
        "content": """
        {
          "kind": "model_generated_dag",
          "tasks": [
            {
              "id": "architecture",
              "task_type": "architecture_plan_execute",
              "role": "ArchitectAgent",
              "title": "Architecture",
              "objective": "Plan architecture."
            },
            {
              "id": "create_static",
              "task_type": "create_static_app",
              "role": "FrontendAgent",
              "title": "Create Static App",
              "objective": "Create static app.",
              "depends_on": ["architecture"]
            }
          ]
        }
        """
    }

    materialized, errors = orchestrator._build_validated_model_dag_proposal_state(
        base_swarm=base,
        final_message=output,
        generated_plan={
            "backend": "no backend",
            "database": "no database",
        },
    )

    assert errors == []
    assert materialized.decisions[-1]["status"] == "accepted"


def test_model_dag_prompt_excludes_static_app_for_backend_database_plan():
    orchestrator = SwarmOrchestrator()
    prompt = orchestrator._build_model_dag_proposal_prompt(
        generated_plan={
            "frontend": "React",
            "backend": "FastAPI",
            "database": "PostgreSQL",
        }
    )

    allowed_segment = prompt.split("Use only these task_type values:", 1)[1].split("Use only these role values:", 1)[0]
    allowed_values = {item.strip(" .") for item in allowed_segment.split(",")}
    assert "create_static_app" not in allowed_values
    assert "review_static_app" not in allowed_values
    assert "do not use create_static_app or review_static_app" in prompt


def test_model_dag_prompt_allows_static_app_for_static_plan():
    orchestrator = SwarmOrchestrator()
    prompt = orchestrator._build_model_dag_proposal_prompt(
        generated_plan={
            "frontend": "HTML/CSS",
            "backend": "no backend",
            "database": "no database",
        }
    )

    allowed_segment = prompt.split("Use only these task_type values:", 1)[1].split("Use only these role values:", 1)[0]
    assert "create_static_app" in allowed_segment
    assert "review_static_app" in allowed_segment


def test_model_dag_prompt_separates_planning_from_implementation_language():
    orchestrator = SwarmOrchestrator()
    prompt = orchestrator._build_model_dag_proposal_prompt(
        generated_plan={
            "frontend": "React",
            "backend": "FastAPI",
            "database": "PostgreSQL",
        }
    )

    assert "Planning task types" in prompt
    assert "must describe planning, design, scope, constraints, handoff, and risks only" in prompt
    assert "Do not use implementation language" in prompt
    assert "do not pretend the app is implemented" in prompt
    assert "use backend_plan_execute only to plan schema/data model/API integration" in prompt
    assert "validation_execute must validate available artifacts or plans only" in prompt


def test_model_dag_prompt_separates_planning_from_implementation_language():
    orchestrator = SwarmOrchestrator()
    prompt = orchestrator._build_model_dag_proposal_prompt(
        generated_plan={
            "frontend": "React",
            "backend": "FastAPI",
            "database": "PostgreSQL",
        }
    )

    assert "Planning task types" in prompt
    assert "must describe planning, design, scope, constraints, handoff, and risks only" in prompt
    assert "Do not use implementation language" in prompt
    assert "do not pretend the app is implemented" in prompt
    assert "use backend_plan_execute only to plan schema/data model/API integration" in prompt
    assert "validation_execute must validate available artifacts or plans only" in prompt


def test_model_dag_semantic_policy_rejects_incompatible_role_for_task_type():
    orchestrator = SwarmOrchestrator()
    base = SwarmState(title="Test", user_prompt="Test")
    output = {
        "content": """
        {
          "kind": "model_generated_dag",
          "tasks": [
            {
              "id": "validation",
              "task_type": "validation_execute",
              "role": "ReviewerAgent",
              "title": "Validation",
              "objective": "Validate plans."
            }
          ]
        }
        """
    }

    materialized, errors = orchestrator._build_validated_model_dag_proposal_state(
        base_swarm=base,
        final_message=output,
        generated_plan={
            "backend": "FastAPI",
            "database": "PostgreSQL",
        },
    )

    assert any(error["error"] == "semantically_incompatible_role" for error in errors)
    assert materialized.decisions[-1]["status"] == "rejected"


def test_model_dag_prompt_includes_exact_role_mappings():
    orchestrator = SwarmOrchestrator()
    prompt = orchestrator._build_model_dag_proposal_prompt(
        generated_plan={
            "backend": "FastAPI",
            "database": "PostgreSQL",
        }
    )

    assert "validation_execute=TesterAgent" in prompt
    assert "consolidate_final=CoordinatorAgent" in prompt
    assert "create_readme=DocumentationAgent" in prompt


def test_model_dag_semantic_policy_rejects_incompatible_role_for_task_type():
    orchestrator = SwarmOrchestrator()
    base = SwarmState(title="Test", user_prompt="Test")
    output = {
        "content": """
        {
          "kind": "model_generated_dag",
          "tasks": [
            {
              "id": "validation",
              "task_type": "validation_execute",
              "role": "ReviewerAgent",
              "title": "Validation",
              "objective": "Validate plans."
            }
          ]
        }
        """
    }

    materialized, errors = orchestrator._build_validated_model_dag_proposal_state(
        base_swarm=base,
        final_message=output,
        generated_plan={
            "backend": "FastAPI",
            "database": "PostgreSQL",
        },
    )

    assert any(error["error"] == "semantically_incompatible_role" for error in errors)
    assert materialized.decisions[-1]["status"] == "rejected"


def test_model_dag_prompt_includes_exact_role_mappings():
    orchestrator = SwarmOrchestrator()
    prompt = orchestrator._build_model_dag_proposal_prompt(
        generated_plan={
            "backend": "FastAPI",
            "database": "PostgreSQL",
        }
    )

    assert "validation_execute=TesterAgent" in prompt
    assert "consolidate_final=CoordinatorAgent" in prompt
    assert "create_readme=DocumentationAgent" in prompt


def test_model_dag_preview_decision_stores_recoverable_metadata(tmp_path):
    orchestrator = SwarmOrchestrator()
    orchestrator.store.root = tmp_path

    swarm = orchestrator.create_swarm(
        user_prompt="crear app con backend",
        dashboard_id="dashboard-test",
        intent="chat",
    )

    saved, errors = orchestrator.record_model_dag_proposal_preview(
        swarm_id=swarm.id,
        generated_plan={
            "summary": "Dashboard simple",
            "frontend": "React",
            "backend": "FastAPI",
            "database": "PostgreSQL",
        },
        final_message={
            "content": """
            {
              "kind": "model_generated_dag",
              "tasks": [
                {
                  "id": "architecture",
                  "task_type": "architecture_plan_execute",
                  "role": "ArchitectAgent",
                  "title": "Architecture",
                  "objective": "Plan architecture."
                },
                {
                  "id": "create_readme",
                  "task_type": "create_readme",
                  "role": "DocumentationAgent",
                  "title": "Create README",
                  "objective": "Create README.",
                  "depends_on": ["architecture"]
                }
              ]
            }
            """
        },
    )

    assert errors == []
    decision = saved.decisions[-1]
    metadata = decision["metadata"]

    assert decision["status"] == "accepted"
    assert metadata["preview_id"]
    assert metadata["proposal"]["kind"] == "model_generated_dag"
    assert metadata["normalized_plan"]["backend"] == "FastAPI"
    assert metadata["normalized_plan"]["database"] == "PostgreSQL"
    assert metadata["plan_fingerprint"]
    assert metadata["task_ids"] == ["architecture", "create_readme"]


def test_model_dag_preview_rejected_parse_error_stores_plan_fingerprint(tmp_path):
    orchestrator = SwarmOrchestrator()
    orchestrator.store.root = tmp_path

    swarm = orchestrator.create_swarm(
        user_prompt="crear app inválida",
        dashboard_id="dashboard-test",
        intent="chat",
    )

    saved, errors = orchestrator.record_model_dag_proposal_preview(
        swarm_id=swarm.id,
        generated_plan={
            "frontend": "React",
            "backend": "FastAPI",
            "database": "PostgreSQL",
        },
        final_message="no hay json",
    )

    assert errors[0]["error"] == "model_dag_proposal_response_not_json"
    decision = saved.decisions[-1]
    metadata = decision["metadata"]

    assert decision["status"] == "rejected"
    assert metadata["preview_id"]
    assert metadata["parse_status"] == "failed"
    assert metadata["normalized_plan"]["backend"] == "FastAPI"
    assert metadata["plan_fingerprint"]


def _record_valid_model_preview_for_materialization(orchestrator, swarm_id):
    saved, errors = orchestrator.record_model_dag_proposal_preview(
        swarm_id=swarm_id,
        generated_plan={
            "summary": "Dashboard simple",
            "frontend": "React",
            "backend": "FastAPI",
            "database": "PostgreSQL",
        },
        final_message={
            "content": """
            {
              "kind": "model_generated_dag",
              "tasks": [
                {
                  "id": "architecture",
                  "task_type": "architecture_plan_execute",
                  "role": "ArchitectAgent",
                  "title": "Architecture",
                  "objective": "Plan architecture."
                },
                {
                  "id": "create_readme",
                  "task_type": "create_readme",
                  "role": "DocumentationAgent",
                  "title": "Create README",
                  "objective": "Create README.",
                  "depends_on": ["architecture"]
                },
                {
                  "id": "consolidate",
                  "task_type": "consolidate_final",
                  "role": "CoordinatorAgent",
                  "title": "Consolidate",
                  "objective": "Consolidate final proposal.",
                  "depends_on": ["create_readme"]
                }
              ]
            }
            """
        },
    )
    assert errors == []
    return saved, saved.decisions[-1]["metadata"]["preview_id"]


def test_materialize_model_dag_proposal_preview_requires_approval(tmp_path):
    orchestrator = SwarmOrchestrator()
    orchestrator.store.root = tmp_path
    swarm = orchestrator.create_swarm(user_prompt="test", dashboard_id="dash", intent="chat")
    saved, preview_id = _record_valid_model_preview_for_materialization(orchestrator, swarm.id)

    result, errors = orchestrator.materialize_model_dag_proposal_preview(
        swarm_id=swarm.id,
        preview_id=preview_id,
        approve=False,
    )

    assert errors[0]["error"] == "approval_required"
    assert result.tasks == []
    assert result.decisions[-1]["kind"] == "dag_proposal_materialization"
    assert result.decisions[-1]["status"] == "rejected"


def test_materialize_model_dag_proposal_preview_persists_tasks_with_approval(tmp_path):
    orchestrator = SwarmOrchestrator()
    orchestrator.store.root = tmp_path
    swarm = orchestrator.create_swarm(user_prompt="test", dashboard_id="dash", intent="chat")
    saved, preview_id = _record_valid_model_preview_for_materialization(orchestrator, swarm.id)

    result, errors = orchestrator.materialize_model_dag_proposal_preview(
        swarm_id=swarm.id,
        preview_id=preview_id,
        generated_plan={
            "summary": "Dashboard simple",
            "frontend": "React",
            "backend": "FastAPI",
            "database": "PostgreSQL",
        },
        approve=True,
    )

    assert errors == []
    assert result.intent == "task"
    assert result.tasks
    assert result.contracts
    assert result.coordinator_contract_id
    assert result.decisions[-1]["kind"] == "dag_proposal_materialization"
    assert result.decisions[-1]["status"] == "accepted"
    assert result.messages[-1].payload["message"] == "model_dag_proposal_materialized"


def test_materialize_model_dag_proposal_preview_rejects_missing_preview(tmp_path):
    orchestrator = SwarmOrchestrator()
    orchestrator.store.root = tmp_path
    swarm = orchestrator.create_swarm(user_prompt="test", dashboard_id="dash", intent="chat")

    result, errors = orchestrator.materialize_model_dag_proposal_preview(
        swarm_id=swarm.id,
        preview_id="missing",
        approve=True,
    )

    assert errors[0]["error"] == "preview_not_found"
    assert result.tasks == []


def test_materialize_model_dag_proposal_preview_rejects_stale_plan(tmp_path):
    orchestrator = SwarmOrchestrator()
    orchestrator.store.root = tmp_path
    swarm = orchestrator.create_swarm(user_prompt="test", dashboard_id="dash", intent="chat")
    saved, preview_id = _record_valid_model_preview_for_materialization(orchestrator, swarm.id)

    result, errors = orchestrator.materialize_model_dag_proposal_preview(
        swarm_id=swarm.id,
        preview_id=preview_id,
        generated_plan={
            "summary": "Changed plan",
            "frontend": "Vue",
            "backend": "Django",
            "database": "SQLite",
        },
        approve=True,
    )

    assert errors[0]["error"] == "preview_plan_fingerprint_mismatch"
    assert result.tasks == []


def test_materialize_model_dag_proposal_preview_rejects_existing_tasks(tmp_path):
    orchestrator = SwarmOrchestrator()
    orchestrator.store.root = tmp_path
    swarm = orchestrator.create_swarm(user_prompt="test", dashboard_id="dash", intent="chat")
    saved, preview_id = _record_valid_model_preview_for_materialization(orchestrator, swarm.id)

    first, errors = orchestrator.materialize_model_dag_proposal_preview(
        swarm_id=swarm.id,
        preview_id=preview_id,
        generated_plan={
            "summary": "Dashboard simple",
            "frontend": "React",
            "backend": "FastAPI",
            "database": "PostgreSQL",
        },
        approve=True,
    )
    assert errors == []

    second, errors = orchestrator.materialize_model_dag_proposal_preview(
        swarm_id=swarm.id,
        preview_id=preview_id,
        generated_plan={
            "summary": "Dashboard simple",
            "frontend": "React",
            "backend": "FastAPI",
            "database": "PostgreSQL",
        },
        approve=True,
    )

    assert errors[0]["error"] == "swarm_already_has_tasks"
    assert len(second.tasks) == len(first.tasks)


def test_materialized_dag_proposal_persists_task_type_on_task_nodes():
    orchestrator = SwarmOrchestrator()
    base = SwarmState(title="Test", user_prompt="Test")

    materialized = orchestrator._materialize_dag_proposal_state(
        base_swarm=base,
        proposal={
            "kind": "model_generated_dag",
            "tasks": [
                {
                    "id": "architecture",
                    "task_type": "architecture_plan_execute",
                    "role": "ArchitectAgent",
                    "title": "Unexpected custom title",
                    "objective": "Plan architecture.",
                }
            ],
        },
    )

    assert materialized.tasks[0].task_type == "architecture_plan_execute"


def test_classify_experimental_task_prefers_explicit_task_type():
    task = TaskNode(
        title="Completely custom title",
        objective="No matcher text here.",
        task_type="validation_execute",
    )

    assert classify_experimental_task(task) == "validation_execute"


def test_classify_experimental_task_rejects_unknown_explicit_task_type():
    task = TaskNode(
        title="Create README.md",
        objective="Create README.md",
        task_type="not_registered",
    )

    try:
        classify_experimental_task(task)
    except ValueError as exc:
        assert "not_registered" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unknown explicit task_type")


def test_model_dag_proposal_prompt_uses_ri_prompt_architecture():
    orchestrator = SwarmOrchestrator()
    prompt = orchestrator._build_model_dag_proposal_prompt(
        generated_plan={
            "summary": "Landing estática",
            "app_type": "static_site",
            "main_goal": "Mostrar servicios",
            "frontend": "HTML/CSS",
            "backend": "none",
            "database": "none",
            "mvp_priority": "visual",
            "out_of_scope": "login",
            "visual_style": "simple",
        }
    )

    assert "openswarm_system_prompt" in prompt
    assert "mode_prompt" in prompt
    assert "state_grounding_rules" in prompt
    assert "model_response_contract_prompt" in prompt
    assert "el modelo razona, pero no inventa estado" in prompt.lower()
    assert "model_generated_dag" in prompt
    assert "Do not execute tools" in prompt
