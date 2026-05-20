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
        self._merge_persisted_evidence(swarm)
        write_data = write_result.result
        write_evidence = self._find_tool_evidence(
            swarm,
            call_id=write_result.call_id,
            task_id=write_task.id,
            path="README.md",
        )
        artifact = {
            "id": f"artifact-{write_task.id}",
            "kind": "documentation",
            "path": "README.md",
            "absolute_path": str(workspace / "README.md"),
            "bytes": write_data["bytes"],
            "created_by_agent_id": worker["id"],
            "created_by_task_id": write_task.id,
            **({"evidence_id": write_evidence.id} if write_evidence else {}),
            "evidence_ref": write_result.call_id,
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
        self._merge_persisted_evidence(swarm)
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
        swarm.final_result["claim_guard"] = self._build_mvp_claim_guard(
            final_result=swarm.final_result,
            final_evidence=final_evidence,
            review_result=review_result,
            approved=approved,
            artifact=artifact,
            write_task_id=write_task.id,
            review_task_id=review_task.id,
        )
        self._apply_mvp_claim_guard(swarm.final_result)
        self._complete_task(swarm, consolidate_task.id, evidence={"kind": "final_result", **swarm.final_result})
        swarm.status = "completed" if approved else "failed"
        self._event(swarm, "swarm_completed", task_id=consolidate_task.id, agent_id=coordinator["id"], payload=swarm.final_result)
        self._merge_persisted_evidence(swarm)
        return self.store.save(swarm)

    @staticmethod
    def _build_mvp_claim_guard(
        *,
        final_result: dict[str, Any],
        final_evidence: list[dict[str, Any]],
        review_result: dict[str, Any],
        approved: bool,
        artifact: dict[str, Any],
        write_task_id: str,
        review_task_id: str,
    ) -> dict[str, Any]:
        evidence_kinds = {item.get("kind") for item in final_evidence if isinstance(item, dict)}
        artifact_supported = (
            "artifact" in evidence_kinds
            and any(
                isinstance(item, dict)
                and item.get("kind") == "artifact"
                and item.get("path") == artifact.get("path")
                and item.get("absolute_path") == artifact.get("absolute_path")
                for item in final_evidence
            )
        )
        review_supported = (
            approved is True
            and review_result.get("status") == "approved"
            and any(
                isinstance(check, dict)
                and check.get("name") == "file_exists"
                and check.get("passed") is True
                for check in review_result.get("checks") or []
            )
            and any(
                isinstance(check, dict)
                and check.get("name") == "contains_expected_title"
                and check.get("passed") is True
                for check in review_result.get("checks") or []
            )
        )
        workspace_supported = "workspace" in evidence_kinds
        task_refs_supported = bool(write_task_id and review_task_id)

        checks = {
            "artifact_supported": artifact_supported,
            "review_supported": review_supported,
            "workspace_supported": workspace_supported,
            "task_refs_supported": task_refs_supported,
        }
        return {
            "status": "verified" if all(checks.values()) else "unverified",
            "checks": checks,
            "supported_claims": [
                "README.md artifact is present in final evidence.",
                "Reviewer approved README.md after reading expected content.",
                "Workspace evidence is present.",
                "Worker and Reviewer task references are present.",
            ],
            "unsupported_claims": [] if all(checks.values()) else [name for name, ok in checks.items() if not ok],
        }

    @staticmethod
    def _apply_mvp_claim_guard(final_result: dict[str, Any]) -> None:
        claim_guard = final_result.get("claim_guard") or {}
        if claim_guard.get("status") == "verified":
            return
        final_result["status"] = "evidence_unverified"
        final_result["summary"] = (
            "El resultado final no pudo verificarse completamente contra la evidencia registrada. "
            "Revisá claim_guard.unsupported_claims antes de confiar en las afirmaciones de cierre."
        )

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

    def _merge_persisted_evidence(self, swarm: SwarmState) -> None:
        try:
            persisted = self.store.load(swarm.id)
        except Exception:
            return
        existing_ids = {item.id for item in swarm.evidence}
        for item in persisted.evidence:
            if item.id not in existing_ids:
                swarm.evidence.append(item)
                existing_ids.add(item.id)

    @staticmethod
    def _find_tool_evidence(swarm: SwarmState, *, call_id: str, task_id: str, path: str):
        normalized_path = str(path or "").replace("\\", "/")
        for evidence in swarm.evidence:
            if evidence.tool_call_id != call_id:
                continue
            if evidence.task_id != task_id:
                continue
            if str(evidence.file_path or "").replace("\\", "/") == normalized_path:
                return evidence
        return None

    @staticmethod
    def _message(message_type: str, from_agent_id: str, **kwargs):
        from backend.apps.agents.orchestration.models import AgentToAgentMessage

        return AgentToAgentMessage(type=message_type, from_agent_id=from_agent_id, **kwargs)

    @staticmethod
    def _event(swarm: SwarmState, event_type: str, **kwargs) -> None:
        event_trace_runtime.create(event_type, swarm_id=swarm.id, **kwargs)


swarm_mvp_executor = SwarmMVPExecutor()
