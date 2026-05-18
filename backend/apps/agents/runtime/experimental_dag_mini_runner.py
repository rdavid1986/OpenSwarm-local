"""Experimental automatic README mini-DAG runner.

This is not a generic DAG orchestrator. It only wires the validated README slice:
Worker -> Reviewer -> deterministic Consolidate.
"""

from __future__ import annotations

import os
from typing import Any

from pydantic import BaseModel, Field

from backend.apps.agents.orchestration.models import SwarmState, TaskNode
from backend.apps.agents.orchestration.store import SwarmStore, swarm_store
from backend.apps.agents.runtime.experimental_dag_chain_runner import (
    ExperimentalDAGChainRunner,
    ExperimentalWorkerReviewRunRequest,
    experimental_dag_chain_runner,
)
from backend.apps.agents.runtime.experimental_task_type_registry import ExperimentalTaskType, classify_experimental_task
from backend.apps.agents.runtime.experimental_dag_consolidator import (
    ExperimentalConsolidateFinalRequest,
    ExperimentalDAGConsolidator,
    experimental_dag_consolidate_runtime_enabled,
    experimental_dag_consolidator,
)


EXPERIMENTAL_DAG_MINI_RUNNER_FLAG = "OPENSWARM_EXPERIMENTAL_DAG_MINI_RUNNER"


class ExperimentalMiniDAGRunRequest(ExperimentalWorkerReviewRunRequest):
    pass


class ExperimentalMiniDAGRunResponse(BaseModel):
    ok: bool
    status: str
    enabled: bool = True
    swarm_id: str
    worker_review: dict[str, Any] = Field(default_factory=dict)
    consolidation: dict[str, Any] = Field(default_factory=dict)
    tasks: list[dict[str, Any]] = Field(default_factory=list)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    messages: list[dict[str, Any]] = Field(default_factory=list)
    tool_history: list[dict[str, Any]] = Field(default_factory=list)
    final_result: dict[str, Any] = Field(default_factory=dict)
    final_evidence: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)


def experimental_dag_mini_runner_enabled() -> bool:
    return experimental_dag_consolidate_runtime_enabled() and os.environ.get(EXPERIMENTAL_DAG_MINI_RUNNER_FLAG) == "1"


class ExperimentalDAGMiniRunner:
    def __init__(
        self,
        *,
        store: SwarmStore | None = None,
        chain_runner: ExperimentalDAGChainRunner | None = None,
        consolidator: ExperimentalDAGConsolidator | None = None,
    ) -> None:
        self.store = store or swarm_store
        self.chain_runner = chain_runner or experimental_dag_chain_runner
        self.consolidator = consolidator or experimental_dag_consolidator

    async def run_mini_dag(self, *, swarm_id: str, body: ExperimentalMiniDAGRunRequest) -> ExperimentalMiniDAGRunResponse:
        if not experimental_dag_mini_runner_enabled():
            return ExperimentalMiniDAGRunResponse(
                ok=False,
                status="disabled",
                enabled=False,
                swarm_id=swarm_id,
                errors=[{"error": f"Set OPENSWARM_EXPERIMENTAL_MINI_RUNTIME=1, OPENSWARM_EXPERIMENTAL_DAG_TASK_RUNTIME=1, OPENSWARM_EXPERIMENTAL_DAG_CHAIN_RUNTIME=1, OPENSWARM_EXPERIMENTAL_DAG_CONSOLIDATE_RUNTIME=1 and {EXPERIMENTAL_DAG_MINI_RUNNER_FLAG}=1 to enable"}],
            )

        swarm = self.store.load(swarm_id)
        worker_review_payload: dict[str, Any] = {"status": "skipped_existing_completed"}
        if not self._worker_and_reviewer_ready(swarm):
            worker_review = await self.chain_runner.run_worker_review(swarm_id=swarm_id, body=body)
            worker_review_payload = worker_review.model_dump(mode="json")
            if not worker_review.ok:
                return self._response(
                    swarm_id=swarm_id,
                    status="worker_review_failed",
                    worker_review=worker_review_payload,
                    errors=worker_review.errors,
                    ok=False,
                )

        consolidation = self.consolidator.consolidate_final(
            swarm_id=swarm_id,
            body=ExperimentalConsolidateFinalRequest(workspace_path=body.workspace_path),
        )
        return self._response(
            swarm_id=swarm_id,
            status=consolidation.status,
            worker_review=worker_review_payload,
            consolidation=consolidation.model_dump(mode="json"),
            errors=consolidation.errors,
            ok=consolidation.ok,
        )

    def _worker_and_reviewer_ready(self, swarm: SwarmState) -> bool:
        worker = self._find_task_by_type(swarm, "create_readme")
        reviewer = self._find_task_by_type(swarm, "review_readme", depends_on=worker.id)
        if worker.status != "completed" or reviewer.status != "completed":
            return False
        artifact = self._find_readme_artifact(swarm, worker.id)
        if not artifact:
            return False
        return self._find_approved_review_result(reviewer, artifact) is not None

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
    def _find_approved_review_result(reviewer: TaskNode, artifact: dict[str, Any]) -> dict[str, Any] | None:
        artifact_id = artifact.get("id")
        for item in [*reviewer.validations, *reviewer.evidence]:
            if item.get("kind") == "review_result" and item.get("artifact_id") == artifact_id and item.get("status") == "approved":
                return item
        return None

    def _response(
        self,
        *,
        swarm_id: str,
        status: str,
        worker_review: dict[str, Any] | None = None,
        consolidation: dict[str, Any] | None = None,
        errors: list[dict[str, Any]] | None = None,
        ok: bool = False,
    ) -> ExperimentalMiniDAGRunResponse:
        swarm = self.store.load(swarm_id)
        return ExperimentalMiniDAGRunResponse(
            ok=ok,
            status=status,
            enabled=True,
            swarm_id=swarm_id,
            worker_review=worker_review or {},
            consolidation=consolidation or {},
            tasks=[task.model_dump(mode="json") for task in swarm.tasks],
            artifacts=swarm.artifacts,
            messages=[message.model_dump(mode="json") for message in swarm.messages],
            tool_history=swarm.tool_history,
            final_result=swarm.final_result,
            final_evidence=swarm.final_evidence,
            errors=errors or [],
        )


experimental_dag_mini_runner = ExperimentalDAGMiniRunner()
