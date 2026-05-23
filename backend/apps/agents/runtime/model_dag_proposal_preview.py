"""Model-generated DAG proposal preview service.

This service asks a model for a DAG proposal, validates it through the
orchestrator preview pipeline, and persists only decisions. It must not execute
DAG tasks or persist model-generated tasks/contracts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from backend.apps.agents.orchestration.models import AgentContract, TaskNode
from backend.apps.agents.orchestration.orchestrator import SwarmOrchestrator, swarm_orchestrator
from backend.apps.agents.orchestration.store import SwarmStore, swarm_store
from backend.apps.agents.providers.ollama_adapter import OllamaAdapter
from backend.apps.agents.runtime.mini_agent_runtime import MiniAgentRuntime, MiniAgentRuntimeContext


@dataclass
class ModelDAGProposalPreviewRequest:
    model: str = "qwen2.5-coder:14b"
    base_url: str | None = None
    generated_plan: dict[str, Any] | None = None
    max_turns: int = 1


@dataclass
class ModelDAGProposalPreviewResponse:
    ok: bool
    status: str
    validation_errors: list[dict[str, Any]] = field(default_factory=list)
    decision: dict[str, Any] | None = None
    final_message: dict[str, Any] | None = None
    provider_events: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    turns: int = 0
    swarm: dict[str, Any] | None = None


class ModelDAGProposalPreviewService:
    def __init__(
        self,
        *,
        store: SwarmStore | None = None,
        orchestrator: SwarmOrchestrator | None = None,
        runtime: MiniAgentRuntime | None = None,
        adapter_factory: Callable[..., OllamaAdapter] | None = None,
    ) -> None:
        self.store = store or swarm_store
        self.orchestrator = orchestrator or swarm_orchestrator
        self.runtime = runtime or MiniAgentRuntime(store=self.store)
        self.adapter_factory = adapter_factory or OllamaAdapter

    async def generate_preview(
        self,
        *,
        swarm_id: str,
        request: ModelDAGProposalPreviewRequest,
    ) -> ModelDAGProposalPreviewResponse:
        swarm = self.store.load(swarm_id)
        prompt = self.orchestrator._build_model_dag_proposal_prompt(generated_plan=request.generated_plan)

        adapter = self.adapter_factory(base_url=request.base_url, allow_network=True)
        health = adapter.healthcheck(timeout_seconds=2.0)
        if not health.get("ok"):
            saved, validation_errors = self.orchestrator.record_model_dag_proposal_preview(
                swarm_id=swarm_id,
                final_message={"content": ""},
            )
            error = {"error": "provider_unavailable", "detail": health}
            saved.decisions[-1]["validation_errors"] = [error]
            saved.decisions[-1]["metadata"]["provider"] = health
            saved.decisions[-1]["status"] = "rejected"
            saved = self.store.save(saved)
            return ModelDAGProposalPreviewResponse(
                ok=False,
                status="provider_unavailable",
                validation_errors=[error],
                decision=saved.decisions[-1] if saved.decisions else None,
                errors=[error],
                swarm=saved.model_dump(mode="json"),
            )

        contract = AgentContract(
            role="PlannerAgent",
            objective="Generate a safe model_generated_dag proposal for preview only.",
            allowed_tools=[],
            provider="ollama",
            model=self._normalize_model(request.model),
            acceptance_criteria=[
                "Return JSON only.",
                "Do not include allowed_tools or output_contract.",
                "Use only supported task types and roles.",
            ],
            output_contract={"dag_proposal": {"kind": "model_generated_dag", "tasks": []}},
        )
        task = TaskNode(
            title="Generate DAG proposal preview",
            objective=prompt,
            assigned_contract_id=contract.id,
        )

        workspace = Path(swarm.workspace_path or (self.store._path(swarm_id).parent / "dag_proposal_preview_workspace"))
        workspace.mkdir(parents=True, exist_ok=True)

        runtime_result = await self.runtime.run_agent_task(
            MiniAgentRuntimeContext(
                contract=contract,
                task=task,
                provider=adapter,
                workspace_path=str(workspace),
                model=contract.model or self._normalize_model(request.model),
                provider_tool_format="ollama",
                swarm_id=None,
                store=None,
                max_turns=max(1, min(int(request.max_turns or 1), 3)),
                inputs={"instruction": prompt},
            )
        )

        if runtime_result.status != "completed" or not runtime_result.final_message:
            final_message = runtime_result.final_message or {"content": ""}
            saved, validation_errors = self.orchestrator.record_model_dag_proposal_preview(
                swarm_id=swarm_id,
                final_message=final_message,
            )
            error = {
                "error": "model_failed",
                "runtime_status": runtime_result.status,
                "runtime_errors": runtime_result.errors,
            }
            saved.decisions[-1]["validation_errors"] = [error, *validation_errors]
            saved.decisions[-1]["status"] = "rejected"
            saved = self.store.save(saved)
            return ModelDAGProposalPreviewResponse(
                ok=False,
                status="model_failed",
                validation_errors=[error, *validation_errors],
                decision=saved.decisions[-1] if saved.decisions else None,
                final_message=runtime_result.final_message,
                provider_events=runtime_result.provider_events,
                errors=runtime_result.errors,
                turns=runtime_result.turns,
                swarm=saved.model_dump(mode="json"),
            )

        saved, validation_errors = self.orchestrator.record_model_dag_proposal_preview(
            swarm_id=swarm_id,
            final_message=runtime_result.final_message,
        )
        status = "accepted" if not validation_errors else "rejected"
        return ModelDAGProposalPreviewResponse(
            ok=not validation_errors,
            status=status,
            validation_errors=validation_errors,
            decision=saved.decisions[-1] if saved.decisions else None,
            final_message=runtime_result.final_message,
            provider_events=runtime_result.provider_events,
            errors=runtime_result.errors,
            turns=runtime_result.turns,
            swarm=saved.model_dump(mode="json"),
        )

    @staticmethod
    def _normalize_model(model: str) -> str:
        clean = str(model or "").strip() or "qwen2.5-coder:14b"
        return clean if clean.startswith("ollama/") else f"ollama/{clean}"


model_dag_proposal_preview_service = ModelDAGProposalPreviewService()
