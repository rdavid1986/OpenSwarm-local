"""Experimental deterministic final consolidation for README DAG slice."""

from __future__ import annotations

import os
from typing import Any

from pydantic import BaseModel, Field

from backend.apps.agents.orchestration.models import AgentToAgentMessage, SwarmState, TaskNode, _now_iso
from backend.apps.agents.orchestration.store import SwarmStore, swarm_store
from backend.apps.agents.runtime.experimental_dag_chain_runner import experimental_dag_chain_runtime_enabled
from backend.apps.agents.runtime.experimental_task_type_registry import ExperimentalTaskType, classify_experimental_task


EXPERIMENTAL_DAG_CONSOLIDATE_RUNTIME_FLAG = "OPENSWARM_EXPERIMENTAL_DAG_CONSOLIDATE_RUNTIME"


class ExperimentalConsolidateFinalRequest(BaseModel):
    workspace_path: str | None = None


class ExperimentalConsolidateFinalResponse(BaseModel):
    ok: bool
    status: str
    enabled: bool = True
    swarm_id: str
    final_result: dict[str, Any] = Field(default_factory=dict)
    final_evidence: list[dict[str, Any]] = Field(default_factory=list)
    tasks: list[dict[str, Any]] = Field(default_factory=list)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    messages: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)


def experimental_dag_consolidate_runtime_enabled() -> bool:
    return experimental_dag_chain_runtime_enabled() and os.environ.get(EXPERIMENTAL_DAG_CONSOLIDATE_RUNTIME_FLAG) == "1"


class ExperimentalDAGConsolidator:
    def __init__(self, *, store: SwarmStore | None = None) -> None:
        self.store = store or swarm_store

    def consolidate_final(self, *, swarm_id: str, body: ExperimentalConsolidateFinalRequest | None = None) -> ExperimentalConsolidateFinalResponse:
        if not experimental_dag_consolidate_runtime_enabled():
            return ExperimentalConsolidateFinalResponse(
                ok=False,
                status="disabled",
                enabled=False,
                swarm_id=swarm_id,
                errors=[{"error": f"Set OPENSWARM_EXPERIMENTAL_MINI_RUNTIME=1, OPENSWARM_EXPERIMENTAL_DAG_TASK_RUNTIME=1, OPENSWARM_EXPERIMENTAL_DAG_CHAIN_RUNTIME=1 and {EXPERIMENTAL_DAG_CONSOLIDATE_RUNTIME_FLAG}=1 to enable"}],
            )

        swarm = self.store.load(swarm_id)
        worker = self._find_task_by_type(swarm, "create_readme")
        reviewer = self._find_task_by_type(swarm, "review_readme", depends_on=worker.id)
        validation = self._find_task_by_type(swarm, "validation_execute", depends_on=reviewer.id)
        consolidate = self._find_task_by_type(swarm, "consolidate_final")
        errors = self._validate_ready(swarm, worker, reviewer, validation)
        if errors:
            return self._response(swarm, status="not_ready", errors=errors, ok=False)

        artifact = self._find_readme_artifact(swarm, worker.id)
        review_result = self._find_approved_review_result(reviewer, artifact)
        final_evidence = self._build_final_evidence(
            swarm=swarm,
            worker=worker,
            reviewer=reviewer,
            consolidate=consolidate,
            artifact=artifact,
            review_result=review_result,
            validation=validation,
        )
        validation_result = validation.validations[-1] if validation.validations else {}
        final_result = {
            "status": "completed",
            "summary": "README.md was created by the Worker, approved by the Reviewer, and validated with SafeShell evidence.",
            "artifact_refs": [artifact.get("id")],
            "review_result": {
                "status": review_result.get("status"),
                "artifact_path": review_result.get("artifact_path"),
                "required_read_satisfied": review_result.get("required_read_satisfied"),
            },
            "validation_result": {
                "status": validation_result.get("status"),
                "commands": validation_result.get("commands") or [],
                "evidence": validation_result.get("evidence") or [],
            },
            "completed_tasks": [worker.id, reviewer.id, validation.id, consolidate.id],
            "created_at": _now_iso(),
        }
        final_result["claim_guard"] = self._build_claim_guard(
            final_result=final_result,
            final_evidence=final_evidence,
            artifact=artifact,
            review_result=review_result,
            worker=worker,
            reviewer=reviewer,
        )
        self._apply_claim_guard(final_result)

        self._upsert_final_evidence(swarm, final_evidence)
        swarm.final_result = final_result
        consolidate.status = "completed"
        consolidate.evidence = [item for item in consolidate.evidence if item.get("kind") != "final_consolidation"]
        consolidate.evidence.append({"kind": "final_consolidation", "final_result": final_result, "final_evidence_count": len(final_evidence)})
        consolidate.updated_at = _now_iso()
        self._append_consolidation_message_once(swarm, consolidate, final_result)
        swarm.status = "completed"
        self.store.save(swarm)
        return self._response(swarm, status="completed", ok=True)

    def _validate_ready(self, swarm: SwarmState, worker: TaskNode, reviewer: TaskNode, validation: TaskNode) -> list[dict[str, Any]]:
        errors: list[dict[str, Any]] = []
        if worker.status != "completed":
            errors.append({"error": "worker_not_completed", "task_id": worker.id, "status": worker.status})
        if reviewer.status != "completed":
            errors.append({"error": "reviewer_not_completed", "task_id": reviewer.id, "status": reviewer.status})
        if validation.status != "completed":
            errors.append({"error": "validation_not_completed", "task_id": validation.id, "status": validation.status})
        if not validation.validations:
            errors.append({"error": "validation_result_missing", "task_id": validation.id})
        artifact = self._find_readme_artifact(swarm, worker.id)
        if not artifact:
            errors.append({"error": "readme_artifact_missing", "task_id": worker.id})
        elif not self._find_approved_review_result(reviewer, artifact):
            errors.append({"error": "approved_review_result_missing", "task_id": reviewer.id, "artifact_id": artifact.get("id")})
        return errors

    @staticmethod
    def _build_final_evidence(
        *,
        swarm: SwarmState,
        worker: TaskNode,
        reviewer: TaskNode,
        consolidate: TaskNode,
        artifact: dict[str, Any],
        review_result: dict[str, Any],
        validation: TaskNode,
    ) -> list[dict[str, Any]]:
        return [
            {
                "kind": "artifact",
                "task_id": worker.id,
                "artifact": artifact,
            },
            {
                "kind": "review_result",
                "task_id": reviewer.id,
                "review_result": review_result,
            },
            {
                "kind": "validation_result",
                "task_id": validation.id,
                "validation_result": validation.validations[-1] if validation.validations else {},
            },
            {
                "kind": "task_status",
                "tasks": [
                    {"id": worker.id, "title": worker.title, "status": worker.status},
                    {"id": reviewer.id, "title": reviewer.title, "status": reviewer.status},
                    {"id": validation.id, "title": validation.title, "status": validation.status},
                    {"id": consolidate.id, "title": consolidate.title, "status": "completed"},
                ],
            },
            {
                "kind": "tool_history_summary",
                "tool_count": len(swarm.tool_history),
                "tools": [
                    {
                        "tool": entry.get("tool"),
                        "status": entry.get("status"),
                        "ok": entry.get("ok"),
                        "task_id": entry.get("task_id"),
                        "path": (entry.get("result") or {}).get("path"),
                    }
                    for entry in swarm.tool_history
                    if entry.get("task_id") in {worker.id, reviewer.id, validation.id}
                ],
            },
        ]

    @staticmethod
    def _upsert_final_evidence(swarm: SwarmState, evidence: list[dict[str, Any]]) -> None:
        swarm.final_evidence = [item for item in swarm.final_evidence if item.get("kind") not in {"artifact", "review_result", "task_status", "tool_history_summary"}]
        swarm.final_evidence.extend(evidence)

    @staticmethod
    def _build_claim_guard(
        *,
        final_result: dict[str, Any],
        final_evidence: list[dict[str, Any]],
        artifact: dict[str, Any],
        review_result: dict[str, Any],
        worker: TaskNode,
        reviewer: TaskNode,
    ) -> dict[str, Any]:
        artifact_refs = set(final_result.get("artifact_refs") or [])
        evidence_by_kind = {item.get("kind"): item for item in final_evidence if isinstance(item, dict)}
        tool_summary = evidence_by_kind.get("tool_history_summary") or {}
        tool_rows = tool_summary.get("tools") or []

        artifact_supported = (
            bool(artifact.get("id"))
            and artifact.get("id") in artifact_refs
            and bool(evidence_by_kind.get("artifact"))
            and (evidence_by_kind.get("artifact") or {}).get("artifact", {}).get("id") == artifact.get("id")
        )
        review_supported = (
            review_result.get("status") == "approved"
            and bool(evidence_by_kind.get("review_result"))
            and (evidence_by_kind.get("review_result") or {}).get("review_result", {}).get("status") == "approved"
            and (evidence_by_kind.get("review_result") or {}).get("review_result", {}).get("artifact_id") == artifact.get("id")
        )
        tasks_supported = False
        task_status = evidence_by_kind.get("task_status") or {}
        task_rows = task_status.get("tasks") or []
        statuses = {row.get("id"): row.get("status") for row in task_rows if isinstance(row, dict)}
        if statuses.get(worker.id) == "completed" and statuses.get(reviewer.id) == "completed":
            tasks_supported = True

        tool_history_supported = any(
            isinstance(row, dict)
            and row.get("task_id") == worker.id
            and row.get("tool") in {"Write", "Edit"}
            and row.get("ok") is True
            and str(row.get("path") or "").replace("\\", "/").lower() == "readme.md"
            for row in tool_rows
        ) and any(
            isinstance(row, dict)
            and row.get("task_id") == reviewer.id
            and row.get("tool") == "Read"
            and row.get("ok") is True
            and str(row.get("path") or "").replace("\\", "/").lower() == "readme.md"
            for row in tool_rows
        )

        checks = {
            "artifact_supported": artifact_supported,
            "review_supported": review_supported,
            "tasks_supported": tasks_supported,
            "tool_history_supported": tool_history_supported,
        }
        return {
            "status": "verified" if all(checks.values()) else "unverified",
            "checks": checks,
            "supported_claims": [
                "README.md artifact exists and is referenced by final_result.",
                "Reviewer approved the referenced README.md artifact.",
                "Worker and Reviewer tasks completed.",
                "Write/Edit and Read tool history supports the create-review claim.",
            ],
            "unsupported_claims": [] if all(checks.values()) else [name for name, ok in checks.items() if not ok],
        }

    @staticmethod
    def _apply_claim_guard(final_result: dict[str, Any]) -> None:
        claim_guard = final_result.get("claim_guard") or {}
        if claim_guard.get("status") == "verified":
            return
        final_result["status"] = "evidence_unverified"
        final_result["summary"] = (
            "Final result could not be fully verified against recorded evidence. "
            "See claim_guard.unsupported_claims before trusting completion claims."
        )

    def _append_consolidation_message_once(self, swarm: SwarmState, consolidate: TaskNode, final_result: dict[str, Any]) -> None:
        from_agent_id = consolidate.assigned_contract_id or swarm.coordinator_contract_id or "CoordinatorAgent"
        for existing in swarm.messages:
            if existing.type == "send_message_to_agent" and existing.from_agent_id == from_agent_id and existing.task_id == consolidate.id and existing.payload.get("final_result"):
                existing.payload["final_result"] = final_result
                return
        swarm.messages.append(
            AgentToAgentMessage(
                type="send_message_to_agent",
                from_agent_id=from_agent_id,
                task_id=consolidate.id,
                payload={"final_result": final_result},
                artifact_refs=list(final_result.get("artifact_refs") or []),
            )
        )

    @staticmethod
    def _find_task_by_type(
        swarm: SwarmState,
        task_type: ExperimentalTaskType,
        *,
        depends_on: str | None = None,
    ) -> TaskNode:
        for task in swarm.tasks:
            if depends_on and depends_on not in task.depends_on:
                continue
            try:
                if classify_experimental_task(task) == task_type:
                    return task
            except ValueError:
                continue
        raise FileNotFoundError(f"Task not found for type: {task_type}")

    @staticmethod
    def _find_readme_artifact(swarm: SwarmState, worker_task_id: str) -> dict[str, Any] | None:
        return next(
            (
                artifact for artifact in swarm.artifacts
                if artifact.get("task_id") == worker_task_id and str(artifact.get("path", "")).replace("\\", "/").lower() == "readme.md"
            ),
            None,
        )

    @staticmethod
    def _find_approved_review_result(reviewer: TaskNode, artifact: dict[str, Any] | None) -> dict[str, Any] | None:
        if not artifact:
            return None
        artifact_id = artifact.get("id")
        for item in [*reviewer.validations, *reviewer.evidence]:
            if item.get("kind") == "review_result" and item.get("artifact_id") == artifact_id and item.get("status") == "approved":
                return item
        return None

    @staticmethod
    def _response(swarm: SwarmState, *, status: str, ok: bool, errors: list[dict[str, Any]] | None = None) -> ExperimentalConsolidateFinalResponse:
        return ExperimentalConsolidateFinalResponse(
            ok=ok,
            status=status,
            enabled=True,
            swarm_id=swarm.id,
            final_result=swarm.final_result,
            final_evidence=swarm.final_evidence,
            tasks=[task.model_dump(mode="json") for task in swarm.tasks],
            artifacts=swarm.artifacts,
            messages=[message.model_dump(mode="json") for message in swarm.messages],
            errors=errors or [],
        )


experimental_dag_consolidator = ExperimentalDAGConsolidator()
