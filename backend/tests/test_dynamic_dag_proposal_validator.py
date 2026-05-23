from backend.apps.agents.orchestration.models import AgentContract, SwarmState, TaskNode
from backend.apps.agents.orchestration.orchestrator import SwarmOrchestrator
from backend.apps.agents.runtime.experimental_task_type_registry import get_experimental_task_spec


def _contract_for(task_type: str, *, role: str) -> AgentContract:
    spec = get_experimental_task_spec(task_type)
    return AgentContract(
        role=role,
        objective=f"Contract for {task_type}",
        allowed_tools=list(spec.allowed_tools),
        output_contract=dict(spec.output_contract),
    )


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
    assert saved.contracts == []
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
    assert saved.contracts == []
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
    assert saved.contracts == []
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
    assert saved.contracts == []
    assert saved.decisions[-1]["kind"] == "dag_proposal_validation"
    assert saved.decisions[-1]["source"] == "model_dag_proposal"
    assert saved.decisions[-1]["status"] == "accepted"
    assert saved.decisions[-1]["metadata"]["task_ids"] == ["architecture", "frontend_plan", "create_readme"]
