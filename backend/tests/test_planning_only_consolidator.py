from pathlib import Path

from backend.apps.agents.orchestration.models import AgentContract, SwarmState, TaskNode
from backend.apps.agents.orchestration.store import SwarmStore
from backend.apps.agents.runtime.experimental_dag_consolidator import ExperimentalDAGConsolidator
from backend.apps.agents.runtime.experimental_task_type_registry import get_experimental_task_spec


def _contract(task_type: str, role: str) -> AgentContract:
    spec = get_experimental_task_spec(task_type)
    return AgentContract(
        role=role,
        objective=f"{role} objective",
        allowed_tools=list(spec.allowed_tools),
        output_contract=dict(spec.output_contract),
    )


def _task(task_type: str, title: str, contract: AgentContract, depends_on=None) -> TaskNode:
    return TaskNode(
        id=task_type,
        title=title,
        objective=title,
        task_type=task_type,
        assigned_contract_id=contract.id,
        depends_on=depends_on or [],
        status="completed",
    )


def _planning_swarm(tmp_path: Path) -> tuple[SwarmStore, SwarmState]:
    store = SwarmStore(root=tmp_path / "swarms")

    architect = _contract("architecture_plan_execute", "ArchitectAgent")
    frontend_agent = _contract("frontend_plan_execute", "FrontendAgent")
    backend_agent = _contract("backend_plan_execute", "BackendAgent")
    security_agent = _contract("security_review_execute", "SecurityAgent")
    tester = _contract("validation_execute", "TesterAgent")
    coordinator = _contract("consolidate_final", "CoordinatorAgent")

    architecture = _task("architecture_plan_execute", "Execute architecture plan", architect)
    architecture.evidence.append({
        "kind": "architecture_plan_result",
        "status": "ready",
        "architecture_plan": {"status": "ready", "summary": "Architecture ready"},
    })

    frontend = _task("frontend_plan_execute", "Execute frontend plan", frontend_agent, ["architecture_plan_execute"])
    frontend.evidence.append({
        "kind": "frontend_plan_result",
        "status": "ready",
        "frontend_plan": {"status": "ready", "summary": "Frontend ready"},
    })

    backend = _task("backend_plan_execute", "Execute backend plan", backend_agent, ["frontend_plan_execute"])
    backend.evidence.append({
        "kind": "backend_plan_result",
        "status": "ready",
        "backend_plan": {"status": "ready", "summary": "Backend ready"},
    })

    security = _task("security_review_execute", "Execute security review", security_agent, ["backend_plan_execute"])
    security.evidence.append({
        "kind": "security_review_result",
        "status": "ready",
        "security_review": {"status": "ready", "summary": "Security ready"},
    })

    validation = _task("validation_execute", "Execute safe validation checks", tester, ["security_review_execute"])
    validation.validations.append({
        "status": "passed",
        "commands": [],
        "evidence": ["plans_validated"],
    })

    consolidate = _task("consolidate_final", "Consolidate final evidence", coordinator, ["validation_execute"])

    swarm = SwarmState(
        title="Planning only",
        user_prompt="Plan app",
        intent="task",
        coordinator_contract_id=coordinator.id,
        contracts=[architect, frontend_agent, backend_agent, security_agent, tester, coordinator],
        tasks=[architecture, frontend, backend, security, validation, consolidate],
    )
    store.save(swarm)
    return store, swarm


def test_planning_only_consolidator_completes_without_implementation_claims(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENSWARM_EXPERIMENTAL_MINI_RUNTIME", "1")
    monkeypatch.setenv("OPENSWARM_EXPERIMENTAL_DAG_TASK_RUNTIME", "1")
    monkeypatch.setenv("OPENSWARM_EXPERIMENTAL_DAG_CHAIN_RUNTIME", "1")
    monkeypatch.setenv("OPENSWARM_EXPERIMENTAL_DAG_CONSOLIDATE_RUNTIME", "1")

    store, swarm = _planning_swarm(tmp_path)
    consolidator = ExperimentalDAGConsolidator(store=store)

    response = consolidator.consolidate_final(swarm_id=swarm.id)

    assert response.ok is True
    assert response.status == "completed"

    stored = store.load(swarm.id)
    final_result = stored.final_result

    assert final_result["status"] == "completed"
    assert final_result["artifact_kind"] == "planning_summary"
    assert final_result["implementation_performed"] is False
    assert final_result["created_files"] == []
    assert final_result["artifact_refs"] == []
    assert final_result["claim_guard"]["status"] == "verified_planning_only"
    assert final_result["claim_guard"]["implementation_performed"] is False
    assert "No se implementó" in final_result["summary"]
    assert "app o artifact ejecutable" in final_result["summary"]
    assert stored.artifacts == []
    assert stored.tool_history == []
    assert stored.tasks[-1].status == "completed"


def test_planning_only_consolidator_requires_validation_result(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENSWARM_EXPERIMENTAL_MINI_RUNTIME", "1")
    monkeypatch.setenv("OPENSWARM_EXPERIMENTAL_DAG_TASK_RUNTIME", "1")
    monkeypatch.setenv("OPENSWARM_EXPERIMENTAL_DAG_CHAIN_RUNTIME", "1")
    monkeypatch.setenv("OPENSWARM_EXPERIMENTAL_DAG_CONSOLIDATE_RUNTIME", "1")

    store, swarm = _planning_swarm(tmp_path)
    validation = next(task for task in swarm.tasks if task.task_type == "validation_execute")
    validation.validations = []
    store.save(swarm)

    consolidator = ExperimentalDAGConsolidator(store=store)
    response = consolidator.consolidate_final(swarm_id=swarm.id)

    assert response.ok is False
    assert response.status == "not_ready"
    assert any(error["error"] == "validation_result_missing" for error in response.errors)
    assert store.load(swarm.id).final_result == {}
