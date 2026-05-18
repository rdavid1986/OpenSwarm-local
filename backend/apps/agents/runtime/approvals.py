"""Experimental Approval Runtime.

Runtime aislado para approvals del nuevo ToolRuntime/PolicyRuntime.
No reemplaza el HITL legacy de AgentManager y no usa /api/agents/approval.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from backend.apps.agents.runtime.events import EventTraceRuntime, event_trace_runtime


ApprovalBehavior = Literal["allow", "deny"]
ApprovalStatus = Literal["pending", "allowed", "denied", "resumed", "resume_failed"]


@dataclass(frozen=True)
class RuntimeApprovalRequest:
    id: str
    tool_name: str
    tool_input: dict[str, Any]
    workspace_path: str
    session_id: str | None = None
    swarm_id: str | None = None
    agent_id: str | None = None
    task_id: str | None = None
    reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "status": "pending",
            "tool_name": self.tool_name,
            "tool_input": self.tool_input,
            "workspace_path": self.workspace_path,
            "session_id": self.session_id,
            "swarm_id": self.swarm_id,
            "agent_id": self.agent_id,
            "task_id": self.task_id,
            "reason": self.reason,
            "metadata": self.metadata,
            "decision": None,
            "resolved_at": None,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class RuntimeApprovalDecision:
    request_id: str
    behavior: ApprovalBehavior
    message: str | None = None
    updated_input: dict[str, Any] | None = None
    decided_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "behavior": self.behavior,
            "message": self.message,
            "updated_input": self.updated_input,
            "decided_at": self.decided_at,
        }


class ApprovalRuntime:
    def __init__(self, *, events: EventTraceRuntime | None = None, store: Any | None = None) -> None:
        self.events = events or event_trace_runtime
        self.store = store
        self._pending: dict[str, RuntimeApprovalRequest] = {}
        self._decisions: dict[str, RuntimeApprovalDecision] = {}

    def create_request(
        self,
        *,
        tool_name: str,
        tool_input: dict[str, Any],
        workspace_path: str,
        session_id: str | None = None,
        swarm_id: str | None = None,
        agent_id: str | None = None,
        task_id: str | None = None,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
        emit_event: bool = True,
    ) -> RuntimeApprovalRequest:
        request = RuntimeApprovalRequest(
            id=uuid4().hex,
            tool_name=tool_name,
            tool_input=dict(tool_input or {}),
            workspace_path=workspace_path,
            session_id=session_id,
            swarm_id=swarm_id,
            agent_id=agent_id,
            task_id=task_id,
            reason=reason,
            metadata=dict(metadata or {}),
        )
        self._pending[request.id] = request
        self._persist_request(request)
        if emit_event:
            self.events.create(
                "approval_required",
                session_id=session_id,
                swarm_id=swarm_id,
                agent_id=agent_id,
                task_id=task_id,
                payload={"approval_request": request.to_dict()},
            )
        return request

    def resolve_request(
        self,
        request_id: str,
        *,
        behavior: ApprovalBehavior,
        swarm_id: str | None = None,
        message: str | None = None,
        updated_input: dict[str, Any] | None = None,
    ) -> RuntimeApprovalDecision:
        if behavior not in {"allow", "deny"}:
            raise ValueError("behavior must be allow or deny")

        approval = self.get_approval(request_id, swarm_id=swarm_id)
        if not approval and request_id not in self._pending:
            raise FileNotFoundError(f"approval request not found: {request_id}")
        if approval and approval.get("status") != "pending":
            raise ValueError(f"approval is already resolved: {request_id}")

        request = self._pending.pop(request_id, None)
        decision = RuntimeApprovalDecision(
            request_id=request_id,
            behavior=behavior,
            message=message,
            updated_input=updated_input,
        )
        self._decisions[request_id] = decision
        resolved_approval = self._persist_decision(
            request_id=request_id,
            behavior=behavior,
            decision=decision,
            swarm_id=swarm_id or (request.swarm_id if request else None),
        )
        event_swarm_id = swarm_id or (request.swarm_id if request else (approval or {}).get("swarm_id"))
        event_agent_id = request.agent_id if request else (approval or {}).get("agent_id")
        event_task_id = request.task_id if request else (approval or {}).get("task_id")
        event_session_id = request.session_id if request else (approval or {}).get("session_id")
        event_type = "approval_allowed" if behavior == "allow" else "approval_denied"

        self.events.create(
            event_type,
            session_id=event_session_id,
            swarm_id=event_swarm_id,
            agent_id=event_agent_id,
            task_id=event_task_id,
            payload={
                "approval": resolved_approval or approval or (request.to_dict() if request else {}),
                "approval_decision": decision.to_dict(),
                "resume_supported": behavior == "allow",
            },
        )
        if behavior == "deny":
            self.events.create(
                "tool_denied",
                session_id=event_session_id,
                swarm_id=event_swarm_id,
                agent_id=event_agent_id,
                task_id=event_task_id,
                payload={
                    "tool": (resolved_approval or approval or {}).get("tool_name"),
                    "status": "denied",
                    "ok": False,
                    "reason": "approval_denied",
                    "approval_id": request_id,
                    "approval_decision": decision.to_dict(),
                },
            )
        return decision

    def resume_approval_tool(
        self,
        approval_id: str,
        *,
        swarm_id: str,
        tool_runtime: Any | None = None,
    ) -> Any:
        store = self._store()
        swarm = store.load(swarm_id)
        approval = self._find_approval(swarm, approval_id)
        self._validate_resume_approval(approval, approval_id=approval_id)

        from backend.apps.agents.runtime.tools import ToolRuntime, ToolResult

        runtime = tool_runtime or ToolRuntime(events=self.events, approvals=self)
        call = self._build_tool_call_from_approval(approval)
        context = self._build_context_from_approval(approval)
        history: list[dict[str, Any]] = []

        self.events.create(
            "approval_resumed",
            session_id=approval.get("session_id"),
            swarm_id=swarm_id,
            agent_id=approval.get("agent_id"),
            task_id=approval.get("task_id"),
            payload={"approval_id": approval_id, "tool": approval.get("tool_name")},
        )

        try:
            result = runtime.execute_tool(call, context, history=history)
        except Exception as exc:
            result = ToolResult(
                call_id=call.id,
                tool_name=str(approval.get("tool_name") or call.name),
                status="failed",
                ok=False,
                error=str(exc),
                started_at=datetime.now().isoformat(),
                completed_at=datetime.now().isoformat(),
                metadata={
                    "session_id": approval.get("session_id"),
                    "swarm_id": swarm_id,
                    "agent_id": approval.get("agent_id"),
                    "task_id": approval.get("task_id"),
                    "workspace_path": approval.get("workspace_path"),
                    "approval_id": approval_id,
                    "policy_resume_approved": True,
                },
            )
            history.append(result.to_history_entry())

        if not getattr(result, "ok", False):
            self.events.create(
                "approval_resume_failed",
                session_id=approval.get("session_id"),
                swarm_id=swarm_id,
                agent_id=approval.get("agent_id"),
                task_id=approval.get("task_id"),
                payload={
                    "approval_id": approval_id,
                    "tool": approval.get("tool_name"),
                    "result": result.to_history_entry(),
                },
            )

        self._mark_resume_result(
            approval_id=approval_id,
            swarm_id=swarm_id,
            result=result,
            history=history,
        )
        return result

    def list_pending(self, *, swarm_id: str | None = None, session_id: str | None = None) -> list[dict[str, Any]]:
        if swarm_id is not None:
            try:
                return self.list_approvals(swarm_id=swarm_id, status="pending", session_id=session_id)
            except FileNotFoundError:
                pass
        requests = list(self._pending.values())
        if swarm_id is not None:
            requests = [request for request in requests if request.swarm_id == swarm_id]
        if session_id is not None:
            requests = [request for request in requests if request.session_id == session_id]
        return [request.to_dict() for request in requests]

    def list_approvals(
        self,
        *,
        swarm_id: str,
        status: ApprovalStatus | None = None,
        session_id: str | None = None,
    ) -> list[dict[str, Any]]:
        swarm = self._load_swarm(swarm_id)
        approvals = [dict(item) for item in getattr(swarm, "experimental_approvals", []) if isinstance(item, dict)]
        if status is not None:
            approvals = [approval for approval in approvals if approval.get("status") == status]
        if session_id is not None:
            approvals = [approval for approval in approvals if approval.get("session_id") == session_id]
        return approvals

    def get_approval(self, request_id: str, *, swarm_id: str | None = None) -> dict[str, Any] | None:
        if swarm_id is not None:
            for approval in self.list_approvals(swarm_id=swarm_id):
                if approval.get("id") == request_id:
                    return approval
            return None
        if request_id in self._pending:
            return self._pending[request_id].to_dict()
        decision = self._decisions.get(request_id)
        if decision:
            return {"id": request_id, "status": "allowed" if decision.behavior == "allow" else "denied", "decision": decision.to_dict()}
        return None

    def list_decisions(self) -> list[dict[str, Any]]:
        return [decision.to_dict() for decision in self._decisions.values()]

    def clear(self) -> None:
        self._pending.clear()
        self._decisions.clear()

    def _store(self) -> Any:
        if self.store is not None:
            return self.store
        from backend.apps.agents.orchestration.store import swarm_store

        return swarm_store

    def _load_swarm(self, swarm_id: str) -> Any:
        return self._store().load(swarm_id)

    def _persist_request(self, request: RuntimeApprovalRequest) -> None:
        if not request.swarm_id:
            return
        try:
            store = self._store()
            swarm = store.load(request.swarm_id)
        except FileNotFoundError:
            return
        approval = request.to_dict()
        swarm.experimental_approvals = [
            item for item in swarm.experimental_approvals
            if not (isinstance(item, dict) and item.get("id") == request.id)
        ]
        swarm.experimental_approvals.append(approval)
        store.save(swarm)

    def _persist_decision(
        self,
        *,
        request_id: str,
        behavior: ApprovalBehavior,
        decision: RuntimeApprovalDecision,
        swarm_id: str | None,
    ) -> dict[str, Any] | None:
        if not swarm_id:
            return None
        store = self._store()
        swarm = store.load(swarm_id)
        resolved_at = decision.decided_at
        status = "allowed" if behavior == "allow" else "denied"
        updated: dict[str, Any] | None = None
        approvals: list[dict[str, Any]] = []
        for item in swarm.experimental_approvals:
            if not isinstance(item, dict):
                continue
            current = dict(item)
            if current.get("id") == request_id:
                current["status"] = status
                current["decision"] = decision.to_dict()
                current["resolved_at"] = resolved_at
                updated = current
            approvals.append(current)
        if updated is None:
            raise FileNotFoundError(f"approval request not found: {request_id}")
        swarm.experimental_approvals = approvals
        store.save(swarm)
        return updated

    @staticmethod
    def _find_approval(swarm: Any, approval_id: str) -> dict[str, Any]:
        for item in getattr(swarm, "experimental_approvals", []) or []:
            if isinstance(item, dict) and item.get("id") == approval_id:
                return dict(item)
        raise FileNotFoundError(f"approval request not found: {approval_id}")

    @staticmethod
    def _validate_resume_approval(approval: dict[str, Any], *, approval_id: str) -> None:
        status = approval.get("status")
        if status == "resumed":
            raise RuntimeError(f"approval is already resumed: {approval_id}")
        if status != "allowed":
            raise ValueError(f"approval must be allowed before resume: {approval_id}")

    @staticmethod
    def _build_tool_call_from_approval(approval: dict[str, Any]) -> Any:
        from backend.apps.agents.runtime.tools import ToolCall

        metadata = approval.get("metadata") if isinstance(approval.get("metadata"), dict) else {}
        call_id = metadata.get("tool_call_id") or approval.get("id")
        return ToolCall(
            name=str(approval.get("tool_name") or ""),
            input=dict(approval.get("tool_input") or {}),
            id=str(call_id),
            provider_call_id=metadata.get("provider_call_id"),
            raw_name=metadata.get("raw_name"),
        )

    @staticmethod
    def _build_context_from_approval(approval: dict[str, Any]) -> Any:
        from backend.apps.agents.runtime.tools import ToolExecutionContext

        metadata = approval.get("metadata") if isinstance(approval.get("metadata"), dict) else {}
        resume_metadata = {
            "approval_id": approval.get("id"),
            "policy_resume_approved": True,
            "resume_tool_input": dict(approval.get("tool_input") or {}),
            "provider_tool_format": metadata.get("provider_tool_format"),
            "task_type": metadata.get("task_type"),
            "policy_decision": metadata.get("policy_decision"),
        }
        for key in ("task_type_allowed_tools", "agent_contract_allowed_tools", "policy_scope"):
            if key in metadata:
                resume_metadata[key] = metadata[key]

        allowed_tools = metadata.get("allowed_tools")
        return ToolExecutionContext(
            workspace_path=str(approval.get("workspace_path") or "."),
            session_id=approval.get("session_id"),
            swarm_id=approval.get("swarm_id"),
            agent_id=approval.get("agent_id"),
            task_id=approval.get("task_id"),
            allowed_tools=list(allowed_tools) if isinstance(allowed_tools, list) else None,
            require_human_approval=True,
            metadata=resume_metadata,
        )

    def _mark_resume_result(
        self,
        *,
        approval_id: str,
        swarm_id: str,
        result: Any,
        history: list[dict[str, Any]],
    ) -> None:
        store = self._store()
        swarm = store.load(swarm_id)
        updated: dict[str, Any] | None = None
        approvals: list[dict[str, Any]] = []
        for item in getattr(swarm, "experimental_approvals", []) or []:
            if not isinstance(item, dict):
                continue
            current = dict(item)
            if current.get("id") == approval_id:
                if current.get("status") != "allowed":
                    raise RuntimeError(f"approval is no longer allowed for resume: {approval_id}")
                current["status"] = "resumed" if getattr(result, "ok", False) else "resume_failed"
                current["resumed_at"] = datetime.now().isoformat()
                current["resume_result"] = result.to_history_entry()
                updated = current
            approvals.append(current)
        if updated is None:
            raise FileNotFoundError(f"approval request not found: {approval_id}")

        existing_history_keys = {
            (
                str(item.get("call_id") or ""),
                str(item.get("status") or ""),
                str(item.get("approval_id") or item.get("approval_request_id") or ""),
            )
            for item in swarm.tool_history
            if isinstance(item, dict)
        }
        for entry in history:
            key = (
                str(entry.get("call_id") or ""),
                str(entry.get("status") or ""),
                str(entry.get("approval_id") or entry.get("approval_request_id") or ""),
            )
            if key not in existing_history_keys:
                swarm.tool_history.append(entry)
                existing_history_keys.add(key)

        task_id = updated.get("task_id")
        if task_id:
            for task in getattr(swarm, "tasks", []) or []:
                if getattr(task, "id", None) != task_id:
                    continue
                if getattr(result, "ok", False) and getattr(task, "status", None) == "blocked":
                    task.status = "running"
                    task.updated_at = datetime.now().isoformat()
                elif not getattr(result, "ok", False):
                    task.status = "failed"
                    task.errors.append({"error": "approval_resume_failed", "detail": getattr(result, "error", None)})
                    task.updated_at = datetime.now().isoformat()
                break

        swarm.experimental_approvals = approvals
        store.save(swarm)


approval_runtime = ApprovalRuntime()

# Compatibilidad con backend.apps.agents.runtime.__init__
ApprovalRequestEnvelope = RuntimeApprovalRequest
ApprovalDecision = RuntimeApprovalDecision

