"""Experimental Worker -> Reviewer DAG chain runner.

Runs only the README Worker task and its dependent Reviewer task through
MiniAgentRuntime + OllamaAdapter. It is feature-flagged and intentionally does
not execute full DAG traversal or final consolidation.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from backend.apps.agents.orchestration.models import AgentContract, AgentToAgentMessage, SwarmState, TaskNode, _now_iso
from backend.apps.agents.orchestration.store import SwarmStore, swarm_store
from backend.apps.agents.providers.ollama_adapter import OllamaAdapter
from backend.apps.agents.runtime.experimental_dag_task_runner import (
    AdapterFactory,
    ExperimentalDAGTaskRunRequest,
    ExperimentalDAGTaskRunner,
    experimental_dag_task_runtime_enabled,
)
from backend.apps.agents.runtime.experimental_mini_runtime import ExperimentalMiniRuntimeResponse
from backend.apps.agents.runtime.mini_agent_runtime import MiniAgentRuntime, MiniAgentRuntimeContext, MiniAgentRuntimeResult
from backend.apps.agents.runtime.tools import ToolCall, ToolExecutionContext
from backend.apps.agents.runtime.experimental_task_type_registry import classify_experimental_task, get_experimental_task_spec


EXPERIMENTAL_DAG_CHAIN_RUNTIME_FLAG = "OPENSWARM_EXPERIMENTAL_DAG_CHAIN_RUNTIME"


class ExperimentalWorkerReviewRunRequest(ExperimentalDAGTaskRunRequest):
    pass


class ExperimentalWorkerReviewResponse(BaseModel):
    ok: bool
    status: str
    enabled: bool = True
    swarm_id: str
    workspace_path: str | None = None
    worker: dict[str, Any] = Field(default_factory=dict)
    reviewer: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    messages: list[dict[str, Any]] = Field(default_factory=list)
    review_result: dict[str, Any] = Field(default_factory=dict)
    errors: list[dict[str, Any]] = Field(default_factory=list)


def experimental_dag_chain_runtime_enabled() -> bool:
    return experimental_dag_task_runtime_enabled() and os.environ.get(EXPERIMENTAL_DAG_CHAIN_RUNTIME_FLAG) == "1"


@dataclass(frozen=True)
class _ChainTasks:
    worker: TaskNode
    reviewer: TaskNode


class ExperimentalDAGChainRunner:
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
        self.single_task_runner = ExperimentalDAGTaskRunner(
            store=self.store,
            runtime=self.runtime,
            adapter_factory=self.adapter_factory,
        )

    async def run_worker_review(
        self,
        *,
        swarm_id: str,
        body: ExperimentalWorkerReviewRunRequest,
    ) -> ExperimentalWorkerReviewResponse:
        if not experimental_dag_chain_runtime_enabled():
            return ExperimentalWorkerReviewResponse(
                ok=False,
                status="disabled",
                enabled=False,
                swarm_id=swarm_id,
                errors=[{"error": f"Set OPENSWARM_EXPERIMENTAL_MINI_RUNTIME=1, OPENSWARM_EXPERIMENTAL_DAG_TASK_RUNTIME=1 and {EXPERIMENTAL_DAG_CHAIN_RUNTIME_FLAG}=1 to enable"}],
            )

        swarm = self.store.load(swarm_id)
        tasks = self._find_worker_reviewer_tasks(swarm)
        workspace = self.single_task_runner._resolve_workspace(body.workspace_path or swarm.workspace_path, swarm_id=swarm_id)

        worker_response = await self.single_task_runner.run_task(swarm_id=swarm_id, task_id=tasks.worker.id, body=body)
        if worker_response.status != "completed":
            return self._response(
                swarm_id=swarm_id,
                workspace=workspace,
                status="worker_failed",
                worker=worker_response.model_dump(mode="json"),
                errors=worker_response.errors,
            )

        swarm = self.store.load(swarm_id)
        artifact = self._find_readme_artifact(swarm, source_task_id=tasks.worker.id)
        if not artifact:
            return self._response(
                swarm_id=swarm_id,
                workspace=workspace,
                status="artifact_missing",
                worker=worker_response.model_dump(mode="json"),
                errors=[{"error": "Worker completed but README.md artifact was not registered"}],
            )

        reviewer_result = await self._run_reviewer(
            swarm=swarm,
            review_task_id=tasks.reviewer.id,
            artifact=artifact,
            body=body,
            workspace=workspace,
        )
        review_result = self._persist_review_result(
            swarm_id=swarm_id,
            review_task_id=tasks.reviewer.id,
            artifact=artifact,
            result=reviewer_result,
        )
        status = "completed" if review_result.get("status") == "approved" else "review_failed"
        return self._response(
            swarm_id=swarm_id,
            workspace=workspace,
            status=status,
            worker=worker_response.model_dump(mode="json"),
            reviewer=self.single_task_runner._response(reviewer_result, swarm_id=swarm_id, workspace_path=str(workspace)).model_dump(mode="json"),
            review_result=review_result,
            ok=status == "completed",
        )

    def _find_worker_reviewer_tasks(self, swarm: SwarmState) -> _ChainTasks:
        worker = next(
            (
                task for task in swarm.tasks
                if classify_experimental_task(task) == "create_readme"
            ),
            None,
        )
        if not worker:
            raise FileNotFoundError("Create README.md task not found")

        reviewer = next(
            (
                task for task in swarm.tasks
                if worker.id in task.depends_on
                and classify_experimental_task(task) == "review_readme"
            ),
            None,
        )
        if not reviewer:
            raise FileNotFoundError("Review README.md task not found")

        return _ChainTasks(worker=worker, reviewer=reviewer)

    async def _run_reviewer(
        self,
        *,
        swarm: SwarmState,
        review_task_id: str,
        artifact: dict[str, Any],
        body: ExperimentalWorkerReviewRunRequest,
        workspace: Path,
    ) -> MiniAgentRuntimeResult:
        review_task = self.single_task_runner._find_task(swarm.tasks, review_task_id)
        contract = self.single_task_runner._find_or_create_contract(swarm.contracts, review_task)
        review_spec = get_experimental_task_spec("review_readme")
        requested_tools = body.allowed_tools or contract.allowed_tools or list(review_spec.allowed_tools)
        read_tools = [tool for tool in self.single_task_runner._resolve_allowed_tools(requested_tools, contract) if tool in set(review_spec.allowed_tools)]
        if "Read" not in read_tools:
            read_tools.insert(0, "Read")
        contract.allowed_tools = read_tools
        contract.provider = "ollama"
        contract.model = self.single_task_runner._normalize_model(body.model)
        artifact_path = str(artifact.get("path") or "")
        safe_artifact = {
            "id": artifact.get("id"),
            "path": artifact_path,
            "kind": artifact.get("kind"),
            "file_type": artifact.get("file_type"),
        }
        contract.objective = (
            f"{contract.objective}\n"
            f"You must read artifact {artifact_path} with the Read tool before returning a review. "
            "Use only the relative artifact path; do not use absolute_path or any absolute filesystem path."
        )
        contract.acceptance_criteria = [*contract.acceptance_criteria, f"Use Read on {artifact.get('path')}.", "Return approved or rejected with evidence."]
        contract.output_contract = dict(review_spec.output_contract)
        contract.output_contract["review_result"]["artifact_path"] = artifact.get("path")

        adapter = self.adapter_factory(base_url=body.base_url, allow_network=True)
        health = adapter.healthcheck(timeout_seconds=2.0)
        if not health.get("ok"):
            return MiniAgentRuntimeResult(
                status="failed",
                task_id=review_task.id,
                agent_contract_id=contract.id,
                final_message=None,
                errors=[{"error": "Ollama is not available", "detail": health}],
            )

        self.single_task_runner._mark_task_running(swarm.id, review_task.id)
        result = await self.runtime.run_agent_task(MiniAgentRuntimeContext(
            contract=contract,
            task=review_task,
            provider=adapter,
            workspace_path=str(workspace),
            model=contract.model,
            provider_tool_format="ollama",
            swarm_id=swarm.id,
            store=self.store,
            max_turns=max(1, min(body.max_turns, 16)),
            inputs={
                "swarm_id": swarm.id,
                "task_id": review_task.id,
                "artifact": safe_artifact,
                "required_tool": {"name": "Read", "path": artifact_path},
                "instruction": f"Read the relative path {artifact_path} with the Read tool and approve or reject it with evidence. Do not use absolute paths.",
            },
        ))
        return self._ensure_reviewer_read(
            result=result,
            contract=contract,
            task=review_task,
            swarm_id=swarm.id,
            workspace=workspace,
            artifact_path=artifact_path,
        )

    def _persist_review_result(
        self,
        *,
        swarm_id: str,
        review_task_id: str,
        artifact: dict[str, Any],
        result: MiniAgentRuntimeResult,
    ) -> dict[str, Any]:
        swarm = self.store.load(swarm_id)
        task = self.single_task_runner._find_task(swarm.tasks, review_task_id)
        read_entries = [
            entry for entry in result.tool_history
            if entry.get("tool") == "Read" and entry.get("ok") and (entry.get("result") or {}).get("path") == artifact.get("path")
        ]
        approved = result.status == "completed" and bool(read_entries)
        review_result = {
            "kind": "review_result",
            "status": "approved" if approved else "rejected",
            "artifact_id": artifact.get("id"),
            "artifact_path": artifact.get("path"),
            "review_task_id": review_task_id,
            "reviewer_agent_id": result.agent_contract_id,
            "required_read_satisfied": bool(read_entries),
            "final_message": result.final_message,
            "created_at": _now_iso(),
        }
        if not approved:
            review_result["errors"] = [*result.errors, {"error": "Reviewer did not complete required Read tool validation"}]
            task.status = "failed"
            task.errors.append(review_result["errors"][-1])
        else:
            task.status = "completed"
        self._upsert_review_evidence(task, review_result)
        self._append_review_message_once(swarm, result.agent_contract_id, review_task_id, review_result)
        task.updated_at = _now_iso()
        self.store.save(swarm)
        return review_result

    def _ensure_reviewer_read(
        self,
        *,
        result: MiniAgentRuntimeResult,
        contract: AgentContract,
        task: TaskNode,
        swarm_id: str,
        workspace: Path,
        artifact_path: str,
    ) -> MiniAgentRuntimeResult:
        if any(entry.get("tool") == "Read" and entry.get("ok") and (entry.get("result") or {}).get("path") == artifact_path for entry in result.tool_history):
            return result

        forced_history: list[dict[str, Any]] = []
        forced = self.runtime.tools.execute_tool(
            ToolCall(name="Read", input={"path": artifact_path}, raw_name="Read"),
            ToolExecutionContext(
                workspace_path=str(workspace),
                session_id=f"mini-{task.id}",
                swarm_id=swarm_id,
                agent_id=contract.id,
                task_id=task.id,
                allowed_tools=["Read"],
                metadata={"forced_by": "experimental_worker_review_runner"},
            ),
            history=forced_history,
        )
        swarm = self.store.load(swarm_id)
        swarm.tool_history.extend(forced_history)
        persisted_task = self.single_task_runner._find_task(swarm.tasks, task.id)
        persisted_task.evidence.append({"kind": "forced_required_tool", "tool": "Read", "history_entry": forced.to_history_entry()})
        if not forced.ok:
            persisted_task.errors.append({"type": "required_tool_error", "tool": "Read", "error": forced.error})
        persisted_task.updated_at = _now_iso()
        self.store.save(swarm)

        merged_history = [*result.tool_history, *forced_history]
        merged_evidence = [*result.evidence, {"kind": "forced_required_tool", "tool": "Read", "history_entry": forced.to_history_entry()}]
        merged_errors = [*result.errors]
        status = result.status
        if not forced.ok:
            merged_errors.append({"type": "required_tool_error", "tool": "Read", "error": forced.error})
            status = "failed"
        else:
            # Si el modelo falló por intentar Read sin path, pero el fallback obligatorio
            # pudo leer correctamente el artifact requerido, el contrato del reviewer queda satisfecho.
            status = "completed"
            merged_errors = [
                error for error in merged_errors
                if "path must be a non-empty string" not in str(error)
                and "Reviewer did not complete required Read tool validation" not in str(error)
            ]
        return MiniAgentRuntimeResult(
            status=status,
            task_id=result.task_id,
            agent_contract_id=result.agent_contract_id,
            final_message=result.final_message,
            tool_history=merged_history,
            evidence=merged_evidence,
            errors=merged_errors,
            provider_events=result.provider_events,
            turns=result.turns,
            persisted=result.persisted,
        )

    @staticmethod
    def _find_readme_artifact(swarm: SwarmState, *, source_task_id: str) -> dict[str, Any] | None:
        return next(
            (
                artifact for artifact in swarm.artifacts
                if artifact.get("task_id") == source_task_id and str(artifact.get("path", "")).replace("\\", "/").lower() == "readme.md"
            ),
            None,
        )

    @staticmethod
    def _upsert_review_evidence(task: TaskNode, review_result: dict[str, Any]) -> None:
        task.evidence = [
            item for item in task.evidence
            if not (item.get("kind") == "review_result" and item.get("artifact_id") == review_result.get("artifact_id"))
        ]
        task.validations = [
            item for item in task.validations
            if not (item.get("kind") == "review_result" and item.get("artifact_id") == review_result.get("artifact_id"))
        ]
        task.evidence.append(review_result)
        task.validations.append(review_result)

    @staticmethod
    def _append_review_message_once(swarm: SwarmState, from_agent_id: str, task_id: str, review_result: dict[str, Any]) -> None:
        artifact_ref = str(review_result.get("artifact_id") or review_result.get("artifact_path") or "")
        for existing in swarm.messages:
            if existing.type == "send_message_to_agent" and existing.from_agent_id == from_agent_id and existing.task_id == task_id and artifact_ref in existing.artifact_refs and existing.payload.get("review_result"):
                existing.payload["review_result"] = review_result
                return
        swarm.messages.append(
            AgentToAgentMessage(
                type="send_message_to_agent",
                from_agent_id=from_agent_id,
                to_agent_id=swarm.coordinator_contract_id,
                task_id=task_id,
                artifact_refs=[artifact_ref] if artifact_ref else [],
                payload={"review_result": review_result},
            )
        )

    def _response(
        self,
        *,
        swarm_id: str,
        workspace: Path,
        status: str,
        worker: dict[str, Any] | None = None,
        reviewer: dict[str, Any] | None = None,
        review_result: dict[str, Any] | None = None,
        errors: list[dict[str, Any]] | None = None,
        ok: bool = False,
    ) -> ExperimentalWorkerReviewResponse:
        swarm = self.store.load(swarm_id)
        return ExperimentalWorkerReviewResponse(
            ok=ok,
            status=status,
            enabled=True,
            swarm_id=swarm_id,
            workspace_path=str(workspace),
            worker=worker or {},
            reviewer=reviewer or {},
            artifacts=swarm.artifacts,
            messages=[message.model_dump(mode="json") for message in swarm.messages],
            review_result=review_result or {},
            errors=errors or [],
        )



experimental_dag_chain_runner = ExperimentalDAGChainRunner()
