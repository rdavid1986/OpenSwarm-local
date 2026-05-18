"""Experimental single-DAG-task runner.

Runs exactly one existing TaskNode from a SwarmState through MiniAgentRuntime +
OllamaAdapter. This is feature-flagged and intentionally does not traverse DAG
dependencies, run reviewers, consolidate, or touch AgentManager.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, Field

from backend.apps.agents.orchestration.models import AgentContract, AgentToAgentMessage, SwarmState, TaskNode, _now_iso
from backend.apps.agents.orchestration.store import SwarmStore, swarm_store
from backend.apps.agents.providers.ollama_adapter import OllamaAdapter
from backend.apps.agents.runtime.experimental_mini_runtime import (
    ALLOWED_EXPERIMENTAL_TOOLS,
    ExperimentalMiniRuntimeResponse,
    experimental_mini_runtime_enabled,
)
from backend.apps.agents.runtime.mini_agent_runtime import MiniAgentRuntime, MiniAgentRuntimeContext, MiniAgentRuntimeResult
from backend.apps.agents.runtime.experimental_task_type_registry import classify_experimental_task, get_experimental_task_spec

EXPERIMENTAL_DAG_TASK_RUNTIME_FLAG = "OPENSWARM_EXPERIMENTAL_DAG_TASK_RUNTIME"


class ExperimentalDAGTaskRunRequest(BaseModel):
    model: str = "qwen2.5-coder:14b"
    base_url: str | None = None
    allowed_tools: list[str] | None = None
    max_turns: int = 8
    workspace_path: str | None = None


def experimental_dag_task_runtime_enabled() -> bool:
    import os

    return experimental_mini_runtime_enabled() and os.environ.get(EXPERIMENTAL_DAG_TASK_RUNTIME_FLAG) == "1"


AdapterFactory = Callable[..., OllamaAdapter]


class ExperimentalDAGTaskRunner:
    def __init__(
        self,
        *,
        store: SwarmStore | None = None,
        runtime: MiniAgentRuntime | None = None,
        adapter_factory: AdapterFactory | None = None,
    ) -> None:
        self.store = store or swarm_store
        self.runtime = runtime or MiniAgentRuntime(store=self.store)
        self.adapter_factory = adapter_factory or OllamaAdapter

    async def run_task(
        self,
        *,
        swarm_id: str,
        task_id: str,
        body: ExperimentalDAGTaskRunRequest,
    ) -> ExperimentalMiniRuntimeResponse:
        if not experimental_dag_task_runtime_enabled():
            return ExperimentalMiniRuntimeResponse(ok=False, status="disabled", enabled=False, swarm_id=swarm_id, task_id=task_id, errors=[{"error": f"Set OPENSWARM_EXPERIMENTAL_MINI_RUNTIME=1 and {EXPERIMENTAL_DAG_TASK_RUNTIME_FLAG}=1 to enable"}])

        swarm = self.store.load(swarm_id)
        task = self._find_task(swarm.tasks, task_id)
        contract = self._find_or_create_contract(swarm.contracts, task)
        allowed_tools = self._resolve_allowed_tools(body.allowed_tools, contract)
        contract.allowed_tools = allowed_tools
        contract.provider = "ollama"
        contract.model = self._normalize_model(body.model)
        workspace = self._resolve_workspace(body.workspace_path or swarm.workspace_path, swarm_id=swarm_id)

        adapter = self.adapter_factory(base_url=body.base_url, allow_network=True)
        health = adapter.healthcheck(timeout_seconds=2.0)
        if not health.get("ok"):
            return ExperimentalMiniRuntimeResponse(ok=False, status="provider_unavailable", enabled=True, swarm_id=swarm_id, task_id=task_id, workspace_path=str(workspace), errors=[{"error": "Ollama is not available", "detail": health}])

        self._mark_task_running(swarm_id, task_id)
        result = await self.runtime.run_agent_task(MiniAgentRuntimeContext(
            contract=contract,
            task=task,
            provider=adapter,
            workspace_path=str(workspace),
            model=contract.model or self._normalize_model(body.model),
            provider_tool_format="ollama",
            swarm_id=swarm_id,
            store=self.store,
            max_turns=max(1, min(body.max_turns, 16)),
            inputs={"swarm_id": swarm_id, "task_id": task_id, "user_prompt": swarm.user_prompt},
        ))
        if result.persisted:
            self._record_artifacts_and_messages(swarm_id=swarm_id, task_id=task_id, contract=contract, result=result, workspace=workspace)
        return self._response(result, swarm_id=swarm_id, workspace_path=str(workspace))

    @staticmethod
    def _find_task(tasks: list[TaskNode], task_id: str) -> TaskNode:
        for task in tasks:
            if task.id == task_id:
                return task
        raise FileNotFoundError(f"Task not found: {task_id}")

    @staticmethod
    def _find_or_create_contract(contracts: list[AgentContract], task: TaskNode) -> AgentContract:
        if task.assigned_contract_id:
            for contract in contracts:
                if contract.id == task.assigned_contract_id:
                    return contract
        create_readme_spec = get_experimental_task_spec("create_readme")
        return AgentContract(
            role="DocumentationAgent",
            objective=f"Execute task: {task.title}",
            allowed_tools=list(create_readme_spec.allowed_tools),
            acceptance_criteria=[task.objective],
            output_contract=dict(create_readme_spec.output_contract),
        )

    @staticmethod
    def _resolve_allowed_tools(requested: list[str] | None, contract: AgentContract) -> list[str]:
        source = requested if requested is not None else contract.allowed_tools
        if not source:
            source = ["Read", "Write", "Edit", "SearchFiles", "SearchText"]
        result: list[str] = []
        aliases = {"Glob": "SearchFiles", "Grep": "SearchText"}
        for tool in source:
            normalized = aliases.get(tool, tool)
            if normalized not in ALLOWED_EXPERIMENTAL_TOOLS:
                raise ValueError(f"Tool not allowed in experimental DAG task runtime: {tool}")
            if normalized not in result:
                result.append(normalized)
        return result

    def _resolve_workspace(self, workspace_path: str | None, *, swarm_id: str) -> Path:
        if workspace_path:
            workspace = Path(workspace_path).expanduser().resolve()
        else:
            workspace = (self.store._path(swarm_id).parent / "dag_task_workspace").resolve()
        workspace.mkdir(parents=True, exist_ok=True)
        return workspace

    @staticmethod
    def _normalize_model(model: str) -> str:
        clean = str(model or "").strip()
        if not clean:
            raise ValueError("model is required")
        return clean if clean.startswith("ollama/") else f"ollama/{clean}"

    def _mark_task_running(self, swarm_id: str, task_id: str) -> None:
        swarm = self.store.load(swarm_id)
        for task in swarm.tasks:
            if task.id == task_id:
                task.status = "running"
                task.updated_at = _now_iso()
                break
        self.store.save(swarm)

    def _record_artifacts_and_messages(
        self,
        *,
        swarm_id: str,
        task_id: str,
        contract: AgentContract,
        result: MiniAgentRuntimeResult,
        workspace: Path,
    ) -> None:
        swarm = self.store.load(swarm_id)
        task = self._find_task(swarm.tasks, task_id)
        artifacts = self._dedupe_artifacts(self._artifacts_from_tool_history(task_id=task_id, contract=contract, result=result, workspace=workspace))
        if not artifacts:
            self.store.save(swarm)
            return

        for artifact in artifacts:
            self._upsert_artifact(swarm, task, artifact)
            self._append_message_once(
                swarm,
                AgentToAgentMessage(
                    type="submit_artifact",
                    from_agent_id=contract.id,
                    task_id=task_id,
                    payload=artifact,
                    artifact_refs=[artifact["id"], artifact["path"]],
                ),
            )

        review_task = self._find_review_task_for_artifacts(swarm, task_id)
        reviewer = self._contract_for_task(swarm, review_task) if review_task else None
        coordinator_id = swarm.coordinator_contract_id or contract.id
        if review_task and reviewer:
            artifact_refs = [artifact["id"] for artifact in artifacts]
            self._append_message_once(
                swarm,
                AgentToAgentMessage(
                    type="request_review",
                    from_agent_id=coordinator_id,
                    to_agent_id=reviewer.id,
                    task_id=review_task.id,
                    artifact_refs=artifact_refs,
                    payload={"source_task_id": task_id, "artifact_refs": artifact_refs},
                    requires_response=True,
                ),
            )

        self.store.save(swarm)

    @staticmethod
    def _dedupe_artifacts(artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_key: dict[tuple[str | None, str | None], dict[str, Any]] = {}
        for artifact in artifacts:
            by_key[(artifact.get("task_id"), artifact.get("path"))] = artifact
        return list(by_key.values())

    @staticmethod
    def _artifacts_from_tool_history(
        *,
        task_id: str,
        contract: AgentContract,
        result: MiniAgentRuntimeResult,
        workspace: Path,
    ) -> list[dict[str, Any]]:
        artifacts: list[dict[str, Any]] = []
        for entry in result.tool_history:
            if not entry.get("ok") or entry.get("tool") not in {"Write", "Edit"}:
                continue
            data = entry.get("result") or {}
            path = data.get("path")
            if not path:
                continue
            normalized_path = str(path).replace("\\", "/")
            suffix = Path(str(path)).suffix.lower().lstrip(".")
            artifacts.append(
                {
                    "id": f"artifact-{task_id}-{normalized_path.replace('/', '__')}",
                    "kind": "documentation" if str(path).lower().endswith((".md", ".markdown")) else "file",
                    "file_type": suffix or "file",
                    "path": normalized_path,
                    "absolute_path": data.get("absolute_path") or str((workspace / str(path)).resolve()),
                    "bytes": data.get("bytes"),
                    "status": "created" if entry.get("tool") == "Write" else "updated",
                    "task_id": task_id,
                    "agent_id": contract.id,
                    "agent_role": contract.role,
                    "evidence_ref": entry.get("call_id"),
                    "created_at": _now_iso(),
                }
            )
        return artifacts

    @staticmethod
    def _upsert_artifact(swarm: SwarmState, task: TaskNode, artifact: dict[str, Any]) -> None:
        def same(existing: dict[str, Any]) -> bool:
            return existing.get("id") == artifact.get("id") or (
                existing.get("task_id") == artifact.get("task_id") and existing.get("path") == artifact.get("path")
            )

        swarm.artifacts = [existing for existing in swarm.artifacts if not same(existing)]
        task.artifacts = [existing for existing in task.artifacts if not same(existing)]
        swarm.artifacts.append(artifact)
        task.artifacts.append(artifact)
        if artifact["path"] not in task.touched_files:
            task.touched_files.append(artifact["path"])

    @staticmethod
    def _append_message_once(swarm: SwarmState, message: AgentToAgentMessage) -> None:
        for existing in swarm.messages:
            if (
                existing.type == message.type
                and existing.from_agent_id == message.from_agent_id
                and existing.to_agent_id == message.to_agent_id
                and existing.task_id == message.task_id
                and set(existing.artifact_refs) == set(message.artifact_refs)
            ):
                return
        swarm.messages.append(message)

    @staticmethod
    def _find_review_task_for_artifacts(swarm: SwarmState, source_task_id: str) -> TaskNode | None:
        for task in swarm.tasks:
            if source_task_id not in task.depends_on:
                continue
            try:
                if classify_experimental_task(task) == "review_readme":
                    return task
            except ValueError:
                continue
        return None

    @staticmethod
    def _contract_for_task(swarm: SwarmState, task: TaskNode | None) -> AgentContract | None:
        if not task or not task.assigned_contract_id:
            return None
        for contract in swarm.contracts:
            if contract.id == task.assigned_contract_id:
                return contract
        return None

    @staticmethod
    def _response(result: MiniAgentRuntimeResult, *, swarm_id: str, workspace_path: str) -> ExperimentalMiniRuntimeResponse:
        return ExperimentalMiniRuntimeResponse(
            ok=result.status == "completed",
            status=result.status,
            enabled=True,
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


experimental_dag_task_runner = ExperimentalDAGTaskRunner()
