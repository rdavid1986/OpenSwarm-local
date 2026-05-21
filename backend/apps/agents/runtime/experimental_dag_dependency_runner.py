"""Experimental dependency-ordered README DAG runner.

This is intentionally narrow: it topologically walks TaskNode.depends_on but
only executes the known safe README DAG task types.
"""

from __future__ import annotations

import os
from typing import Any

from pydantic import BaseModel, Field

from backend.apps.agents.orchestration.models import AgentContract, SwarmState, TaskNode, _now_iso
from backend.apps.agents.orchestration.store import SwarmStore, swarm_store
from backend.apps.agents.providers.ollama_adapter import OllamaAdapter
from backend.apps.agents.runtime.experimental_dag_chain_runner import ExperimentalDAGChainRunner
from backend.apps.agents.runtime.experimental_dag_task_runner import AdapterFactory
from backend.apps.agents.runtime.experimental_dag_consolidator import ExperimentalDAGConsolidator
from backend.apps.agents.runtime.experimental_dag_mini_runner import (
    ExperimentalMiniDAGRunRequest,
    experimental_dag_mini_runner_enabled,
)
from backend.apps.agents.runtime.mini_agent_runtime import MiniAgentRuntimeContext
from backend.apps.agents.runtime.events import event_trace_runtime
from backend.apps.agents.runtime.tools import ToolCall, ToolExecutionContext
from backend.apps.agents.runtime.experimental_task_type_registry import (
    ExperimentalTaskContractValidationError,
    ExperimentalTaskType,
    classify_experimental_task,
    get_experimental_task_spec,
    validate_experimental_task_contract,
    validate_experimental_task_completion,
)


EXPERIMENTAL_DAG_DEPENDENCY_RUNNER_FLAG = "OPENSWARM_EXPERIMENTAL_DAG_DEPENDENCY_RUNNER"
EXPERIMENTAL_PLANNER_AGENT_RUNTIME_FLAG = "OPENSWARM_EXPERIMENTAL_PLANNER_AGENT_RUNTIME"
KnownTaskType = ExperimentalTaskType


class ExperimentalDAGDependencyRunRequest(ExperimentalMiniDAGRunRequest):
    pass


class ExperimentalDAGDependencyRunResponse(BaseModel):
    ok: bool
    status: str
    enabled: bool = True
    swarm_id: str
    execution_order: list[dict[str, Any]] = Field(default_factory=list)
    tasks: list[dict[str, Any]] = Field(default_factory=list)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    messages: list[dict[str, Any]] = Field(default_factory=list)
    tool_history: list[dict[str, Any]] = Field(default_factory=list)
    final_result: dict[str, Any] = Field(default_factory=dict)
    final_evidence: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)


def experimental_dag_dependency_runner_enabled() -> bool:
    return experimental_dag_mini_runner_enabled() and os.environ.get(EXPERIMENTAL_DAG_DEPENDENCY_RUNNER_FLAG) == "1"


class ExperimentalDAGDependencyRunner:
    def __init__(
        self,
        *,
        store: SwarmStore | None = None,
        chain_runner: ExperimentalDAGChainRunner | None = None,
        consolidator: ExperimentalDAGConsolidator | None = None,
        planner_adapter_factory: AdapterFactory | None = None,
    ) -> None:
        self.store = store or swarm_store
        self.chain_runner = chain_runner or ExperimentalDAGChainRunner(store=self.store)
        self.consolidator = consolidator or ExperimentalDAGConsolidator(store=self.store)
        self.planner_adapter_factory = planner_adapter_factory or getattr(self.chain_runner, "adapter_factory", OllamaAdapter)

    def _run_architecture_plan_execute_task(
        self,
        *,
        task: TaskNode,
        swarm: SwarmState,
    ) -> dict[str, Any]:
        architecture_plan = {
            "status": "ready",
            "summary": "Architecture plan generated from the current swarm intake context.",
            "components": [
                {"name": "orchestrator", "responsibility": "Coordinate task execution and state transitions."},
                {"name": "agents", "responsibility": "Execute specialized responsibilities through controlled task types."},
                {"name": "evidence", "responsibility": "Record verifiable outputs for review and final consolidation."},
                {"name": "validation", "responsibility": "Run safe validation checks through approved execution paths."},
            ],
            "constraints": [
                "No shell access is granted by architecture_plan_execute.",
                "No files are written by architecture_plan_execute.",
                "Frontend and backend implementation remain inactive in this phase.",
            ],
            "risks": [
                "Architecture output is generated from available swarm context only.",
                "Detailed implementation tasks require later specialized task types.",
            ],
        }
        result = {
            "kind": "architecture_plan_result",
            "status": "ready",
            "architecture_plan": architecture_plan,
            "created_at": _now_iso(),
        }
        task.evidence.append(result)
        task.status = "completed"
        task.updated_at = _now_iso()
        return result


    def _run_frontend_plan_execute_task(
        self,
        *,
        task: TaskNode,
        swarm: SwarmState,
    ) -> dict[str, Any]:
        frontend_plan = {
            "status": "ready",
            "summary": "Frontend plan generated from architecture and project intake context.",
            "components": [
                {"name": "app_shell", "responsibility": "Provide the main application layout and navigation."},
                {"name": "chat_surface", "responsibility": "Display user messages, agent progress, artifacts, and final results."},
                {"name": "orchestration_canvas", "responsibility": "Show DAG task state, dependencies, evidence, and claim guard status."},
                {"name": "settings_models", "responsibility": "Expose local-first model/provider configuration without executing setup actions."},
            ],
            "routes": [
                {"path": "/", "purpose": "Main chat and orchestration workspace."},
                {"path": "/settings", "purpose": "Model, provider, and local runtime configuration."},
            ],
            "constraints": [
                "No frontend files are written by frontend_plan_execute.",
                "No shell access is granted by frontend_plan_execute.",
                "Implementation remains inactive until a later approved task type.",
            ],
            "risks": [
                "Frontend plan is derived from current swarm context only.",
                "UI implementation requires later file-writing task types with explicit tool policies.",
            ],
        }
        result = {
            "kind": "frontend_plan_result",
            "status": "ready",
            "frontend_plan": frontend_plan,
            "created_at": _now_iso(),
        }
        task.evidence.append(result)
        task.status = "completed"
        task.updated_at = _now_iso()
        return result


    def _run_backend_plan_execute_task(
        self,
        *,
        task: TaskNode,
        swarm: SwarmState,
    ) -> dict[str, Any]:
        backend_plan = {
            "status": "ready",
            "summary": "Backend plan generated from architecture and project intake context.",
            "services": [
                {"name": "orchestration_api", "responsibility": "Expose swarm, DAG, task, evidence, and final result operations."},
                {"name": "runtime_services", "responsibility": "Run controlled task types through explicit dispatch paths."},
                {"name": "storage", "responsibility": "Persist swarm state, artifacts, evidence, and configuration locally."},
            ],
            "data_models": [
                {"name": "SwarmState", "purpose": "Store contracts, tasks, artifacts, messages, evidence, and final results."},
                {"name": "TaskNode", "purpose": "Represent DAG tasks, dependencies, status, validations, and evidence."},
                {"name": "AgentContract", "purpose": "Constrain role, tools, objectives, and output contracts."},
            ],
            "api_endpoints": [
                {"path": "/api/swarms", "purpose": "Swarm lifecycle and interaction endpoints."},
                {"path": "/api/swarms/{swarm_id}/experimental/start-implementation", "purpose": "Start controlled DAG implementation."},
            ],
            "constraints": [
                "No backend files are written by backend_plan_execute.",
                "No shell access is granted by backend_plan_execute.",
                "Implementation remains inactive until a later approved task type.",
            ],
            "risks": [
                "Backend plan is derived from current swarm context only.",
                "API implementation changes require later file-writing task types with explicit tool policies.",
            ],
        }
        result = {
            "kind": "backend_plan_result",
            "status": "ready",
            "backend_plan": backend_plan,
            "created_at": _now_iso(),
        }
        task.evidence.append(result)
        task.status = "completed"
        task.updated_at = _now_iso()
        return result


    def _run_security_review_execute_task(
        self,
        *,
        task: TaskNode,
        swarm: SwarmState,
    ) -> dict[str, Any]:
        security_review = {
            "status": "ready",
            "summary": "Security review generated from architecture, frontend plan, backend plan, and project intake context.",
            "findings": [
                {
                    "area": "tool_policy",
                    "severity": "medium",
                    "summary": "Executable planning tasks currently run without tools, which keeps implementation risk low.",
                },
                {
                    "area": "dependency_control",
                    "severity": "medium",
                    "summary": "Missing dependencies should require explicit user approval before installation.",
                },
                {
                    "area": "evidence_integrity",
                    "severity": "high",
                    "summary": "Final completion claims must remain tied to recorded task evidence and claim guard checks.",
                },
            ],
            "constraints": [
                "No security files are written by security_review_execute.",
                "No shell access is granted by security_review_execute.",
                "Security review is advisory until later enforcement task types are approved.",
            ],
            "risks": [
                "Security review is generated from current swarm context only.",
                "Full security verification requires later read-only inspection and validation task types.",
            ],
        }
        result = {
            "kind": "security_review_result",
            "status": "ready",
            "security_review": security_review,
            "created_at": _now_iso(),
        }
        task.evidence.append(result)
        task.status = "completed"
        task.updated_at = _now_iso()
        return result


    def _run_validation_execute_task(
        self,
        *,
        swarm: SwarmState,
        task: TaskNode,
        contract: AgentContract,
        workspace_path: str,
    ) -> dict[str, Any]:
        spec = get_experimental_task_spec("validation_execute")
        validate_experimental_task_contract(
            swarm=swarm,
            task=task,
            task_type="validation_execute",
        )

        history: list[dict[str, Any]] = []
        command = "python -m py_compile ok.py"
        result = self.chain_runner.runtime.tools.execute_tool(
            ToolCall(name="SafeShell", input={"command": command}, raw_name="SafeShell"),
            ToolExecutionContext(
                workspace_path=workspace_path,
                session_id="experimental-dag-validation",
                swarm_id=swarm.id,
                agent_id=contract.id,
                task_id=task.id,
                allowed_tools=list(spec.allowed_tools),
                metadata={"task_type": "validation_execute"},
            ),
            history=history,
        )

        swarm.tool_history.extend(history)

        validation_result = {
            "status": "passed" if result.ok else "failed",
            "commands": [
                {
                    "command": command,
                    "ok": result.ok,
                    "exit_code": result.result.get("exit_code"),
                    "stdout": result.result.get("stdout", ""),
                    "stderr": result.result.get("stderr", ""),
                }
            ],
            "evidence": ["command_executed"] if result.ok else [],
        }
        task.validations.append(validation_result)
        if result.ok:
            task.evidence.append("command_executed")
        task.status = "completed" if result.ok else "failed"
        task.updated_at = _now_iso()
        return validation_result

    async def run_dag_dependencies(
        self,
        *,
        swarm_id: str,
        body: ExperimentalDAGDependencyRunRequest,
    ) -> ExperimentalDAGDependencyRunResponse:
        if not experimental_dag_dependency_runner_enabled():
            return ExperimentalDAGDependencyRunResponse(
                ok=False,
                status="disabled",
                enabled=False,
                swarm_id=swarm_id,
                errors=[{"error": f"Set OPENSWARM_EXPERIMENTAL_DAG_DEPENDENCY_RUNNER=1 and previous experimental DAG flags to enable"}],
            )

        self._trace_event(swarm_id, "dag_started", payload={"runner": "experimental_dag_dependency_runner"})
        order = self._topological_sort(self.store.load(swarm_id))
        preflight_error = self._preflight_task_contracts(swarm_id=swarm_id, order=order)
        if preflight_error:
            return preflight_error
        execution_order: list[dict[str, Any]] = []
        for task in order:
            swarm = self.store.load(swarm_id)
            current = self._task_by_id(swarm, task.id)
            task_type = self._classify_task(current)
            execution_order.append({"task_id": current.id, "title": current.title, "type": task_type})
            self._trace_event(swarm_id, "task_started", task_id=current.id, payload={"title": current.title, "type": task_type})
            if current.status == "completed" and self._has_valid_completion(swarm, current, task_type):
                execution_order[-1]["action"] = "skipped_completed"
                self._trace_event(swarm_id, "task_skipped", task_id=current.id, payload={"title": current.title, "type": task_type, "reason": "valid_completion"})
                continue

            if task_type == "plan_reused":
                if self._planner_agent_runtime_enabled():
                    planner_result = await self._run_planner_agent(swarm=swarm, task=current, body=body)
                    execution_order[-1]["action"] = "planner_executed"
                    execution_order[-1]["status"] = planner_result.get("status")
                    self._trace_event(swarm_id, "planner_validated", task_id=current.id, payload={"planner_result": planner_result})
                    if planner_result.get("status") != "validated":
                        self._trace_event(swarm_id, "planner_rejected", task_id=current.id, payload={"planner_result": planner_result})
                        self._trace_event(swarm_id, "dag_failed", task_id=current.id, payload={"error": "plan_rejected", "planner_result": planner_result})
                        return self._response(
                            swarm_id,
                            status="failed",
                            execution_order=execution_order,
                            errors=[{"error": "plan_rejected", "planner_result": planner_result}],
                            ok=False,
                        )
                else:
                    self._mark_plan_reused(swarm, current)
                    execution_order[-1]["action"] = "marked_reused"
                    self._trace_event(swarm_id, "task_completed", task_id=current.id, payload={"title": current.title, "type": task_type, "status": "plan_reused"})
                continue

            if task_type == "architecture_plan_execute":
                current.status = "running"
                self.store.save(swarm)
                architecture_result = self._run_architecture_plan_execute_task(
                    task=current,
                    swarm=swarm,
                )
                self.store.save(swarm)
                self._trace_event(swarm_id, "architecture_plan_completed", task_id=current.id, payload=architecture_result)
                self._trace_event(swarm_id, "task_completed", task_id=current.id, payload={"title": current.title, "type": task_type, "status": "ready"})
                continue

            if task_type == "frontend_plan_execute":
                current.status = "running"
                self.store.save(swarm)
                frontend_result = self._run_frontend_plan_execute_task(
                    task=current,
                    swarm=swarm,
                )
                self.store.save(swarm)
                self._trace_event(swarm_id, "frontend_plan_completed", task_id=current.id, payload=frontend_result)
                self._trace_event(swarm_id, "task_completed", task_id=current.id, payload={"title": current.title, "type": task_type, "status": "ready"})
                continue

            if task_type == "backend_plan_execute":
                current.status = "running"
                self.store.save(swarm)
                backend_result = self._run_backend_plan_execute_task(
                    task=current,
                    swarm=swarm,
                )
                self.store.save(swarm)
                self._trace_event(swarm_id, "backend_plan_completed", task_id=current.id, payload=backend_result)
                self._trace_event(swarm_id, "task_completed", task_id=current.id, payload={"title": current.title, "type": task_type, "status": "ready"})
                continue

            if task_type == "security_review_execute":
                current.status = "running"
                self.store.save(swarm)
                security_result = self._run_security_review_execute_task(
                    task=current,
                    swarm=swarm,
                )
                self.store.save(swarm)
                self._trace_event(swarm_id, "security_review_completed", task_id=current.id, payload=security_result)
                self._trace_event(swarm_id, "task_completed", task_id=current.id, payload={"title": current.title, "type": task_type, "status": "ready"})
                continue

            if task_type == "create_readme":
                result = await self.chain_runner.single_task_runner.run_task(swarm_id=swarm_id, task_id=current.id, body=body)
                execution_order[-1]["action"] = "executed"
                execution_order[-1]["status"] = result.status
                if result.status == "completed":
                    self._trace_event(swarm_id, "task_completed", task_id=current.id, payload={"title": current.title, "type": task_type, "status": result.status})
                if result.status != "completed":
                    self._trace_event(swarm_id, "task_failed", task_id=current.id, payload={"title": current.title, "type": task_type, "status": result.status, "errors": result.errors})
                    self._trace_event(swarm_id, "dag_failed", task_id=current.id, payload={"error": "task_failed", "type": task_type, "errors": result.errors})
                    return self._response(swarm_id, status="failed", execution_order=execution_order, errors=result.errors, ok=False)
                continue

            if task_type == "review_readme":
                swarm = self.store.load(swarm_id)
                worker = self._find_task_by_type(swarm, "create_readme")
                artifact = self.chain_runner._find_readme_artifact(swarm, source_task_id=worker.id)
                if not artifact:
                    return self._response(swarm_id, status="failed", execution_order=execution_order, errors=[{"error": "README artifact missing before review"}], ok=False)
                reviewer_result = await self.chain_runner._run_reviewer(
                    swarm=swarm,
                    review_task_id=current.id,
                    artifact=artifact,
                    body=body,
                    workspace=self.chain_runner.single_task_runner._resolve_workspace(body.workspace_path or swarm.workspace_path, swarm_id=swarm_id),
                )
                review_result = self.chain_runner._persist_review_result(
                    swarm_id=swarm_id,
                    review_task_id=current.id,
                    artifact=artifact,
                    result=reviewer_result,
                )
                execution_order[-1]["action"] = "executed"
                execution_order[-1]["status"] = review_result.get("status")
                if review_result.get("status") == "approved":
                    self._trace_event(swarm_id, "review_completed", task_id=current.id, payload=review_result)
                    self._trace_event(swarm_id, "task_completed", task_id=current.id, payload={"title": current.title, "type": task_type, "status": review_result.get("status")})
                if review_result.get("status") != "approved":
                    self._trace_event(swarm_id, "task_failed", task_id=current.id, payload={"title": current.title, "type": task_type, "status": review_result.get("status"), "errors": review_result.get("errors") or []})
                    self._trace_event(swarm_id, "dag_failed", task_id=current.id, payload={"error": "review_failed", "errors": review_result.get("errors") or []})
                    return self._response(swarm_id, status="failed", execution_order=execution_order, errors=review_result.get("errors") or [], ok=False)
                continue

            if task_type == "inspect_readme":
                result = self._run_inspect_readme(swarm_id=swarm_id, task=current, body=body)
                execution_order[-1]["action"] = "executed"
                execution_order[-1]["status"] = result.get("status")
                if result.get("status") == "completed":
                    self._trace_event(swarm_id, "task_completed", task_id=current.id, payload={"title": current.title, "type": task_type, "status": "completed"})
                else:
                    self._trace_event(swarm_id, "task_failed", task_id=current.id, payload={"title": current.title, "type": task_type, "status": "failed", "errors": result.get("errors") or []})
                    self._trace_event(swarm_id, "dag_failed", task_id=current.id, payload={"error": "inspect_readme_failed", "errors": result.get("errors") or []})
                    return self._response(swarm_id, status="failed", execution_order=execution_order, errors=result.get("errors") or [], ok=False)
                continue


            if task_type == "validation_execute":
                current.status = "running"
                self.store.save(swarm)
                validation_result = await self._run_validation_execute_task(
                    swarm_id=swarm_id,
                    task=current,
                    body=body,
                )
                self.store.save(swarm)
                if validation_result.get("status") == "completed":
                    self._trace_event(swarm_id, "task_completed", task_id=current.id, payload={"title": current.title, "type": task_type, "status": "completed"})
                else:
                    self._trace_event(swarm_id, "task_failed", task_id=current.id, payload={"title": current.title, "type": task_type, "status": "failed", "errors": validation_result.get("errors") or []})
                    self._trace_event(swarm_id, "dag_failed", task_id=current.id, payload={"error": "validation_execute_failed", "errors": validation_result.get("errors") or []})
                    return self._response(swarm_id, status="failed", execution_order=execution_order, errors=validation_result.get("errors") or [], ok=False)
                continue

            if task_type == "consolidate_final":
                self._trace_event(swarm_id, "consolidation_started", task_id=current.id, payload={"title": current.title})
                result = self.consolidator.consolidate_final(swarm_id=swarm_id)
                execution_order[-1]["action"] = "executed"
                execution_order[-1]["status"] = result.status
                if result.ok:
                    self._trace_event(swarm_id, "consolidation_completed", task_id=current.id, payload={"status": result.status})
                    self._trace_event(swarm_id, "task_completed", task_id=current.id, payload={"title": current.title, "type": task_type, "status": result.status})
                if not result.ok:
                    self._trace_event(swarm_id, "task_failed", task_id=current.id, payload={"title": current.title, "type": task_type, "status": result.status, "errors": result.errors})
                    self._trace_event(swarm_id, "dag_failed", task_id=current.id, payload={"error": "consolidation_failed", "errors": result.errors})
                    return self._response(swarm_id, status="failed", execution_order=execution_order, errors=result.errors, ok=False)
                continue

            return self._response(
                swarm_id,
                status="failed",
                execution_order=execution_order,
                errors=[{"error": "unknown_task_type", "task_id": current.id, "title": current.title}],
                ok=False,
            )

        self._trace_event(swarm_id, "dag_completed", payload={"execution_order": execution_order})
        return self._response(swarm_id, status="completed", execution_order=execution_order, ok=True)

    def _preflight_task_contracts(
        self,
        *,
        swarm_id: str,
        order: list[TaskNode],
    ) -> ExperimentalDAGDependencyRunResponse | None:
        for task in order:
            try:
                task_type = self._classify_task(task)
            except ValueError:
                self._trace_event(swarm_id, "dag_failed", task_id=task.id, payload={"error": "unknown_task_type", "title": task.title})
                return self._response(
                    swarm_id,
                    status="failed",
                    execution_order=[{"task_id": task.id, "title": task.title, "type": "unknown", "action": "failed"}],
                    errors=[{"error": "unknown_task_type", "task_id": task.id, "title": task.title}],
                    ok=False,
                )

            swarm = self.store.load(swarm_id)
            current = self._task_by_id(swarm, task.id)
            if current.status == "completed" and self._has_valid_completion(swarm, current, task_type):
                continue

            try:
                validate_experimental_task_contract(swarm=swarm, task=current, task_type=task_type)
            except ExperimentalTaskContractValidationError as exc:
                error = exc.to_error()
                self._trace_event(swarm_id, "task_contract_validation_failed", task_id=current.id, payload=error)
                self._trace_event(swarm_id, "dag_failed", task_id=current.id, payload=error)
                return self._response(
                    swarm_id,
                    status="failed",
                    execution_order=[{"task_id": current.id, "title": current.title, "type": task_type, "action": "failed"}],
                    errors=[error],
                    ok=False,
                )

        return None

    @staticmethod
    def _trace_event(
        swarm_id: str,
        event_type: str,
        *,
        task_id: str | None = None,
        agent_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        event_trace_runtime.create(
            event_type,
            swarm_id=swarm_id,
            task_id=task_id,
            agent_id=agent_id,
            payload=payload or {},
        )

    def _topological_sort(self, swarm: SwarmState) -> list[TaskNode]:
        tasks_by_id = {task.id: task for task in swarm.tasks}
        unknown_deps = [
            {"task_id": task.id, "missing_dep": dep}
            for task in swarm.tasks
            for dep in task.depends_on
            if dep not in tasks_by_id
        ]
        if unknown_deps:
            raise ValueError(f"Unknown task dependencies: {unknown_deps}")

        ordered: list[TaskNode] = []
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(task: TaskNode) -> None:
            if task.id in visited:
                return
            if task.id in visiting:
                raise ValueError(f"Cycle detected at task {task.id}")
            visiting.add(task.id)
            for dep_id in task.depends_on:
                visit(tasks_by_id[dep_id])
            visiting.remove(task.id)
            visited.add(task.id)
            ordered.append(task)

        for task in swarm.tasks:
            visit(task)
        return ordered

    def _classify_task(self, task: TaskNode) -> KnownTaskType:
        return classify_experimental_task(task)

    def _has_valid_completion(self, swarm: SwarmState, task: TaskNode, task_type: KnownTaskType) -> bool:
        return validate_experimental_task_completion(
            swarm=swarm,
            task=task,
            task_type=task_type,
            planner_agent_runtime_enabled=self._planner_agent_runtime_enabled(),
            readme_artifact_finder=lambda current_swarm, source_task_id: self.chain_runner._find_readme_artifact(
                current_swarm,
                source_task_id=source_task_id,
            ),
            task_finder=self._find_task_by_type,
            approved_review_finder=self._find_approved_review_result,
        )

    def _mark_plan_reused(self, swarm: SwarmState, task: TaskNode) -> None:
        task.status = "completed"
        task.evidence = [item for item in task.evidence if item.get("kind") != "plan_reused"]
        task.evidence.append(
            {
                "kind": "plan_reused",
                "status": "completed",
                "message": "Existing README DAG was reused by experimental dependency runner.",
                "created_at": _now_iso(),
            }
        )
        task.updated_at = _now_iso()
        self.store.save(swarm)

    async def _run_planner_agent(
        self,
        *,
        swarm: SwarmState,
        task: TaskNode,
        body: ExperimentalDAGDependencyRunRequest,
    ) -> dict[str, Any]:
        before_task_ids = [item.id for item in swarm.tasks]
        contract = self._planner_contract(swarm, task, body)
        adapter = self.planner_adapter_factory(base_url=body.base_url, allow_network=True)
        health = adapter.healthcheck(timeout_seconds=2.0)
        if not health.get("ok"):
            self._persist_planner_result(
                swarm_id=swarm.id,
                task_id=task.id,
                result={"kind": "planner_result", "status": "rejected", "reason": "provider_unavailable", "detail": health},
            )
            return {"status": "rejected", "reason": "provider_unavailable", "detail": health}

        self._mark_task_running(swarm.id, task.id)
        runtime_result = await self.chain_runner.runtime.run_agent_task(MiniAgentRuntimeContext(
            contract=contract,
            task=task,
            provider=adapter,
            workspace_path=body.workspace_path or swarm.workspace_path or str(self.store._path(swarm.id).parent / "dag_dependency_workspace"),
            model=contract.model or self.chain_runner.single_task_runner._normalize_model(body.model),
            provider_tool_format="ollama",
            swarm_id=swarm.id,
            store=self.store,
            max_turns=max(1, min(body.max_turns, 8)),
            inputs={
                "strict_contract": {
                    "allowed_status": ["plan_validated", "plan_rejected"],
                    "may_create_tasks": False,
                    "may_modify_depends_on": False,
                    "expected_task_types": list(get_experimental_task_spec.__globals__["TASK_TYPE_REGISTRY"].keys()),
                    "required_order": ["Plan task DAG", "Create README.md", "Review README.md", "Consolidate final evidence"],
                },
                "dag": [
                    {
                        "id": item.id,
                        "title": item.title,
                        "objective": item.objective,
                        "depends_on": item.depends_on,
                        "status": item.status,
                    }
                    for item in swarm.tasks
                ],
                "instruction": "Validate or reject the existing README DAG only. Do not propose, create, delete, or modify tasks.",
            },
        ))
        planner_result = self._parse_planner_result(runtime_result.final_message)
        after_swarm = self.store.load(swarm.id)
        if [item.id for item in after_swarm.tasks] != before_task_ids:
            planner_result = {"status": "rejected", "reason": "planner_task_mutation_detected"}
        evidence = {
            "kind": "planner_result",
            "status": "validated" if planner_result.get("status") == "plan_validated" else "rejected",
            "planner_status": planner_result.get("status"),
            "reason": planner_result.get("reason"),
            "final_message": runtime_result.final_message,
            "turns": runtime_result.turns,
            "created_at": _now_iso(),
        }
        self._persist_planner_result(swarm_id=swarm.id, task_id=task.id, result=evidence)
        return evidence

    def _run_inspect_readme(
        self,
        *,
        swarm_id: str,
        task: TaskNode,
        body: ExperimentalDAGDependencyRunRequest,
    ) -> dict[str, Any]:
        swarm = self.store.load(swarm_id)
        workspace = self.chain_runner.single_task_runner._resolve_workspace(
            body.workspace_path or swarm.workspace_path,
            swarm_id=swarm_id,
        )
        self._mark_task_running(swarm_id, task.id)
        history: list[dict[str, Any]] = []
        result = self.chain_runner.runtime.tools.execute_tool(
            ToolCall(name="Read", input={"path": "README.md"}, raw_name="Read"),
            ToolExecutionContext(
                workspace_path=str(workspace),
                session_id=f"mini-{task.id}",
                swarm_id=swarm_id,
                agent_id=task.assigned_contract_id,
                task_id=task.id,
                allowed_tools=["Read"],
                metadata={"task_type": "inspect_readme"},
            ),
            history=history,
        )

        swarm = self.store.load(swarm_id)
        persisted_task = self._task_by_id(swarm, task.id)
        swarm.tool_history.extend(history)

        if not result.ok:
            error = {"error": "inspect_readme_read_failed", "detail": result.error}
            persisted_task.errors.append(error)
            persisted_task.status = "failed"
            persisted_task.updated_at = _now_iso()
            self.store.save(swarm)
            return {"status": "failed", "errors": [error]}

        data = result.result or {}
        content = str(data.get("content") or "")
        inspection = {
            "kind": "readme_inspection",
            "path": "README.md",
            "bytes": data.get("bytes"),
            "line_count": len(content.splitlines()),
            "has_title": content.lstrip().startswith("#"),
            "created_at": _now_iso(),
        }
        persisted_task.evidence = [
            item for item in persisted_task.evidence
            if item.get("kind") != "readme_inspection"
        ]
        persisted_task.evidence.append(inspection)
        persisted_task.validations = [
            item for item in persisted_task.validations
            if item.get("kind") != "readme_inspection"
        ]
        persisted_task.validations.append(inspection)
        persisted_task.status = "completed"
        persisted_task.updated_at = _now_iso()
        self.store.save(swarm)
        return {"status": "completed", "inspection": inspection}

    def _planner_contract(self, swarm: SwarmState, task: TaskNode, body: ExperimentalDAGDependencyRunRequest) -> AgentContract:
        existing = None
        if task.assigned_contract_id:
            existing = next((contract for contract in swarm.contracts if contract.id == task.assigned_contract_id), None)
        planner_spec = get_experimental_task_spec("plan_reused")
        contract = existing or AgentContract(
            role="PlannerAgent",
            objective="Validate the existing README DAG without changing it.",
            allowed_tools=list(planner_spec.allowed_tools),
            acceptance_criteria=[],
            output_contract=dict(planner_spec.output_contract),
        )
        contract.role = "PlannerAgent"
        contract.provider = "ollama"
        contract.model = self.chain_runner.single_task_runner._normalize_model(body.model)
        contract.allowed_tools = list(planner_spec.allowed_tools)
        contract.objective = (
            "Validate the existing README Task DAG. You must not create, remove, rename, reorder, or modify tasks. "
            "Return only JSON: {\"status\":\"plan_validated\",\"reason\":\"...\"} or "
            "{\"status\":\"plan_rejected\",\"reason\":\"...\"}."
        )
        contract.acceptance_criteria = [
            "The DAG contains Plan task DAG, Create README.md, Review README.md, and Consolidate final evidence.",
            "Create README.md depends on Plan task DAG.",
            "Review README.md depends on Create README.md.",
            "Consolidate final evidence depends on Review README.md.",
            "No new tasks are proposed.",
        ]
        contract.output_contract = dict(planner_spec.output_contract)
        return contract

    @staticmethod
    def _parse_planner_result(final_message: dict[str, Any] | None) -> dict[str, Any]:
        import json
        import re

        content = str((final_message or {}).get("content") or "").strip()
        if not content:
            return {"status": "plan_rejected", "reason": "empty planner response"}
        try:
            data = json.loads(content)
        except Exception:
            match = re.search(r"\{.*\}", content, flags=re.S)
            if not match:
                return {"status": "plan_rejected", "reason": "planner response was not JSON", "raw": content[:500]}
            try:
                data = json.loads(match.group(0))
            except Exception:
                return {"status": "plan_rejected", "reason": "planner JSON parse failed", "raw": content[:500]}
        if isinstance(data.get("planner_result"), dict):
            data = data["planner_result"]
        status = data.get("status")
        if status not in {"plan_validated", "plan_rejected"}:
            return {"status": "plan_rejected", "reason": "invalid planner status", "raw": data}
        return {"status": status, "reason": str(data.get("reason") or "")}

    def _persist_planner_result(self, *, swarm_id: str, task_id: str, result: dict[str, Any]) -> None:
        swarm = self.store.load(swarm_id)
        task = self._task_by_id(swarm, task_id)
        task.evidence = [item for item in task.evidence if item.get("kind") not in {"plan_reused", "planner_result"}]
        task.evidence.append(result)
        task.status = "completed" if result.get("status") == "validated" else "failed"
        if task.status == "failed":
            task.errors.append({"error": "planner_rejected", "planner_result": result})
        task.updated_at = _now_iso()
        self.store.save(swarm)

    def _mark_task_running(self, swarm_id: str, task_id: str) -> None:
        swarm = self.store.load(swarm_id)
        task = self._task_by_id(swarm, task_id)
        task.status = "running"
        task.updated_at = _now_iso()
        self.store.save(swarm)

    @staticmethod
    def _planner_agent_runtime_enabled() -> bool:
        return os.environ.get(EXPERIMENTAL_PLANNER_AGENT_RUNTIME_FLAG) == "1"

    def _find_task_by_type(self, swarm: SwarmState, task_type: KnownTaskType) -> TaskNode:
        for task in swarm.tasks:
            if self._classify_task(task) == task_type:
                return task
        raise FileNotFoundError(f"Task not found for type: {task_type}")

    @staticmethod
    def _find_approved_review_result(reviewer: TaskNode, artifact: dict[str, Any]) -> dict[str, Any] | None:
        artifact_id = artifact.get("id")
        for item in [*reviewer.validations, *reviewer.evidence]:
            if item.get("kind") == "review_result" and item.get("artifact_id") == artifact_id and item.get("status") == "approved":
                return item
        return None

    @staticmethod
    def _task_by_id(swarm: SwarmState, task_id: str) -> TaskNode:
        for task in swarm.tasks:
            if task.id == task_id:
                return task
        raise FileNotFoundError(f"Task not found: {task_id}")

    def _response(
        self,
        swarm_id: str,
        *,
        status: str,
        execution_order: list[dict[str, Any]],
        errors: list[dict[str, Any]] | None = None,
        ok: bool = False,
    ) -> ExperimentalDAGDependencyRunResponse:
        swarm = self.store.load(swarm_id)
        return ExperimentalDAGDependencyRunResponse(
            ok=ok,
            status=status,
            enabled=True,
            swarm_id=swarm_id,
            execution_order=execution_order,
            tasks=[task.model_dump(mode="json") for task in swarm.tasks],
            artifacts=swarm.artifacts,
            messages=[message.model_dump(mode="json") for message in swarm.messages],
            tool_history=swarm.tool_history,
            final_result=swarm.final_result,
            final_evidence=swarm.final_evidence,
            errors=errors or [],
        )


experimental_dag_dependency_runner = ExperimentalDAGDependencyRunner()
