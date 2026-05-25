from dataclasses import dataclass

from backend.apps.agents.orchestration.orchestrator import SwarmOrchestrator
from backend.apps.agents.orchestration.store import SwarmStore
from backend.apps.agents.runtime.mini_agent_runtime import MiniAgentRuntimeResult
from backend.apps.agents.runtime.model_dag_proposal_preview import (
    ModelDAGProposalPreviewRequest,
    ModelDAGProposalPreviewService,
)


@dataclass
class FakeAdapter:
    ok: bool = True

    def healthcheck(self, timeout_seconds: float = 2.0):
        if self.ok:
            return {"ok": True, "base_url": "fake://ollama", "models": []}
        return {"ok": False, "base_url": "fake://ollama", "error": "offline"}


class FakeRuntime:
    def __init__(self, result: MiniAgentRuntimeResult):
        self.result = result
        self.last_context = None

    async def run_agent_task(self, context):
        self.last_context = context
        return self.result


def _service(tmp_path, *, runtime_result, adapter_ok=True):
    store = SwarmStore(root=tmp_path / "swarms")
    orchestrator = SwarmOrchestrator(store=store)
    runtime = FakeRuntime(runtime_result)
    service = ModelDAGProposalPreviewService(
        store=store,
        orchestrator=orchestrator,
        runtime=runtime,
        adapter_factory=lambda **kwargs: FakeAdapter(ok=adapter_ok),
    )
    swarm = orchestrator.create_swarm(
        user_prompt="crear app",
        dashboard_id="dash-test",
        intent="chat",
    )
    return service, orchestrator, runtime, swarm


def _assert_only_base_coordinator_contracts(contracts):
    assert all(contract.role == "CoordinatorAgent" for contract in contracts)


async def _run(service, swarm_id):
    return await service.generate_preview(
        swarm_id=swarm_id,
        request=ModelDAGProposalPreviewRequest(
            model="qwen2.5-coder:14b",
            generated_plan={"app_type": "web app", "frontend": "React", "backend": "FastAPI", "database": "PostgreSQL"},
            max_turns=1,
        ),
    )


def test_model_dag_preview_service_accepts_valid_model_output(tmp_path):
    import asyncio

    result = MiniAgentRuntimeResult(
        status="completed",
        task_id="tmp-task",
        agent_contract_id="tmp-agent",
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
                  "objective": "Create README.",
                  "depends_on": ["architecture"]
                }
              ]
            }
            """
        },
        turns=1,
    )
    service, orchestrator, runtime, swarm = _service(tmp_path, runtime_result=result)

    response = asyncio.run(_run(service, swarm.id))
    stored = orchestrator.store.load(swarm.id)

    assert response.ok is True
    assert response.status == "accepted"
    assert response.validation_errors == []
    assert stored.tasks == []
    _assert_only_base_coordinator_contracts(stored.contracts)
    assert stored.decisions[-1]["source"] == "model_dag_proposal"
    assert stored.decisions[-1]["status"] == "accepted"
    assert runtime.last_context.swarm_id is None
    assert runtime.last_context.store is None
    assert runtime.last_context.contract.allowed_tools == []


def test_model_dag_preview_service_rejects_invalid_json_without_tasks(tmp_path):
    import asyncio

    result = MiniAgentRuntimeResult(
        status="completed",
        task_id="tmp-task",
        agent_contract_id="tmp-agent",
        final_message={"content": "no hay json"},
        turns=1,
    )
    service, orchestrator, runtime, swarm = _service(tmp_path, runtime_result=result)

    response = asyncio.run(_run(service, swarm.id))
    stored = orchestrator.store.load(swarm.id)

    assert response.ok is False
    assert response.status == "rejected"
    assert response.validation_errors[0]["error"] == "model_dag_proposal_response_not_json"
    assert stored.tasks == []
    _assert_only_base_coordinator_contracts(stored.contracts)
    assert stored.decisions[-1]["status"] == "rejected"
    assert runtime.last_context.contract.allowed_tools == []


def test_model_dag_preview_service_handles_provider_unavailable(tmp_path):
    import asyncio

    result = MiniAgentRuntimeResult(
        status="completed",
        task_id="tmp-task",
        agent_contract_id="tmp-agent",
        final_message={"content": "{}"},
    )
    service, orchestrator, runtime, swarm = _service(tmp_path, runtime_result=result, adapter_ok=False)

    response = asyncio.run(_run(service, swarm.id))
    stored = orchestrator.store.load(swarm.id)

    assert response.ok is False
    assert response.status == "provider_unavailable"
    assert response.validation_errors[0]["error"] == "provider_unavailable"
    assert stored.tasks == []
    _assert_only_base_coordinator_contracts(stored.contracts)
    assert stored.decisions[-1]["status"] == "rejected"
    assert runtime.last_context is None


def test_model_dag_preview_service_handles_model_failed(tmp_path):
    import asyncio

    result = MiniAgentRuntimeResult(
        status="failed",
        task_id="tmp-task",
        agent_contract_id="tmp-agent",
        final_message=None,
        errors=[{"error": "runtime_failed"}],
        turns=1,
    )
    service, orchestrator, runtime, swarm = _service(tmp_path, runtime_result=result)

    response = asyncio.run(_run(service, swarm.id))
    stored = orchestrator.store.load(swarm.id)

    assert response.ok is False
    assert response.status == "model_failed"
    assert response.validation_errors[0]["error"] == "model_failed"
    assert stored.tasks == []
    _assert_only_base_coordinator_contracts(stored.contracts)
    assert stored.decisions[-1]["status"] == "rejected"
    assert runtime.last_context.swarm_id is None
    assert runtime.last_context.store is None


def test_model_dag_preview_service_rejects_semantically_incompatible_static_app(tmp_path):
    import asyncio

    result = MiniAgentRuntimeResult(
        status="completed",
        task_id="tmp-task",
        agent_contract_id="tmp-agent",
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
        },
        turns=1,
    )
    service, orchestrator, runtime, swarm = _service(tmp_path, runtime_result=result)

    response = asyncio.run(_run(service, swarm.id))
    stored = orchestrator.store.load(swarm.id)

    assert response.ok is False
    assert response.status == "rejected"
    assert any(error["error"] == "semantically_incompatible_task_type" for error in response.validation_errors)
    assert stored.tasks == []
    _assert_only_base_coordinator_contracts(stored.contracts)
    assert stored.decisions[-1]["status"] == "rejected"
