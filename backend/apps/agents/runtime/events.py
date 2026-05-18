"""Event/Trace Runtime facade.

Phase 8 introduces structured event names and a tiny in-memory trace facade.
It does not replace ws_manager/seq_log yet. Future phases can bridge these
events to WebSocket, session messages, and durable swarm/task state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from backend.apps.agents.ws_manager import ws_manager


TraceEventType = Literal[
    "agent_started",
    "agent_message",
    "provider_request",
    "provider_response",
    "tool_requested",
    "tool_approved",
    "tool_denied",
    "tool_started",
    "tool_completed",
    "tool_failed",
    "task_started",
    "task_contract_validation_failed",
    "task_completed",
    "task_failed",
    "dag_started",
    "dag_completed",
    "dag_failed",
    "task_skipped",
    "planner_validated",
    "planner_rejected",
    "consolidation_started",
    "consolidation_completed",
    "review_requested",
    "review_completed",
    "approval_required",
    "approval_allowed",
    "approval_denied",
    "approval_resumed",
    "approval_resume_failed",
    "stop_requested",
    "agent_stopped",
    "swarm_completed",
    "error",
]


@dataclass(frozen=True)
class TraceEvent:
    type: TraceEventType
    payload: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    swarm_id: str | None = None
    session_id: str | None = None
    agent_id: str | None = None
    task_id: str | None = None
    parent_event_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "created_at": self.created_at,
            "swarm_id": self.swarm_id,
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "task_id": self.task_id,
            "parent_event_id": self.parent_event_id,
            "payload": self.payload,
        }


class EventTraceRuntime:
    """Structured event collector and optional WS bridge."""

    def __init__(self) -> None:
        self._events_by_session: dict[str, list[TraceEvent]] = {}
        self._events_by_swarm: dict[str, list[TraceEvent]] = {}

    def record(self, event: TraceEvent) -> TraceEvent:
        if event.session_id:
            self._events_by_session.setdefault(event.session_id, []).append(event)
        if event.swarm_id:
            self._events_by_swarm.setdefault(event.swarm_id, []).append(event)
            self._persist_swarm_event(event)
        return event

    @staticmethod
    def _persist_swarm_event(event: TraceEvent) -> None:
        if not event.swarm_id:
            return
        try:
            from backend.apps.agents.orchestration.store import swarm_store

            swarm = swarm_store.load(event.swarm_id)
            event_dict = event.to_dict()
            existing_ids = {str(item.get("id")) for item in swarm.events if isinstance(item, dict)}
            if event_dict["id"] not in existing_ids:
                swarm.events.append(event_dict)
                swarm_store.save(swarm)
        except FileNotFoundError:
            return
        except Exception:
            return

    def create(
        self,
        event_type: TraceEventType,
        *,
        payload: dict[str, Any] | None = None,
        swarm_id: str | None = None,
        session_id: str | None = None,
        agent_id: str | None = None,
        task_id: str | None = None,
        parent_event_id: str | None = None,
    ) -> TraceEvent:
        return self.record(
            TraceEvent(
                type=event_type,
                payload=payload or {},
                swarm_id=swarm_id,
                session_id=session_id,
                agent_id=agent_id,
                task_id=task_id,
                parent_event_id=parent_event_id,
            )
        )

    async def emit_session_event(
        self,
        event_type: TraceEventType,
        *,
        session_id: str,
        payload: dict[str, Any] | None = None,
        swarm_id: str | None = None,
        agent_id: str | None = None,
        task_id: str | None = None,
        parent_event_id: str | None = None,
        ws_event: str = "trace:event",
    ) -> TraceEvent:
        event = self.create(
            event_type,
            payload=payload,
            swarm_id=swarm_id,
            session_id=session_id,
            agent_id=agent_id,
            task_id=task_id,
            parent_event_id=parent_event_id,
        )
        await ws_manager.send_to_session(session_id, ws_event, event.to_dict())
        return event

    async def emit_global_event(
        self,
        event_type: TraceEventType,
        *,
        payload: dict[str, Any] | None = None,
        swarm_id: str | None = None,
        session_id: str | None = None,
        agent_id: str | None = None,
        task_id: str | None = None,
        parent_event_id: str | None = None,
        ws_event: str = "trace:event",
    ) -> TraceEvent:
        event = self.create(
            event_type,
            payload=payload,
            swarm_id=swarm_id,
            session_id=session_id,
            agent_id=agent_id,
            task_id=task_id,
            parent_event_id=parent_event_id,
        )
        await ws_manager.broadcast_global(ws_event, event.to_dict())
        return event

    def list_session_events(self, session_id: str) -> list[TraceEvent]:
        return list(self._events_by_session.get(session_id, []))

    def list_swarm_events(self, swarm_id: str) -> list[TraceEvent]:
        return list(self._events_by_swarm.get(swarm_id, []))

    def clear(self) -> None:
        self._events_by_session.clear()
        self._events_by_swarm.clear()


event_trace_runtime = EventTraceRuntime()
