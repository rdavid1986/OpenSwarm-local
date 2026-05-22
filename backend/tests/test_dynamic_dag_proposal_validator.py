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
