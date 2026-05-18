"""Minimal vertical MVP executor for SwarmOrchestrator.

This intentionally does not refactor AgentManager or provider loops. It executes
one fixed README-review vertical slice using existing builtin tool definitions,
PolicyRuntime, EventTraceRuntime, and SwarmStore so the UI/API can inspect real
state and real filesystem evidence.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.apps.agents.orchestration.models import SwarmState, _now_iso
from backend.apps.agents.orchestration.store import SwarmStore, swarm_store
from backend.apps.agents.runtime.events import event_trace_runtime
from backend.apps.agents.runtime.tools import (
    ToolCall,
    ToolExecutionContext,
    ToolRuntime,
    tool_runtime,
)


class SwarmMVPExecutor:
    def __init__(
        self,
        *,
        store: SwarmStore | None = None,
        tools: ToolRuntime | None = None,
    ) -> None:
        self.store = store or swarm_store
        self.tools = tools or tool_runtime

    def run_readme_review_mvp(self, swarm_id: str, *, workspace_path: str | None = None) -> SwarmState:
        swarm = self.store.load(swarm_id)
        workspace = self._resolve_workspace(swarm, workspace_path=workspace_path)
        swarm.workspace_path = str(workspace)
        swarm.status = "running"
        self._event(swarm, "task_started", payload={"workspace_path": str(workspace)})

        planner = self._contract_by_role(swarm, "PlannerAgent")
        worker = self._contract_by_role(swarm, "DocumentationAgent")
        reviewer = self._contract_by_role(swarm, "ReviewerAgent")
        coordinator = self._contract_by_role(swarm, "CoordinatorAgent")

        plan_task = self._task_by_title(swarm, "Plan task DAG")
        write_task = self._task_by_title(swarm, "Create README.md")
        review_task = self._task_by_title(swarm, "Review README.md")
        consolidate_task = self._task_by_title(swarm, "Consolidate final evidence")

        self._complete_task(
            swarm,
            plan_task.id,
            evidence={
                "kind": "task_dag_ready",
                "agent_id": planner["id"],
                "task_count": len(swarm.tasks),
                "contract_count": len(swarm.contracts),
            },
        )

        readme_content = self._render_readme(swarm)
        write_result = self._execute_write_tool(
            swarm=swarm,
            agent_id=worker["id"],
            task_id=write_task.id,
            workspace=workspace,
            path="README.md",
            content=readme_content,
        )
        write_data = write_result.result
        artifact = {
            "id": f"artifact-{write_task.id}",
            "kind": "documentation",
            "path": "README.md",
            "absolute_path": str(workspace / "README.md"),
            "bytes": write_data["bytes"],
            "created_by_agent_id": worker["id"],
            "created_by_task_id": write_task.id,
            "created_at": _now_iso(),
        }
        swarm.artifacts.append(artifact)
        write_task.artifacts.append(artifact)
        write_task.touched_files.append("README.md")
        write_task.evidence.append({"kind": "tool_result", "tool": "Write", "result": write_result.to_history_entry()})
        swarm.messages.append(self._message("submit_artifact", worker["id"], task_id=write_task.id, payload=artifact))
        self._complete_task(swarm, write_task.id, evidence={"kind": "artifact_submitted", "path": "README.md"})
        self._event(swarm, "agent_message", task_id=write_task.id, agent_id=worker["id"], payload={"message_type": "submit_artifact", "artifact": artifact})

        swarm.messages.append(
            self._message(
                "request_review",
                coordinator["id"],
                to_agent_id=reviewer["id"],
                task_id=review_task.id,
                artifact_refs=[artifact["id"], artifact["path"]],
            )
        )
        self._event(swarm, "review_requested", task_id=review_task.id, agent_id=coordinator["id"], payload={"artifact_refs": [artifact["id"], artifact["path"]]})

        read_result = self._execute_read_tool(
            swarm=swarm,
            agent_id=reviewer["id"],
            task_id=review_task.id,
            workspace=workspace,
            path="README.md",
        )
        read_data = read_result.result
        approved = read_result.ok and "OpenSwarm MVP" in read_data.get("content", "")
        review_result = {
            "kind": "review_result",
            "status": "approved" if approved else "rejected",
            "reviewer_agent_id": reviewer["id"],
            "read_tool_result": {
                "path": read_data.get("path"),
                "bytes_read": len((read_data.get("content") or "").encode("utf-8")),
                "truncated": read_data.get("truncated", False),
            },
            "checks": [
                {"name": "file_exists", "passed": read_result.ok},
                {"name": "contains_expected_title", "passed": "OpenSwarm MVP" in read_data.get("content", "")},
            ],
            "created_at": _now_iso(),
        }
        review_task.evidence.append({"kind": "tool_result", "tool": "Read", "result": read_result.to_history_entry()})
        review_task.validations.append(review_result)
        swarm.messages.append(self._message("send_message_to_agent", reviewer["id"], to_agent_id=coordinator["id"], task_id=review_task.id, payload=review_result))
        self._complete_task(swarm, review_task.id, evidence=review_result)
        self._event(swarm, "review_completed", task_id=review_task.id, agent_id=reviewer["id"], payload=review_result)

        final_evidence = [
            {"kind": "workspace", "path": str(workspace)},
            {"kind": "artifact", "path": artifact["path"], "absolute_path": artifact["absolute_path"], "bytes": artifact["bytes"]},
            review_result,
        ]
        swarm.final_evidence = final_evidence
        swarm.final_result = {
            "status": "completed" if approved else "failed",
            "summary": "README.md creado y aprobado por ReviewerAgent." if approved else "README.md creado pero rechazado por ReviewerAgent.",
            "evidence": final_evidence,
            "provider_bridge": "pending: executor is prepared around contracts/runtime state but does not call OllamaAdapter yet.",
        }
        self._complete_task(swarm, consolidate_task.id, evidence={"kind": "final_result", **swarm.final_result})
        swarm.status = "completed" if approved else "failed"
        self._event(swarm, "swarm_completed", task_id=consolidate_task.id, agent_id=coordinator["id"], payload=swarm.final_result)
        return self.store.save(swarm)

    def _resolve_workspace(self, swarm: SwarmState, *, workspace_path: str | None) -> Path:
        raw = workspace_path or swarm.workspace_path
        if raw:
            workspace = Path(raw).expanduser().resolve()
        else:
            workspace = (self.store._path(swarm.id).parent / "workspace").resolve()
        workspace.mkdir(parents=True, exist_ok=True)
        return workspace

    def _execute_write_tool(self, *, swarm: SwarmState, agent_id: str, task_id: str, workspace: Path, path: str, content: str):
        self._event(swarm, "tool_requested", task_id=task_id, agent_id=agent_id, payload={"tool": "Write", "path": path})
        result = self.tools.execute_tool(
            ToolCall(name="Write", input={"path": path, "content": content}),
            self._tool_context(swarm, agent_id=agent_id, task_id=task_id, workspace=workspace),
            history=swarm.tool_history,
        )
        if not result.ok:
            raise RuntimeError(result.error or "Write failed")
        return result

    def _execute_read_tool(self, *, swarm: SwarmState, agent_id: str, task_id: str, workspace: Path, path: str):
        self._event(swarm, "tool_requested", task_id=task_id, agent_id=agent_id, payload={"tool": "Read", "path": path})
        result = self.tools.execute_tool(
            ToolCall(name="Read", input={"path": path}),
            self._tool_context(swarm, agent_id=agent_id, task_id=task_id, workspace=workspace),
            history=swarm.tool_history,
        )
        return result

    @staticmethod
    def _tool_context(swarm: SwarmState, *, agent_id: str, task_id: str, workspace: Path) -> ToolExecutionContext:
        return ToolExecutionContext(
            workspace_path=str(workspace),
            swarm_id=swarm.id,
            agent_id=agent_id,
            task_id=task_id,
        )

    @staticmethod
    def _render_readme(swarm: SwarmState) -> str:
        return f"""# OpenSwarm MVP

Este README fue creado por el MVP vertical del Swarm Orchestrator.

## Instrucción global

{swarm.user_prompt}

## Evidencia esperada

- Worker creó este archivo usando la tool real `Write`.
- Reviewer leyó este archivo usando la tool real `Read`.
- El estado del swarm persiste tasks, mensajes, artifacts y evidencia.
"""

    @staticmethod
    def _contract_by_role(swarm: SwarmState, role: str) -> dict[str, Any]:
        for contract in swarm.contracts:
            if contract.role == role:
                return contract.model_dump(mode="json")
        raise RuntimeError(f"Missing contract role: {role}")

    @staticmethod
    def _task_by_title(swarm: SwarmState, title: str):
        for task in swarm.tasks:
            if task.title == title:
                return task
        raise RuntimeError(f"Missing task: {title}")

    @staticmethod
    def _complete_task(swarm: SwarmState, task_id: str, *, evidence: dict[str, Any]) -> None:
        for task in swarm.tasks:
            if task.id == task_id:
                task.status = "completed"
                task.evidence.append(evidence)
                task.updated_at = _now_iso()
                return
        raise RuntimeError(f"Missing task_id: {task_id}")

    @staticmethod
    def _message(message_type: str, from_agent_id: str, **kwargs):
        from backend.apps.agents.orchestration.models import AgentToAgentMessage

        return AgentToAgentMessage(type=message_type, from_agent_id=from_agent_id, **kwargs)

    @staticmethod
    def _event(swarm: SwarmState, event_type: str, **kwargs) -> None:
        event_trace_runtime.create(event_type, swarm_id=swarm.id, **kwargs)


swarm_mvp_executor = SwarmMVPExecutor()
