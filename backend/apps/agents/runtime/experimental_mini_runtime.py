"""Experimental MiniAgentRuntime service.

Feature-flagged service for running a single task through MiniAgentRuntime with
OllamaAdapter. This is intentionally isolated from AgentManager and normal
OpenSwarm flows.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from backend.apps.agents.orchestration.models import AgentContract, TaskNode
from backend.apps.agents.orchestration.store import SwarmStore, swarm_store
from backend.apps.agents.providers.ollama_adapter import OllamaAdapter
from backend.apps.agents.runtime.mini_agent_runtime import MiniAgentRuntime, MiniAgentRuntimeContext, MiniAgentRuntimeResult

EXPERIMENTAL_MINI_RUNTIME_FLAG = "OPENSWARM_EXPERIMENTAL_MINI_RUNTIME"
ALLOWED_EXPERIMENTAL_TOOLS = {"Read", "Write", "Edit", "Diff", "Glob", "Grep", "SearchFiles", "SearchText"}


class ExperimentalMiniRuntimeRequest(BaseModel):
    model: str = "qwen2.5-coder:14b"
    task: str
    workspace_path: str | None = None
    allowed_tools: list[str] = Field(default_factory=lambda: ["Read", "Write", "Edit", "SearchFiles", "SearchText"])
    base_url: str | None = None
    max_turns: int = 8


class ExperimentalMiniRuntimeResponse(BaseModel):
    ok: bool
    status: str
    enabled: bool
    swarm_id: str | None = None
    task_id: str | None = None
    agent_contract_id: str | None = None
    workspace_path: str | None = None
    final_message: dict[str, Any] | None = None
    tool_history: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    turns: int = 0
    persisted: bool = False


def experimental_mini_runtime_enabled() -> bool:
    return os.environ.get(EXPERIMENTAL_MINI_RUNTIME_FLAG) == "1"


class ExperimentalMiniRuntimeService:
    def __init__(self, *, store: SwarmStore | None = None, runtime: MiniAgentRuntime | None = None) -> None:
        self.store = store or swarm_store
        self.runtime = runtime or MiniAgentRuntime(store=self.store)

    async def run_ollama_task(
        self,
        *,
        body: ExperimentalMiniRuntimeRequest,
        swarm_id: str | None = None,
    ) -> ExperimentalMiniRuntimeResponse:
        if not experimental_mini_runtime_enabled():
            return ExperimentalMiniRuntimeResponse(ok=False, status="disabled", enabled=False, errors=[{"error": f"Set {EXPERIMENTAL_MINI_RUNTIME_FLAG}=1 to enable"}])

        allowed_tools = self._validate_allowed_tools(body.allowed_tools)
        workspace = self._resolve_workspace(body.workspace_path, swarm_id=swarm_id)
        model = self._normalize_model(body.model)
        adapter = OllamaAdapter(base_url=body.base_url, allow_network=True)
        health = adapter.healthcheck(timeout_seconds=2.0)
        if not health.get("ok"):
            return ExperimentalMiniRuntimeResponse(
                ok=False,
                status="provider_unavailable",
                enabled=True,
                swarm_id=swarm_id,
                workspace_path=str(workspace),
                errors=[{"error": "Ollama is not available", "detail": health}],
            )

        contract = AgentContract(
            role="DocumentationAgent",
            objective="Execute one experimental local-provider task with evidence and safe tools only.",
            allowed_tools=allowed_tools,
            provider="ollama",
            model=model,
            acceptance_criteria=["Use only allowed safe tools.", "Return final evidence."],
        )
        task = TaskNode(
            title="Experimental Mini Runtime Task",
            objective=body.task,
            assigned_contract_id=contract.id,
        )

        context_store = self.store if swarm_id else None
        if swarm_id:
            self._attach_to_swarm_if_needed(swarm_id, contract, task)

        result = await self.runtime.run_agent_task(MiniAgentRuntimeContext(
            contract=contract,
            task=task,
            provider=adapter,
            workspace_path=str(workspace),
            model=model,
            provider_tool_format="ollama",
            swarm_id=swarm_id,
            store=context_store,
            max_turns=max(1, min(body.max_turns, 16)),
            inputs={"task": body.task},
        ))
        return self._response(result, enabled=True, swarm_id=swarm_id, workspace_path=str(workspace))

    @staticmethod
    def _validate_allowed_tools(tools: list[str]) -> list[str]:
        result: list[str] = []
        for tool in tools:
            if tool not in ALLOWED_EXPERIMENTAL_TOOLS:
                raise ValueError(f"Tool not allowed in experimental mini runtime: {tool}")
            if tool not in result:
                result.append(tool)
        return result

    def _resolve_workspace(self, workspace_path: str | None, *, swarm_id: str | None) -> Path:
        if workspace_path:
            workspace = Path(workspace_path).expanduser().resolve()
        elif swarm_id:
            workspace = (self.store._path(swarm_id).parent / "experimental_workspace").resolve()
        else:
            workspace = (self.store.root / "experimental" / "workspace").resolve()
        workspace.mkdir(parents=True, exist_ok=True)
        return workspace

    @staticmethod
    def _normalize_model(model: str) -> str:
        clean = str(model or "").strip()
        if not clean:
            raise ValueError("model is required")
        return clean if clean.startswith("ollama/") else f"ollama/{clean}"

    def _attach_to_swarm_if_needed(self, swarm_id: str, contract: AgentContract, task: TaskNode) -> None:
        swarm = self.store.load(swarm_id)
        swarm.contracts.append(contract)
        swarm.tasks.append(task)
        self.store.save(swarm)

    @staticmethod
    def _response(result: MiniAgentRuntimeResult, *, enabled: bool, swarm_id: str | None, workspace_path: str) -> ExperimentalMiniRuntimeResponse:
        return ExperimentalMiniRuntimeResponse(
            ok=result.status == "completed",
            status=result.status,
            enabled=enabled,
            swarm_id=swarm_id,
            task_id=result.task_id,
            agent_contract_id=result.agent_contract_id,
            workspace_path=workspace_path,
            final_message=result.final_message,
            tool_history=result.tool_history,
            evidence=result.evidence,
            errors=result.errors,
            turns=result.turns,
            persisted=result.persisted,
        )


experimental_mini_runtime_service = ExperimentalMiniRuntimeService()
