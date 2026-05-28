"""Swarm orchestration models.

These are provider/runtime neutral state contracts. They deliberately avoid
executing agents or importing AgentManager so they can be introduced safely.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


AgentRole = Literal[
    "CoordinatorAgent",
    "PlannerAgent",
    "ArchitectAgent",
    "BackendAgent",
    "FrontendAgent",
    "TesterAgent",
    "ReviewerAgent",
    "SecurityAgent",
    "DocumentationAgent",
]

TaskStatus = Literal["pending", "running", "blocked", "completed", "failed", "cancelled"]
SwarmStatus = Literal["draft", "running", "paused", "completed", "failed", "cancelled"]
SwarmIntent = Literal["chat", "task"]

MessageType = Literal[
    "send_message_to_agent",
    "request_review",
    "report_blocker",
    "submit_artifact",
    "ask_coordinator",
    "broadcast_to_swarm",
    "chat_message",
]

EvidenceAction = Literal[
    "read",
    "created",
    "modified",
    "executed",
    "validated",
    "generated",
    "output",
]

EvidenceStatus = Literal["pending", "completed", "failed", "skipped"]


def _now_iso() -> str:
    return datetime.now().isoformat()


class AgentContract(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    role: AgentRole
    objective: str
    allowed_tools: list[str] = Field(default_factory=list)
    provider: str | None = None
    model: str | None = None
    acceptance_criteria: list[str] = Field(default_factory=list)
    output_contract: dict[str, Any] = Field(default_factory=dict)


class EvidenceRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    kind: str
    swarm_id: str | None = None
    task_id: str | None = None
    agent_id: str | None = None
    session_id: str | None = None
    tool_call_id: str | None = None
    tool_name: str | None = None
    event_id: str | None = None
    artifact_id: str | None = None
    file_path: str | None = None
    absolute_path: str | None = None
    command: str | None = None
    action: EvidenceAction | None = None
    status: EvidenceStatus = "completed"
    summary: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_now_iso)


class TaskNode(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    title: str
    objective: str
    task_type: str | None = None
    assigned_contract_id: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    status: TaskStatus = "pending"
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any] | EvidenceRecord] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    validations: list[dict[str, Any]] = Field(default_factory=list)
    touched_files: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=_now_iso)
    updated_at: str = Field(default_factory=_now_iso)


class AgentToAgentMessage(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    type: MessageType
    from_agent_id: str
    to_agent_id: str | None = None
    task_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    artifact_refs: list[str] = Field(default_factory=list)
    requires_response: bool = False
    created_at: str = Field(default_factory=_now_iso)


class SwarmState(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    title: str
    user_prompt: str
    intent: SwarmIntent = "task"
    status: SwarmStatus = "draft"
    dashboard_id: str | None = None
    workspace_path: str | None = None
    coordinator_contract_id: str | None = None
    contracts: list[AgentContract] = Field(default_factory=list)
    tasks: list[TaskNode] = Field(default_factory=list)
    messages: list[AgentToAgentMessage] = Field(default_factory=list)
    decisions: list[dict[str, Any]] = Field(default_factory=list)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    tool_history: list[dict[str, Any]] = Field(default_factory=list)
    events: list[dict[str, Any]] = Field(default_factory=list)
    experimental_approvals: list[dict[str, Any]] = Field(default_factory=list)
    project_intake_state: dict[str, Any] = Field(default_factory=dict)
    orchestration_canvas_state: dict[str, Any] = Field(default_factory=dict)
    configuration: dict[str, Any] = Field(default_factory=dict)
    effective_configuration: dict[str, Any] = Field(default_factory=dict)
    configuration_sources: dict[str, Any] = Field(default_factory=dict)
    configuration_conflicts: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[EvidenceRecord] = Field(default_factory=list)
    final_evidence: list[dict[str, Any] | EvidenceRecord] = Field(default_factory=list)
    final_result: dict[str, Any] = Field(default_factory=dict)
    implementation: dict[str, Any] = Field(default_factory=dict)
    output_bridge: dict[str, Any] = Field(default_factory=dict)
    implementation_state: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_now_iso)
    updated_at: str = Field(default_factory=_now_iso)
