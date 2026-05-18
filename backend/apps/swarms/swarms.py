"""Swarm API endpoints.

Thin REST surface over the non-executing SwarmOrchestrator state. This is
intentionally state-only for now: it exposes plans/contracts/messages/artifacts
without launching AgentManager sessions yet.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel

from backend.config.Apps import SubApp
from backend.apps.agents.orchestration.executor import swarm_mvp_executor
from backend.apps.agents.orchestration.orchestrator import swarm_orchestrator
from backend.apps.agents.runtime.experimental_mini_runtime import (
    ExperimentalMiniRuntimeRequest,
    experimental_mini_runtime_enabled,
    experimental_mini_runtime_service,
)
from backend.apps.agents.runtime.experimental_dag_task_runner import (
    ExperimentalDAGTaskRunRequest,
    experimental_dag_task_runner,
    experimental_dag_task_runtime_enabled,
)
from backend.apps.agents.runtime.experimental_dag_chain_runner import (
    ExperimentalWorkerReviewRunRequest,
    experimental_dag_chain_runner,
    experimental_dag_chain_runtime_enabled,
)
from backend.apps.agents.runtime.experimental_dag_consolidator import (
    ExperimentalConsolidateFinalRequest,
    experimental_dag_consolidator,
    experimental_dag_consolidate_runtime_enabled,
)
from backend.apps.agents.runtime.experimental_dag_mini_runner import (
    ExperimentalMiniDAGRunRequest,
    experimental_dag_mini_runner,
    experimental_dag_mini_runner_enabled,
)
from backend.apps.agents.runtime.experimental_dag_dependency_runner import (
    ExperimentalDAGDependencyRunRequest,
    experimental_dag_dependency_runner,
    experimental_dag_dependency_runner_enabled,
)
from backend.apps.agents.runtime.approvals import approval_runtime
from backend.apps.agents.runtime.events import event_trace_runtime
from backend.apps.agents.orchestration.models import AgentToAgentMessage
from backend.apps.agents.providers.ollama_adapter import OllamaAdapter
from backend.apps.agents.runtime.provider import ProviderTurnContext


@asynccontextmanager
async def swarms_lifespan():
    swarm_orchestrator.store.root.mkdir(parents=True, exist_ok=True)
    yield


swarms = SubApp("swarms", swarms_lifespan)


class CreateSwarmRequest(BaseModel):
    user_prompt: str = "Experimental swarm"
    dashboard_id: str | None = None
    workspace_path: str | None = None


class RunMVPRequest(BaseModel):
    workspace_path: str | None = None


class SubmitArtifactRequest(BaseModel):
    from_agent_id: str
    task_id: str
    artifact: dict[str, Any]


class RequestReviewRequest(BaseModel):
    from_agent_id: str
    to_agent_id: str
    task_id: str
    artifact_refs: list[str] = []


class ExperimentalApprovalDecisionRequest(BaseModel):
    message: str | None = None
    updated_input: dict[str, Any] | None = None


class ExperimentalChatRequest(BaseModel):
    message: str
    model: str = "qwen2.5-coder:14b"


def _dump(swarm):
    return swarm.model_dump(mode="json")


def _load_or_404(swarm_id: str):
    try:
        return swarm_orchestrator.store.load(swarm_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Swarm not found")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid swarm_id")


def _openswarm_app_explanation() -> str:
    return (
        "OpenSwarm es una aplicación local-first para trabajar con agentes de IA en tu propia máquina. "
        "Su objetivo es permitir que el usuario converse con un swarm, pida tareas grandes, vea cómo se dividen en pasos, "
        "controle tools con permisos, revise approvals y vea artifacts/resultados dentro del canvas. "
        "La SwarmCard funciona como el chat principal del swarm. "
        "El panel derecho muestra información opcional: tareas, approvals, artifacts, actividad reciente y resultado final. "
        "El sistema está pensado para usar modelos locales con Ollama y mantener el control humano sobre acciones sensibles."
    )


def _is_app_question(user_message: str) -> bool:
    normalized = (user_message or "").strip().lower()
    return (
        "como funciona esta app" in normalized
        or "cómo funciona esta app" in normalized
        or "que es esta app" in normalized
        or "qué es esta app" in normalized
        or "openswarm" in normalized
    )


def _normalize_chat_response(content: str, user_message: str) -> str:
    text = (content or "").strip()

    if _is_app_question(user_message) and "openswarm" not in text.lower():
        return _openswarm_app_explanation()

    if not text:
        return "No se generó una respuesta."

    try:
        parsed = json.loads(text)
    except Exception:
        return text

    if isinstance(parsed, dict):
        for key in ("answer", "response", "content", "message", "summary", "text"):
            value = parsed.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        function_name = str(parsed.get("function_name") or "").strip().lower()
        query = ""
        params = parsed.get("parameters")
        if isinstance(params, dict):
            query = str(params.get("query") or "").strip().lower()

        normalized_user = user_message.strip().lower()
        if "app" in normalized_user or "aplic" in normalized_user or "openswarm" in normalized_user or "app" in query:
            return _openswarm_app_explanation()

        if function_name:
            return "El modelo devolvió una intención estructurada, pero no una respuesta conversacional útil."

    return text


@swarms.router.get("/list")
async def list_swarms(dashboard_id: str | None = None):
    return {"swarms": swarm_orchestrator.store.list(dashboard_id=dashboard_id)}


@swarms.router.post("/create")
async def create_swarm(body: CreateSwarmRequest):
    try:
        swarm = swarm_orchestrator.create_swarm(
            user_prompt=body.user_prompt,
            dashboard_id=body.dashboard_id,
            workspace_path=body.workspace_path,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    event_trace_runtime.create(
        swarm_id=swarm.id,
        event_type="agent_message",
        payload={"message": "swarm_created", "title": swarm.title},
    )
    return _dump(swarm)


@swarms.router.get("/{swarm_id}")
async def get_swarm(swarm_id: str):
    return _dump(_load_or_404(swarm_id))


@swarms.router.get("/{swarm_id}/tasks")
async def get_swarm_tasks(swarm_id: str):
    swarm = _load_or_404(swarm_id)
    return {"tasks": [task.model_dump(mode="json") for task in swarm.tasks]}


@swarms.router.get("/{swarm_id}/agents")
async def get_swarm_agents(swarm_id: str):
    swarm = _load_or_404(swarm_id)
    return {"agents": [contract.model_dump(mode="json") for contract in swarm.contracts]}


@swarms.router.get("/{swarm_id}/messages")
async def get_swarm_messages(swarm_id: str):
    swarm = _load_or_404(swarm_id)
    return {"messages": [message.model_dump(mode="json") for message in swarm.messages]}


@swarms.router.get("/{swarm_id}/artifacts")
async def get_swarm_artifacts(swarm_id: str):
    swarm = _load_or_404(swarm_id)
    return {"artifacts": swarm.artifacts}


@swarms.router.post("/{swarm_id}/experimental/chat")
async def experimental_swarm_chat(swarm_id: str, body: ExperimentalChatRequest):
    swarm = _load_or_404(swarm_id)
    user_message = (body.message or "").strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="message is required")
    if getattr(swarm, "intent", "task") != "chat":
        raise HTTPException(status_code=400, detail="Swarm is not a chat-intent swarm")

    coordinator_id = swarm.coordinator_contract_id or (swarm.contracts[0].id if swarm.contracts else "swarm")
    swarm.messages.append(
        AgentToAgentMessage(
            type="chat_message",
            from_agent_id="user",
            to_agent_id=coordinator_id,
            payload={"role": "user", "content": user_message},
            requires_response=True,
        )
    )

    adapter = OllamaAdapter(allow_network=True, supports_json_mode=False)
    context = ProviderTurnContext(
        session_id=swarm.id,
        agent_id=coordinator_id,
        model=body.model,
        system_prompt=(
            "You are OpenSwarm's local-first swarm chat coordinator. "
            "Answer in plain text, not JSON. "
            "Answer in the same language as the user. "
            "Answer normal user questions clearly and concisely. "
            "Do not claim that you executed tools, created files, or ran tasks unless the runtime did so. "
            "If the user asks for an executable project task, explain that it should be run as a task swarm."
        ),
        messages=[{"role": "user", "content": user_message}],
        tools=[],
    )

    assistant_content = ""
    provider_events: list[dict[str, Any]] = []
    async for event in adapter.run_turn(context):
        provider_events.append({"type": event.type, "payload": event.payload})
        if event.type == "message_final":
            message = event.payload.get("message") or {}
            assistant_content = str(message.get("content") or "").strip()
        elif event.type == "error":
            raise HTTPException(status_code=500, detail=str(event.payload.get("error") or "Ollama chat failed"))

    assistant_content = _normalize_chat_response(assistant_content, user_message)

    swarm.messages.append(
        AgentToAgentMessage(
            type="chat_message",
            from_agent_id=coordinator_id,
            to_agent_id="user",
            payload={"role": "assistant", "content": assistant_content},
            requires_response=False,
        )
    )
    swarm.final_result = {
        "status": "completed",
        "summary": assistant_content,
        "intent": "chat",
    }
    swarm = swarm_orchestrator.store.save(swarm)

    event_trace_runtime.create(
        swarm_id=swarm.id,
        event_type="chat_completed",
        payload={"message": "chat_response_generated"},
    )

    return {**_dump(swarm), "provider_events": provider_events}


@swarms.router.get("/{swarm_id}/events")
async def get_swarm_events(swarm_id: str):
    swarm = _load_or_404(swarm_id)
    persisted_events = [event for event in swarm.events if isinstance(event, dict)]
    memory_events = [event.to_dict() for event in event_trace_runtime.list_swarm_events(swarm_id)]

    merged: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for event in [*persisted_events, *memory_events]:
        event_id = str(event.get("id") or "")
        if event_id and event_id in seen_ids:
            continue
        if event_id:
            seen_ids.add(event_id)
        merged.append(event)

    return {"events": merged}


@swarms.router.get("/{swarm_id}/experimental/approvals")
async def experimental_list_approvals(swarm_id: str, status: str | None = None):
    _load_or_404(swarm_id)
    valid_statuses = {"pending", "allowed", "denied", "resumed", "resume_failed"}
    if status is not None and status not in valid_statuses:
        raise HTTPException(status_code=400, detail="status must be pending, allowed, denied, resumed, or resume_failed")
    approvals = approval_runtime.list_approvals(swarm_id=swarm_id, status=status)  # type: ignore[arg-type]
    pending_count = len(approval_runtime.list_approvals(swarm_id=swarm_id, status="pending"))
    return {"approvals": approvals, "pending_count": pending_count}


@swarms.router.get("/{swarm_id}/experimental/approvals/{approval_id}")
async def experimental_get_approval(swarm_id: str, approval_id: str):
    _load_or_404(swarm_id)
    approval = approval_runtime.get_approval(approval_id, swarm_id=swarm_id)
    if not approval:
        raise HTTPException(status_code=404, detail=f"approval not found: {approval_id}")
    return {"approval": approval}


@swarms.router.post("/{swarm_id}/experimental/approvals/{approval_id}/allow")
async def experimental_allow_approval(swarm_id: str, approval_id: str, body: ExperimentalApprovalDecisionRequest | None = None):
    _load_or_404(swarm_id)
    payload = body or ExperimentalApprovalDecisionRequest()
    try:
        decision = approval_runtime.resolve_request(
            approval_id,
            behavior="allow",
            swarm_id=swarm_id,
            message=payload.message,
            updated_input=payload.updated_input,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    approval = approval_runtime.get_approval(approval_id, swarm_id=swarm_id)
    return {"ok": True, "approval": approval, "decision": decision.to_dict(), "resume_supported": True}


@swarms.router.post("/{swarm_id}/experimental/approvals/{approval_id}/deny")
async def experimental_deny_approval(swarm_id: str, approval_id: str, body: ExperimentalApprovalDecisionRequest | None = None):
    _load_or_404(swarm_id)
    payload = body or ExperimentalApprovalDecisionRequest()
    try:
        decision = approval_runtime.resolve_request(
            approval_id,
            behavior="deny",
            swarm_id=swarm_id,
            message=payload.message,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    approval = approval_runtime.get_approval(approval_id, swarm_id=swarm_id)
    return {"ok": True, "approval": approval, "decision": decision.to_dict()}


@swarms.router.post("/{swarm_id}/experimental/approvals/{approval_id}/resume")
async def experimental_resume_approval(swarm_id: str, approval_id: str):
    _load_or_404(swarm_id)
    try:
        result = approval_runtime.resume_approval_tool(approval_id, swarm_id=swarm_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    approval = approval_runtime.get_approval(approval_id, swarm_id=swarm_id)
    return {"ok": result.ok, "approval": approval, "result": result.to_history_entry()}


@swarms.router.post("/{swarm_id}/run-mvp")
async def run_swarm_mvp(swarm_id: str, body: RunMVPRequest | None = None):
    try:
        swarm = swarm_mvp_executor.run_readme_review_mvp(
            swarm_id,
            workspace_path=body.workspace_path if body else None,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Swarm not found")
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _dump(swarm)


@swarms.router.post("/{swarm_id}/experimental/run-task")
async def experimental_run_task(swarm_id: str, body: ExperimentalMiniRuntimeRequest):
    if not experimental_mini_runtime_enabled():
        raise HTTPException(status_code=404, detail="Experimental mini runtime is disabled")
    _load_or_404(swarm_id)
    try:
        result = await experimental_mini_runtime_service.run_ollama_task(body=body, swarm_id=swarm_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result.model_dump(mode="json")


@swarms.router.post("/{swarm_id}/experimental/run-task/{task_id}")
async def experimental_run_existing_task(swarm_id: str, task_id: str, body: ExperimentalDAGTaskRunRequest):
    if not experimental_dag_task_runtime_enabled():
        raise HTTPException(status_code=404, detail="Experimental DAG task runtime is disabled")
    _load_or_404(swarm_id)
    try:
        result = await experimental_dag_task_runner.run_task(swarm_id=swarm_id, task_id=task_id, body=body)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result.model_dump(mode="json")


@swarms.router.post("/{swarm_id}/experimental/run-worker-review")
async def experimental_run_worker_review(swarm_id: str, body: ExperimentalWorkerReviewRunRequest):
    if not experimental_dag_chain_runtime_enabled():
        raise HTTPException(status_code=404, detail="Experimental DAG chain runtime is disabled")
    _load_or_404(swarm_id)
    try:
        result = await experimental_dag_chain_runner.run_worker_review(swarm_id=swarm_id, body=body)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result.model_dump(mode="json")


@swarms.router.post("/{swarm_id}/experimental/consolidate-final")
async def experimental_consolidate_final(swarm_id: str, body: ExperimentalConsolidateFinalRequest | None = None):
    if not experimental_dag_consolidate_runtime_enabled():
        raise HTTPException(status_code=404, detail="Experimental DAG consolidate runtime is disabled")
    _load_or_404(swarm_id)
    try:
        result = experimental_dag_consolidator.consolidate_final(swarm_id=swarm_id, body=body)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result.model_dump(mode="json")


@swarms.router.post("/{swarm_id}/experimental/run-mini-dag")
async def experimental_run_mini_dag(swarm_id: str, body: ExperimentalMiniDAGRunRequest):
    if not experimental_dag_mini_runner_enabled():
        raise HTTPException(status_code=404, detail="Experimental DAG mini runner is disabled")
    _load_or_404(swarm_id)
    try:
        result = await experimental_dag_mini_runner.run_mini_dag(swarm_id=swarm_id, body=body)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result.model_dump(mode="json")


@swarms.router.post("/{swarm_id}/experimental/run-dag-dependencies")
async def experimental_run_dag_dependencies(swarm_id: str, body: ExperimentalDAGDependencyRunRequest):
    if not experimental_dag_dependency_runner_enabled():
        raise HTTPException(status_code=404, detail="Experimental DAG dependency runner is disabled")
    _load_or_404(swarm_id)
    try:
        result = await experimental_dag_dependency_runner.run_dag_dependencies(swarm_id=swarm_id, body=body)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result.model_dump(mode="json")


@swarms.router.post("/{swarm_id}/pause")
async def pause_swarm(swarm_id: str):
    try:
        swarm = swarm_orchestrator.update_status(swarm_id=swarm_id, status="paused")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Swarm not found")
    return _dump(swarm)


@swarms.router.post("/{swarm_id}/resume")
async def resume_swarm(swarm_id: str):
    try:
        swarm = swarm_orchestrator.update_status(swarm_id=swarm_id, status="running")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Swarm not found")
    return _dump(swarm)


@swarms.router.post("/{swarm_id}/cancel")
async def cancel_swarm(swarm_id: str):
    try:
        swarm = swarm_orchestrator.update_status(swarm_id=swarm_id, status="cancelled")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Swarm not found")
    event_trace_runtime.create(
        swarm_id=swarm.id,
        event_type="stop_requested",
        payload={"reason": "api_cancel"},
    )
    return _dump(swarm)


@swarms.router.post("/{swarm_id}/artifacts")
async def submit_artifact(swarm_id: str, body: SubmitArtifactRequest):
    try:
        swarm = swarm_orchestrator.submit_artifact(
            swarm_id=swarm_id,
            from_agent_id=body.from_agent_id,
            task_id=body.task_id,
            artifact=body.artifact,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Swarm not found")
    event_trace_runtime.create(
        swarm_id=swarm.id,
        task_id=body.task_id,
        agent_id=body.from_agent_id,
        event_type="agent_message",
        payload={"message_type": "submit_artifact", "artifact": body.artifact},
    )
    return _dump(swarm)


@swarms.router.post("/{swarm_id}/request-review")
async def request_review(swarm_id: str, body: RequestReviewRequest):
    try:
        swarm = swarm_orchestrator.request_review(
            swarm_id=swarm_id,
            from_agent_id=body.from_agent_id,
            to_agent_id=body.to_agent_id,
            task_id=body.task_id,
            artifact_refs=body.artifact_refs,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Swarm not found")
    event_trace_runtime.create(
        swarm_id=swarm.id,
        task_id=body.task_id,
        agent_id=body.from_agent_id,
        event_type="review_requested",
        payload={"to_agent_id": body.to_agent_id, "artifact_refs": body.artifact_refs},
    )
    return _dump(swarm)
