"""Minimal non-executing Swarm Orchestrator.

Creates Coordinator/Planner/Worker/Reviewer contracts and a durable Task DAG
for the mandatory README-review MVP shape. It does not launch sessions yet.
"""

from __future__ import annotations

from backend.apps.agents.orchestration.models import (
    AgentContract,
    AgentToAgentMessage,
    SwarmStatus,
    SwarmState,
    TaskNode,
)
from backend.apps.agents.orchestration.store import SwarmStore, swarm_store
from backend.apps.agents.runtime.experimental_task_type_registry import get_experimental_task_spec


class SwarmOrchestrator:
    def __init__(self, store: SwarmStore | None = None) -> None:
        self.store = store or swarm_store

    def create_swarm(
        self,
        *,
        user_prompt: str,
        dashboard_id: str | None = None,
        workspace_path: str | None = None,
    ) -> SwarmState:
        prompt = (user_prompt or "").strip()
        if not prompt:
            raise ValueError("user_prompt is required")

        intent = self._classify_intent(prompt)

        if intent == "chat":
            coordinator = AgentContract(
                role="CoordinatorAgent",
                objective="Answer normal user questions in the Swarm chat without executing a Task DAG.",
                allowed_tools=[],
                acceptance_criteria=["Answer the user clearly.", "Do not create artifacts unless explicitly requested."],
                output_contract={"message": "string"},
            )
            swarm = SwarmState(
                title=self._derive_title(prompt),
                user_prompt=prompt,
                intent="chat",
                dashboard_id=dashboard_id,
                workspace_path=workspace_path,
                coordinator_contract_id=coordinator.id,
                contracts=[coordinator],
                tasks=[],
                messages=[
                    AgentToAgentMessage(
                        type="broadcast_to_swarm",
                        from_agent_id=coordinator.id,
                        payload={"user_prompt": prompt, "intent": "chat"},
                        requires_response=False,
                    )
                ],
            )
            return self.store.save(swarm)

        plan_spec = get_experimental_task_spec("plan_reused")
        create_spec = get_experimental_task_spec("create_readme")
        review_spec = get_experimental_task_spec("review_readme")
        consolidate_spec = get_experimental_task_spec("consolidate_final")

        coordinator = AgentContract(
            role="CoordinatorAgent",
            objective="Coordinate the swarm, maintain task state, request reviews, and consolidate evidence.",
            allowed_tools=list(consolidate_spec.allowed_tools),
            acceptance_criteria=["Every completed task has evidence.", "Final result cites artifacts."],
            output_contract=dict(consolidate_spec.output_contract),
        )
        planner = AgentContract(
            role="PlannerAgent",
            objective="Translate the user instruction into a small executable Task DAG.",
            allowed_tools=list(plan_spec.allowed_tools),
            acceptance_criteria=["Tasks have clear dependencies and acceptance criteria."],
            output_contract=dict(plan_spec.output_contract),
        )
        worker = AgentContract(
            role="DocumentationAgent",
            objective="Create or update documentation artifacts using real filesystem tools.",
            allowed_tools=list(create_spec.allowed_tools),
            acceptance_criteria=["README.md exists in the workspace.", "Artifact path is submitted."],
            output_contract=dict(create_spec.output_contract),
        )
        reviewer = AgentContract(
            role="ReviewerAgent",
            objective="Validate submitted artifacts by reading them with real tools and reporting evidence.",
            allowed_tools=list(review_spec.allowed_tools),
            acceptance_criteria=["Reviewer reads README.md.", "Reviewer returns approval or rejection with evidence."],
            output_contract=dict(review_spec.output_contract),
        )

        plan_task = TaskNode(
            title=plan_spec.title,
            objective="Create or reuse a minimal plan for the requested work.",
            assigned_contract_id=planner.id,
        )
        write_task = TaskNode(
            title=create_spec.title,
            objective="Create a basic README.md in the workspace using a real write tool.",
            assigned_contract_id=worker.id,
            depends_on=[plan_task.id],
        )
        review_task = TaskNode(
            title=review_spec.title,
            objective="Read README.md with a real read tool and validate the artifact.",
            assigned_contract_id=reviewer.id,
            depends_on=[write_task.id],
        )
        consolidate_task = TaskNode(
            title=consolidate_spec.title,
            objective="Summarize work, artifacts, reviewer result, and evidence for the user.",
            assigned_contract_id=coordinator.id,
            depends_on=[review_task.id],
        )

        swarm = SwarmState(
            title=self._derive_title(prompt),
            user_prompt=prompt,
            intent="task",
            dashboard_id=dashboard_id,
            workspace_path=workspace_path,
            coordinator_contract_id=coordinator.id,
            contracts=[coordinator, planner, worker, reviewer],
            tasks=[plan_task, write_task, review_task, consolidate_task],
            messages=[
                AgentToAgentMessage(
                    type="broadcast_to_swarm",
                    from_agent_id=coordinator.id,
                    payload={"user_prompt": prompt},
                    requires_response=False,
                )
            ],
        )
        return self.store.save(swarm)

    def ensure_readme_dag(self, *, swarm_id: str) -> SwarmState:
        swarm = self.store.load(swarm_id)
        if swarm.tasks:
            return swarm

        create_spec = get_experimental_task_spec("create_readme")
        review_spec = get_experimental_task_spec("review_readme")
        consolidate_spec = get_experimental_task_spec("consolidate_final")

        coordinator = AgentContract(
            role="CoordinatorAgent",
            objective="Coordinate the swarm, maintain task state, request reviews, and consolidate evidence.",
            allowed_tools=list(consolidate_spec.allowed_tools),
            acceptance_criteria=["Every completed task has evidence.", "Final result cites artifacts."],
            output_contract=dict(consolidate_spec.output_contract),
        )
        worker = AgentContract(
            role="DocumentationAgent",
            objective="Create or update documentation artifacts using real filesystem tools.",
            allowed_tools=list(create_spec.allowed_tools),
            acceptance_criteria=["README.md exists in the workspace.", "Artifact path is submitted."],
            output_contract=dict(create_spec.output_contract),
        )
        reviewer = AgentContract(
            role="ReviewerAgent",
            objective="Validate submitted artifacts by reading them with real tools and reporting evidence.",
            allowed_tools=list(review_spec.allowed_tools),
            acceptance_criteria=["Reviewer reads README.md.", "Reviewer returns approval or rejection with evidence."],
            output_contract=dict(review_spec.output_contract),
        )

        write_task = TaskNode(
            title=create_spec.title,
            objective="Create a basic README.md in the workspace using a real write tool.",
            assigned_contract_id=worker.id,
        )
        review_task = TaskNode(
            title=review_spec.title,
            objective="Read README.md with a real read tool and validate the artifact.",
            assigned_contract_id=reviewer.id,
            depends_on=[write_task.id],
        )
        consolidate_task = TaskNode(
            title=consolidate_spec.title,
            objective="Summarize work, artifacts, reviewer result, and evidence for the user.",
            assigned_contract_id=coordinator.id,
            depends_on=[review_task.id],
        )

        swarm.intent = "task"
        swarm.coordinator_contract_id = coordinator.id
        swarm.contracts.extend([coordinator, worker, reviewer])
        swarm.tasks.extend([write_task, review_task, consolidate_task])
        swarm.messages.append(
            AgentToAgentMessage(
                type="broadcast_to_swarm",
                from_agent_id=coordinator.id,
                payload={"message": "implementation_dag_created", "source": "start_implementation"},
                requires_response=False,
            )
        )
        return self.store.save(swarm)

    def submit_artifact(
        self,
        *,
        swarm_id: str,
        from_agent_id: str,
        task_id: str,
        artifact: dict,
    ) -> SwarmState:
        swarm = self.store.load(swarm_id)
        swarm.artifacts.append(artifact)
        for task in swarm.tasks:
            if task.id == task_id:
                task.artifacts.append(artifact)
                if path := artifact.get("path"):
                    if path not in task.touched_files:
                        task.touched_files.append(path)
                break
        swarm.messages.append(
            AgentToAgentMessage(
                type="submit_artifact",
                from_agent_id=from_agent_id,
                task_id=task_id,
                payload=artifact,
                artifact_refs=[str(artifact.get("id") or artifact.get("path") or "")],
            )
        )
        return self.store.save(swarm)

    def request_review(
        self,
        *,
        swarm_id: str,
        from_agent_id: str,
        to_agent_id: str,
        task_id: str,
        artifact_refs: list[str],
    ) -> SwarmState:
        swarm = self.store.load(swarm_id)
        swarm.messages.append(
            AgentToAgentMessage(
                type="request_review",
                from_agent_id=from_agent_id,
                to_agent_id=to_agent_id,
                task_id=task_id,
                artifact_refs=artifact_refs,
                requires_response=True,
            )
        )
        return self.store.save(swarm)

    def update_status(self, *, swarm_id: str, status: SwarmStatus) -> SwarmState:
        swarm = self.store.load(swarm_id)
        swarm.status = status
        return self.store.save(swarm)

    @staticmethod
    def _classify_intent(prompt: str) -> str:
        normalized = " ".join((prompt or "").strip().lower().split())
        task_markers = (
            "crea ",
            "crear ",
            "creá ",
            "modifica ",
            "modificar ",
            "modificá ",
            "edita ",
            "editar ",
            "editá ",
            "implementa ",
            "implementar ",
            "implementá ",
            "agrega ",
            "agregar ",
            "agregá ",
            "corrige ",
            "corregir ",
            "corregí ",
            "genera ",
            "generar ",
            "generá ",
            "haz ",
            "hacer ",
            "hacé ",
            "build ",
            "fix ",
            "create ",
            "modify ",
            "edit ",
            "implement ",
            "add ",
            "generate ",
        )
        chat_markers = (
            "que es ",
            "qué es ",
            "como funciona",
            "cómo funciona",
            "explica ",
            "explicame ",
            "explícame ",
            "porque ",
            "por qué ",
            "cuanto ",
            "cuánto ",
            "cual ",
            "cuál ",
            "what is ",
            "how does ",
            "explain ",
        )
        if normalized.startswith(task_markers):
            return "task"
        if normalized.startswith(chat_markers) or normalized.endswith("?"):
            return "chat"
        return "chat"

    @staticmethod
    def _derive_title(prompt: str) -> str:
        text = " ".join(prompt.split())
        return text[:80] or "Swarm"


swarm_orchestrator = SwarmOrchestrator()
