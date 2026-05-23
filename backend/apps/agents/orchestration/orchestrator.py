"""Minimal non-executing Swarm Orchestrator.

Creates Coordinator/Planner/Worker/Reviewer contracts and a durable Task DAG
for the mandatory README-review MVP shape. It does not launch sessions yet.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from backend.apps.agents.orchestration.models import (
    AgentContract,
    AgentToAgentMessage,
    SwarmStatus,
    SwarmState,
    TaskNode,
)
from backend.apps.agents.orchestration.store import SwarmStore, swarm_store
from backend.apps.agents.runtime.experimental_task_type_registry import (
    ExperimentalTaskContractValidationError,
    classify_experimental_task,
    get_experimental_task_spec,
    validate_experimental_task_contract,
)


class SwarmOrchestrator:
    def __init__(self, store: SwarmStore | None = None) -> None:
        self.store = store or swarm_store

    @staticmethod
    def _slugify_workspace_title(title: str) -> str:
        normalized = (title or "openswarm-project").strip().lower()
        replacements = {
            "á": "a",
            "é": "e",
            "í": "i",
            "ó": "o",
            "ú": "u",
            "ü": "u",
            "ñ": "n",
        }
        for source, target in replacements.items():
            normalized = normalized.replace(source, target)
        normalized = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
        return (normalized or "openswarm-project")[:72].strip("-") or "openswarm-project"

    def _default_workspace_path(self, swarm: SwarmState) -> str:
        slug = self._slugify_workspace_title(swarm.title)
        folder_name = f"{slug}-{swarm.id[:8]}"
        workspace = Path.home() / ".openswarm" / "workspaces" / folder_name
        workspace.mkdir(parents=True, exist_ok=True)
        return str(workspace)

    def _ensure_workspace_path(self, swarm: SwarmState) -> SwarmState:
        if not swarm.workspace_path:
            swarm.workspace_path = self._default_workspace_path(swarm)
        return swarm

    def create_swarm(
        self,
        *,
        user_prompt: str,
        dashboard_id: str | None = None,
        workspace_path: str | None = None,
        intent: str | None = None,
    ) -> SwarmState:
        prompt = (user_prompt or "").strip()
        if not prompt:
            raise ValueError("user_prompt is required")

        requested_intent = (intent or "").strip().lower()
        if requested_intent and requested_intent not in {"chat", "task"}:
            raise ValueError("intent must be 'chat' or 'task'")
        intent = requested_intent or self._classify_intent(prompt)

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
            self._ensure_workspace_path(swarm)
            return self.store.save(swarm)

        plan_summary = f"Initial task request: {prompt}"
        app_type = "app"
        main_goal = prompt
        frontend = "frontend not defined"
        backend = "backend not defined"
        database = "database not defined"
        mvp_priority = "MVP priority not defined"
        out_of_scope = "out of scope not defined"

        plan_spec = get_experimental_task_spec("plan_reused")
        architecture_spec = get_experimental_task_spec("architecture_plan_execute")
        frontend_spec = get_experimental_task_spec("frontend_plan_execute")
        backend_spec = get_experimental_task_spec("backend_plan_execute")
        security_spec = get_experimental_task_spec("security_review_execute")
        create_spec = get_experimental_task_spec("create_readme")
        review_spec = get_experimental_task_spec("review_readme")
        consolidate_spec = get_experimental_task_spec("consolidate_final")
        validation_spec = get_experimental_task_spec("validation_execute")

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
        architect = AgentContract(
            role="ArchitectAgent",
            objective="Generate a safe architecture plan from the project intake without using tools.",
            allowed_tools=list(architecture_spec.allowed_tools),
            acceptance_criteria=["Architecture plan is ready.", "Architecture output includes components, constraints, and risks."],
            output_contract=dict(architecture_spec.output_contract),
        )
        frontend_planner = AgentContract(
            role="FrontendAgent",
            objective="Generate a safe frontend plan from architecture without using tools.",
            allowed_tools=list(frontend_spec.allowed_tools),
            acceptance_criteria=["Frontend plan is ready.", "Frontend output includes components, routes, constraints, and risks."],
            output_contract=dict(frontend_spec.output_contract),
        )
        backend_planner = AgentContract(
            role="BackendAgent",
            objective="Generate a safe backend plan from architecture without using tools.",
            allowed_tools=list(backend_spec.allowed_tools),
            acceptance_criteria=["Backend plan is ready.", "Backend output includes services, data models, API endpoints, constraints, and risks."],
            output_contract=dict(backend_spec.output_contract),
        )
        security_reviewer = AgentContract(
            role="SecurityAgent",
            objective="Generate a safe security review from architecture, frontend plan, and backend plan without using tools.",
            allowed_tools=list(security_spec.allowed_tools),
            acceptance_criteria=["Security review is ready.", "Security output includes findings, constraints, and risks."],
            output_contract=dict(security_spec.output_contract),
        )
        worker = AgentContract(
            role="DocumentationAgent",
            objective="Create or update documentation artifacts using real filesystem tools.",
            allowed_tools=list(create_spec.allowed_tools),
            acceptance_criteria=["Implementation brief README.md exists in the workspace.", "Artifact path is submitted."],
            output_contract=dict(create_spec.output_contract),
        )
        reviewer = AgentContract(
            role="ReviewerAgent",
            objective="Validate submitted artifacts by reading them with real tools and reporting evidence.",
            allowed_tools=list(review_spec.allowed_tools),
            acceptance_criteria=["Reviewer reads the implementation brief README.md.", "Reviewer returns approval or rejection with evidence."],
            output_contract=dict(review_spec.output_contract),
        )
        tester = AgentContract(
            role="TesterAgent",
            objective="Run strictly allowlisted validation commands with SafeShell.",
            allowed_tools=list(validation_spec.allowed_tools),
            acceptance_criteria=["Validation runs only allowlisted SafeShell commands.", "Validation produces command evidence."],
            output_contract=dict(validation_spec.output_contract),
        )

        plan_task = TaskNode(
            title=plan_spec.title,
            objective="Create or reuse a minimal plan for the requested work.",
            assigned_contract_id=planner.id,
        )
        architecture_task = TaskNode(
            title=architecture_spec.title,
            objective=(
                "Generate an architecture plan from the project intake before creating artifacts. "
                f"Use the intake context: {plan_summary} "
                f"App type: {app_type}. Main goal: {main_goal}. "
                f"Stack: {frontend} + {backend} + {database}. "
                f"MVP priority: {mvp_priority}. Out of scope: {out_of_scope}."
            ),
            assigned_contract_id=architect.id,
            depends_on=[plan_task.id],
        )
        frontend_plan_task = TaskNode(
            title=frontend_spec.title,
            objective=(
                "Generate a frontend plan from the architecture plan before creating artifacts. "
                f"Use the intake context: {plan_summary} "
                f"Frontend: {frontend}. MVP priority: {mvp_priority}. Out of scope: {out_of_scope}."
            ),
            assigned_contract_id=frontend_planner.id,
            depends_on=[architecture_task.id],
        )
        backend_plan_task = TaskNode(
            title=backend_spec.title,
            objective=(
                "Generate a backend plan from the architecture plan before creating artifacts. "
                f"Use the intake context: {plan_summary} "
                f"Backend: {backend}. Database: {database}. MVP priority: {mvp_priority}. Out of scope: {out_of_scope}."
            ),
            assigned_contract_id=backend_planner.id,
            depends_on=[frontend_plan_task.id],
        )
        security_review_task = TaskNode(
            title=security_spec.title,
            objective=(
                "Generate a security review from the architecture, frontend, and backend plans before creating artifacts. "
                f"Use the intake context: {plan_summary} "
                f"Stack: {frontend} + {backend} + {database}. MVP priority: {mvp_priority}. Out of scope: {out_of_scope}."
            ),
            assigned_contract_id=security_reviewer.id,
            depends_on=[backend_plan_task.id],
        )
        write_task = TaskNode(
            title=create_spec.title,
            objective="Create a basic README.md in the workspace using a real write tool.",
            assigned_contract_id=worker.id,
            depends_on=[security_review_task.id],
        )
        review_task = TaskNode(
            title=review_spec.title,
            objective="Read README.md with a real read tool and validate the artifact.",
            assigned_contract_id=reviewer.id,
            depends_on=[write_task.id],
        )
        validation_task = TaskNode(
            title=validation_spec.title,
            objective="Run safe validation checks after reviewer approval and before final consolidation.",
            assigned_contract_id=tester.id,
            depends_on=[review_task.id],
        )
        consolidate_task = TaskNode(
            title=consolidate_spec.title,
            objective="Summarize work, artifacts, reviewer result, validation result, and evidence for the user.",
            assigned_contract_id=coordinator.id,
            depends_on=[validation_task.id],
        )

        swarm = SwarmState(
            title=self._derive_title(prompt),
            user_prompt=prompt,
            intent="task",
            dashboard_id=dashboard_id,
            workspace_path=workspace_path,
            coordinator_contract_id=coordinator.id,
            contracts=[coordinator, planner, architect, frontend_planner, backend_planner, security_reviewer, worker, reviewer, tester],
            tasks=[
                plan_task,
                architecture_task,
                frontend_plan_task,
                backend_plan_task,
                security_review_task,
                write_task,
                review_task,
                validation_task,
                consolidate_task,
            ],
            messages=[
                AgentToAgentMessage(
                    type="broadcast_to_swarm",
                    from_agent_id=coordinator.id,
                    payload={"user_prompt": prompt},
                    requires_response=False,
                )
            ],
        )
        self._ensure_workspace_path(swarm)
        return self.store.save(swarm)

    @staticmethod
    def _normalize_generated_plan(generated_plan: dict | None, *, defaults: dict[str, str] | None = None) -> dict[str, str]:
        source = generated_plan if isinstance(generated_plan, dict) else {}
        fallback = defaults or {}
        normalized = {
            "summary": str(source.get("summary") or fallback.get("summary") or "Plan generated from project intake."),
            "app_type": str(source.get("app_type") or fallback.get("app_type") or "app"),
            "main_goal": str(source.get("main_goal") or fallback.get("main_goal") or "build the requested MVP"),
            "frontend": str(source.get("frontend") or fallback.get("frontend") or "frontend not defined"),
            "backend": str(source.get("backend") or fallback.get("backend") or "backend not defined"),
            "database": str(source.get("database") or fallback.get("database") or "database not defined"),
            "mvp_priority": str(source.get("mvp_priority") or fallback.get("mvp_priority") or "MVP priority not defined"),
            "out_of_scope": str(source.get("out_of_scope") or fallback.get("out_of_scope") or "out of scope not defined"),
            "visual_style": str(source.get("visual_style") or fallback.get("visual_style") or "clean modern UI"),
        }
        return normalized

    @staticmethod
    def _select_dag_template(normalized_plan: dict[str, str]) -> str:
        app_type = normalized_plan.get("app_type", "").lower()
        frontend = normalized_plan.get("frontend", "").lower()
        backend = normalized_plan.get("backend", "").lower()
        database = normalized_plan.get("database", "").lower()

        static_signals = ["static", "html", "css", "landing", "tutorial", "brochure"]
        no_backend_signals = ["no backend", "none", "static", "sin backend"]
        no_database_signals = ["no database", "none", "static", "sin database"]

        if (
            any(signal in app_type or signal in frontend for signal in static_signals)
            and any(signal in backend for signal in no_backend_signals)
            and any(signal in database for signal in no_database_signals)
        ):
            return "static_app"

        return "implementation_brief"

    def ensure_static_app_dag(self, *, swarm_id: str, generated_plan: dict | None = None) -> SwarmState:
        swarm = self.store.load(swarm_id)
        self._ensure_workspace_path(swarm)
        if swarm.tasks:
            return self.store.save(swarm)

        plan = self._normalize_generated_plan(
            generated_plan,
            defaults={
                "summary": "Plan generated from project intake.",
                "app_type": "web app",
                "main_goal": "build a static app",
                "frontend": "HTML/CSS",
                "backend": "no backend",
                "database": "no database",
                "mvp_priority": "static MVP",
                "out_of_scope": "out of scope not defined",
                "visual_style": "clean modern UI",
            },
        )
        plan_summary = plan["summary"]
        app_type = plan["app_type"]
        main_goal = plan["main_goal"]
        frontend = plan["frontend"]
        backend = plan["backend"]
        database = plan["database"]
        mvp_priority = plan["mvp_priority"]
        out_of_scope = plan["out_of_scope"]
        visual_style = plan["visual_style"]

        architecture_spec = get_experimental_task_spec("architecture_plan_execute")
        frontend_spec = get_experimental_task_spec("frontend_plan_execute")
        backend_spec = get_experimental_task_spec("backend_plan_execute")
        security_spec = get_experimental_task_spec("security_review_execute")
        create_spec = get_experimental_task_spec("create_static_app")
        review_spec = get_experimental_task_spec("review_static_app")
        consolidate_spec = get_experimental_task_spec("consolidate_final")
        validation_spec = get_experimental_task_spec("validation_execute")

        coordinator = AgentContract(
            role="CoordinatorAgent",
            objective="Coordinate the static app build, maintain task state, and consolidate evidence.",
            allowed_tools=list(consolidate_spec.allowed_tools),
            acceptance_criteria=["Every completed task has evidence.", "Final result cites created static app artifacts."],
            output_contract=dict(consolidate_spec.output_contract),
        )
        architect = AgentContract(
            role="ArchitectAgent",
            objective="Generate a safe architecture plan from the project intake without using tools.",
            allowed_tools=list(architecture_spec.allowed_tools),
            acceptance_criteria=["Architecture plan is ready.", "Architecture output includes components, constraints, and risks."],
            output_contract=dict(architecture_spec.output_contract),
        )
        frontend_planner = AgentContract(
            role="FrontendAgent",
            objective="Generate a safe frontend plan for a static app from architecture without using tools.",
            allowed_tools=list(frontend_spec.allowed_tools),
            acceptance_criteria=["Frontend plan is ready.", "Frontend output includes static routes, content sections, constraints, and risks."],
            output_contract=dict(frontend_spec.output_contract),
        )
        backend_planner = AgentContract(
            role="BackendAgent",
            objective="Confirm backend scope for the static app without using tools.",
            allowed_tools=list(backend_spec.allowed_tools),
            acceptance_criteria=["Backend plan is ready.", "Backend output confirms no backend work unless intake requires it."],
            output_contract=dict(backend_spec.output_contract),
        )
        security_reviewer = AgentContract(
            role="SecurityAgent",
            objective="Generate a safe security review for static app files without using tools.",
            allowed_tools=list(security_spec.allowed_tools),
            acceptance_criteria=["Security review is ready.", "Security output includes static-app constraints and risks."],
            output_contract=dict(security_spec.output_contract),
        )
        static_builder = AgentContract(
            role="FrontendAgent",
            objective="Create static app files using controlled filesystem tools only.",
            allowed_tools=list(create_spec.allowed_tools),
            acceptance_criteria=[
                "index.html, styles.css, and content.json exist in the workspace.",
                "index.html references only existing local files.",
                "Content describes OpenSwarm as local-first agent orchestration without prohibited product claims.",
                "Static app artifact paths are submitted with evidence.",
            ],
            output_contract=dict(create_spec.output_contract),
        )
        reviewer = AgentContract(
            role="ReviewerAgent",
            objective="Validate created static app files by reading them with real tools and reporting evidence.",
            allowed_tools=list(review_spec.allowed_tools),
            acceptance_criteria=[
                "Reviewer reads index.html, styles.css, and content.json.",
                "Reviewer rejects missing files, missing referenced files, prohibited claims, or incomplete required sections.",
                "Reviewer returns approval or rejection with evidence.",
            ],
            output_contract=dict(review_spec.output_contract),
        )
        tester = AgentContract(
            role="TesterAgent",
            objective="Run strictly allowlisted validation checks or safe artifact validation.",
            allowed_tools=list(validation_spec.allowed_tools),
            acceptance_criteria=["Validation uses only safe checks.", "Validation produces evidence."],
            output_contract=dict(validation_spec.output_contract),
        )

        architecture_task = TaskNode(
            title=architecture_spec.title,
            objective=(
                "Generate an architecture plan from the project intake before creating static app files. "
                f"Use the intake context: {plan_summary} "
                f"App type: {app_type}. Main goal: {main_goal}. "
                f"Stack: {frontend} + {backend} + {database}. "
                f"MVP priority: {mvp_priority}. Out of scope: {out_of_scope}."
            ),
            assigned_contract_id=architect.id,
        )
        frontend_plan_task = TaskNode(
            title=frontend_spec.title,
            objective=(
                "Generate a frontend plan for the static app before creating files. "
                f"Use the intake context: {plan_summary} "
                f"Frontend: {frontend}. Visual style: {visual_style}. "
                f"MVP priority: {mvp_priority}. Out of scope: {out_of_scope}."
            ),
            assigned_contract_id=frontend_planner.id,
            depends_on=[architecture_task.id],
        )
        backend_plan_task = TaskNode(
            title=backend_spec.title,
            objective=(
                "Confirm backend scope for this static app before creating files. "
                f"Backend: {backend}. Database: {database}. MVP priority: {mvp_priority}. Out of scope: {out_of_scope}."
            ),
            assigned_contract_id=backend_planner.id,
            depends_on=[frontend_plan_task.id],
        )
        security_review_task = TaskNode(
            title=security_spec.title,
            objective=(
                "Generate a security review for the static app before creating files. "
                f"Stack: {frontend} + {backend} + {database}. MVP priority: {mvp_priority}. Out of scope: {out_of_scope}."
            ),
            assigned_contract_id=security_reviewer.id,
            depends_on=[backend_plan_task.id],
        )
        create_task = TaskNode(
            title=create_spec.title,
            objective=(
                "Create a real static web app in the workspace using controlled file tools only. "
                "Create index.html, styles.css, and content.json as mandatory artifacts. "
                "index.html may reference styles.css and content.json only because those files must also be created. "
                "Describe OpenSwarm accurately as a local-first application for coordinating AI agents on the user's machine, "
                "with dashboards/SwarmCard, orchestrator chat, tasks/cards/DAG, controlled tools, approvals, artifacts, evidence, final_result, "
                "and local models such as Ollama when possible. "
                "Do not claim generic distributed computing, cloud-first operation, automatic scalability, high availability, cost effectiveness, copyright, or invented years. "
                "Do not use shell, npm, package managers, external CDNs, network calls, or backend code. "
                f"Use the intake context: {plan_summary} "
                f"Main goal: {main_goal}. Frontend: {frontend}. Visual style: {visual_style}. "
                f"MVP priority: {mvp_priority}. Out of scope: {out_of_scope}."
            ),
            assigned_contract_id=static_builder.id,
            depends_on=[security_review_task.id],
        )
        review_task = TaskNode(
            title=review_spec.title,
            objective=(
                "Read index.html, styles.css, and content.json with a real read tool. Reject if any required file is missing, "
                "index.html references a missing file, content uses prohibited product claims or invented years, required sections "
                "(Características, Ventajas, Próximos pasos) are missing, or required mentions are missing: local-first, agentes de IA, "
                "dashboards/SwarmCard, tools, evidence, and final_result."
            ),
            assigned_contract_id=reviewer.id,
            depends_on=[create_task.id],
        )
        validation_task = TaskNode(
            title=validation_spec.title,
            objective="Run safe validation checks before final consolidation.",
            assigned_contract_id=tester.id,
            depends_on=[review_task.id],
        )
        consolidate_task = TaskNode(
            title=consolidate_spec.title,
            objective="Summarize created static app files, reviewer result, validation result, evidence, and claim guard status for the user.",
            assigned_contract_id=coordinator.id,
            depends_on=[validation_task.id],
        )

        swarm.intent = "task"
        swarm.coordinator_contract_id = coordinator.id
        swarm.contracts = [coordinator, architect, frontend_planner, backend_planner, security_reviewer, static_builder, reviewer, tester]
        swarm.tasks = [architecture_task, frontend_plan_task, backend_plan_task, security_review_task, create_task, review_task, validation_task, consolidate_task]
        swarm.messages.append(
            AgentToAgentMessage(
                type="broadcast_to_swarm",
                from_agent_id=coordinator.id,
                payload={
                    "message": "static_app_dag_created",
                    "source": "start_implementation",
                    "generated_plan_used": bool(plan),
                    "generated_plan_summary": plan_summary,
                },
                requires_response=False,
            )
        )
        return self.store.save(swarm)


    def ensure_readme_dag(self, *, swarm_id: str, generated_plan: dict | None = None) -> SwarmState:
        swarm = self.store.load(swarm_id)
        self._ensure_workspace_path(swarm)
        if swarm.tasks:
            return self.store.save(swarm)

        plan = self._normalize_generated_plan(
            generated_plan,
            defaults={
                "summary": "Plan generated from project intake.",
                "app_type": "app",
                "main_goal": "document the requested MVP",
                "frontend": "frontend not defined",
                "backend": "backend not defined",
                "database": "database not defined",
                "mvp_priority": "MVP priority not defined",
                "out_of_scope": "out of scope not defined",
            },
        )
        plan_summary = plan["summary"]
        app_type = plan["app_type"]
        main_goal = plan["main_goal"]
        frontend = plan["frontend"]
        backend = plan["backend"]
        database = plan["database"]
        mvp_priority = plan["mvp_priority"]
        out_of_scope = plan["out_of_scope"]

        architecture_spec = get_experimental_task_spec("architecture_plan_execute")
        frontend_spec = get_experimental_task_spec("frontend_plan_execute")
        backend_spec = get_experimental_task_spec("backend_plan_execute")
        security_spec = get_experimental_task_spec("security_review_execute")
        create_spec = get_experimental_task_spec("create_readme")
        review_spec = get_experimental_task_spec("review_readme")
        consolidate_spec = get_experimental_task_spec("consolidate_final")
        validation_spec = get_experimental_task_spec("validation_execute")

        coordinator = AgentContract(
            role="CoordinatorAgent",
            objective="Coordinate the swarm, maintain task state, request reviews, and consolidate evidence.",
            allowed_tools=list(consolidate_spec.allowed_tools),
            acceptance_criteria=["Every completed task has evidence.", "Final result cites artifacts."],
            output_contract=dict(consolidate_spec.output_contract),
        )
        architect = AgentContract(
            role="ArchitectAgent",
            objective="Generate a safe architecture plan from the project intake without using tools.",
            allowed_tools=list(architecture_spec.allowed_tools),
            acceptance_criteria=["Architecture plan is ready.", "Architecture output includes components, constraints, and risks."],
            output_contract=dict(architecture_spec.output_contract),
        )
        frontend_planner = AgentContract(
            role="FrontendAgent",
            objective="Generate a safe frontend plan from architecture without using tools.",
            allowed_tools=list(frontend_spec.allowed_tools),
            acceptance_criteria=["Frontend plan is ready.", "Frontend output includes components, routes, constraints, and risks."],
            output_contract=dict(frontend_spec.output_contract),
        )
        backend_planner = AgentContract(
            role="BackendAgent",
            objective="Generate a safe backend plan from architecture without using tools.",
            allowed_tools=list(backend_spec.allowed_tools),
            acceptance_criteria=["Backend plan is ready.", "Backend output includes services, data models, API endpoints, constraints, and risks."],
            output_contract=dict(backend_spec.output_contract),
        )
        security_reviewer = AgentContract(
            role="SecurityAgent",
            objective="Generate a safe security review from architecture, frontend plan, and backend plan without using tools.",
            allowed_tools=list(security_spec.allowed_tools),
            acceptance_criteria=["Security review is ready.", "Security output includes findings, constraints, and risks."],
            output_contract=dict(security_spec.output_contract),
        )
        worker = AgentContract(
            role="DocumentationAgent",
            objective="Create or update documentation artifacts using real filesystem tools.",
            allowed_tools=list(create_spec.allowed_tools),
            acceptance_criteria=["Implementation brief README.md exists in the workspace.", "Artifact path is submitted."],
            output_contract=dict(create_spec.output_contract),
        )
        reviewer = AgentContract(
            role="ReviewerAgent",
            objective="Validate submitted artifacts by reading them with real tools and reporting evidence.",
            allowed_tools=list(review_spec.allowed_tools),
            acceptance_criteria=["Reviewer reads the implementation brief README.md.", "Reviewer returns approval or rejection with evidence."],
            output_contract=dict(review_spec.output_contract),
        )
        tester = AgentContract(
            role="TesterAgent",
            objective="Run strictly allowlisted validation commands with SafeShell.",
            allowed_tools=list(validation_spec.allowed_tools),
            acceptance_criteria=["Validation runs only allowlisted SafeShell commands.", "Validation produces command evidence."],
            output_contract=dict(validation_spec.output_contract),
        )

        architecture_task = TaskNode(
            title=architecture_spec.title,
            objective=(
                "Generate an architecture plan from the project intake before creating artifacts. "
                f"Use the intake context: {plan_summary} "
                f"App type: {app_type}. Main goal: {main_goal}. "
                f"Stack: {frontend} + {backend} + {database}. "
                f"MVP priority: {mvp_priority}. Out of scope: {out_of_scope}."
            ),
            assigned_contract_id=architect.id,
        )
        frontend_plan_task = TaskNode(
            title=frontend_spec.title,
            objective=(
                "Generate a frontend plan from the architecture plan before creating artifacts. "
                f"Use the intake context: {plan_summary} "
                f"Frontend: {frontend}. MVP priority: {mvp_priority}. Out of scope: {out_of_scope}."
            ),
            assigned_contract_id=frontend_planner.id,
            depends_on=[architecture_task.id],
        )
        backend_plan_task = TaskNode(
            title=backend_spec.title,
            objective=(
                "Generate a backend plan from the architecture plan before creating artifacts. "
                f"Use the intake context: {plan_summary} "
                f"Backend: {backend}. Database: {database}. MVP priority: {mvp_priority}. Out of scope: {out_of_scope}."
            ),
            assigned_contract_id=backend_planner.id,
            depends_on=[frontend_plan_task.id],
        )
        security_review_task = TaskNode(
            title=security_spec.title,
            objective=(
                "Generate a security review from the architecture, frontend, and backend plans before creating artifacts. "
                f"Use the intake context: {plan_summary} "
                f"Stack: {frontend} + {backend} + {database}. MVP priority: {mvp_priority}. Out of scope: {out_of_scope}."
            ),
            assigned_contract_id=security_reviewer.id,
            depends_on=[backend_plan_task.id],
        )
        write_task = TaskNode(
            title=create_spec.title,
            objective=(
                "Create an implementation brief README.md in the workspace using a real write tool. This is documentation only; do not claim that frontend/backend app files were implemented. "
                f"Use the project intake plan as source context: {plan_summary} "
                f"App type: {app_type}. Main goal: {main_goal}. "
                f"Stack: {frontend} + {backend} + {database}. "
                f"MVP priority: {mvp_priority}. Out of scope: {out_of_scope}."
            ),
            assigned_contract_id=worker.id,
            depends_on=[security_review_task.id],
        )
        review_task = TaskNode(
            title=review_spec.title,
            objective=(
                "Read the implementation brief README.md with a real read tool and validate that it reflects the project intake plan, "
                "including stack, MVP priority, and out-of-scope constraints."
            ),
            assigned_contract_id=reviewer.id,
            depends_on=[write_task.id],
        )
        validation_task = TaskNode(
            title=validation_spec.title,
            objective="Run safe validation checks before final consolidation.",
            assigned_contract_id=tester.id,
            depends_on=[review_task.id],
        )
        consolidate_task = TaskNode(
            title=consolidate_spec.title,
            objective="Summarize work, artifacts, reviewer result, validation result, evidence, and claim guard status for the user.",
            assigned_contract_id=coordinator.id,
            depends_on=[validation_task.id],
        )

        swarm.intent = "task"
        swarm.coordinator_contract_id = coordinator.id
        swarm.contracts = [coordinator, architect, frontend_planner, backend_planner, security_reviewer, worker, reviewer, tester]
        swarm.tasks = [architecture_task, frontend_plan_task, backend_plan_task, security_review_task, write_task, review_task, validation_task, consolidate_task]
        swarm.messages.append(
            AgentToAgentMessage(
                type="broadcast_to_swarm",
                from_agent_id=coordinator.id,
                payload={
                    "message": "implementation_dag_created",
                    "source": "start_implementation",
                    "generated_plan_used": bool(plan),
                    "generated_plan_summary": plan_summary,
                },
                requires_response=False,
            )
        )
        return self.store.save(swarm)

    def ensure_specialized_agent_contracts(self, *, swarm_id: str, generated_plan: dict | None = None) -> SwarmState:
        swarm = self.store.load(swarm_id)
        plan = generated_plan if isinstance(generated_plan, dict) else {}

        existing_roles = {contract.role for contract in swarm.contracts}
        frontend = str(plan.get("frontend") or "the selected frontend")
        backend = str(plan.get("backend") or "the selected backend")
        database = str(plan.get("database") or "the selected database")
        app_type = str(plan.get("app_type") or "the requested app")
        main_goal = str(plan.get("main_goal") or "the requested goal")

        contract_specs = [
            {
                "role": "ArchitectAgent",
                "objective": (
                    f"Translate the project intake into a safe implementation architecture for {app_type}. "
                    f"Main goal: {main_goal}."
                ),
                "allowed_tools": [],
                "acceptance_criteria": [
                    "Architecture decisions stay within the project intake scope.",
                    "No files are modified by this contract until executable task types exist.",
                ],
                "output_contract": {
                    "architecture_plan": {
                        "status": "draft|ready",
                        "summary": "string",
                        "constraints": [],
                    }
                },
            },
            {
                "role": "FrontendAgent",
                "objective": f"Prepare frontend implementation work for {frontend} without executing unsupported task types yet.",
                "allowed_tools": [],
                "acceptance_criteria": [
                    "Frontend scope reflects the generated plan.",
                    "No frontend files are modified until frontend task types are registered.",
                ],
                "output_contract": {
                    "frontend_plan": {
                        "status": "draft|ready",
                        "summary": "string",
                    }
                },
            },
            {
                "role": "BackendAgent",
                "objective": f"Prepare backend implementation work for {backend} with {database} without executing unsupported task types yet.",
                "allowed_tools": [],
                "acceptance_criteria": [
                    "Backend scope reflects the generated plan.",
                    "No backend files are modified until backend task types are registered.",
                ],
                "output_contract": {
                    "backend_plan": {
                        "status": "draft|ready",
                        "summary": "string",
                    }
                },
            },
            {
                "role": "TesterAgent",
                "objective": "Prepare validation strategy for the generated project without running unsupported shell commands yet.",
                "allowed_tools": [],
                "acceptance_criteria": [
                    "Validation plan is explicit.",
                    "No commands are executed until a safe shell task type exists.",
                ],
                "output_contract": {
                    "validation_plan": {
                        "status": "draft|ready",
                        "checks": [],
                    }
                },
            },
            {
                "role": "SecurityAgent",
                "objective": "Review implementation scope for local-first safety, path safety, secrets, and risky operations.",
                "allowed_tools": [],
                "acceptance_criteria": [
                    "Security review remains evidence-oriented.",
                    "No file or shell operation is executed by this dormant contract.",
                ],
                "output_contract": {
                    "security_review": {
                        "status": "draft|ready",
                        "risks": [],
                    }
                },
            },
        ]

        added_roles = []
        for spec in contract_specs:
            role = spec["role"]
            if role in existing_roles:
                continue
            swarm.contracts.append(
                AgentContract(
                    role=role,
                    objective=spec["objective"],
                    allowed_tools=list(spec["allowed_tools"]),
                    acceptance_criteria=list(spec["acceptance_criteria"]),
                    output_contract=dict(spec["output_contract"]),
                )
            )
            existing_roles.add(role)
            added_roles.append(role)

        if added_roles:
            swarm.messages.append(
                AgentToAgentMessage(
                    type="broadcast_to_swarm",
                    from_agent_id=swarm.coordinator_contract_id or swarm.contracts[0].id,
                    payload={
                        "message": "specialized_agent_contracts_created",
                        "source": "start_implementation",
                        "roles": added_roles,
                    },
                    requires_response=False,
                )
            )

        return self.store.save(swarm)

    def _build_model_dag_proposal_prompt(self, *, generated_plan: dict | None = None) -> str:
        plan = self._normalize_generated_plan(generated_plan)
        allowed_task_types = [
            "architecture_plan_execute",
            "frontend_plan_execute",
            "backend_plan_execute",
            "security_review_execute",
            "create_readme",
            "review_readme",
            "create_static_app",
            "review_static_app",
            "validation_execute",
            "consolidate_final",
        ]
        allowed_roles = [
            "CoordinatorAgent",
            "PlannerAgent",
            "ArchitectAgent",
            "BackendAgent",
            "FrontendAgent",
            "TesterAgent",
            "ReviewerAgent",
            "SecurityAgent",
            "DocumentationAgent",
        ]

        return (
            "Create a safe DAG proposal for OpenSwarm. Return JSON only. "
            "Do not execute tools. Do not create files. Do not include markdown. "
            "The backend will validate and may reject the proposal. "
            "You must not include allowed_tools or output_contract; backend derives those from TASK_TYPE_REGISTRY. "
            "Use only these task_type values: " + ', '.join(allowed_task_types) + ". "
            "Use only these role values: " + ', '.join(allowed_roles) + ". "
            "Each task must include id, task_type, role, title, objective, and optional depends_on array of existing task ids. "
            "Dependencies must form an acyclic graph. "
            "Use registry-compatible titles when possible. "
            "Return shape: {\"kind\":\"model_generated_dag\",\"tasks\":[...]} . "
            f"Project summary: {plan['summary']} "
            f"App type: {plan['app_type']}. Main goal: {plan['main_goal']}. "
            f"Frontend: {plan['frontend']}. Backend: {plan['backend']}. Database: {plan['database']}. "
            f"MVP priority: {plan['mvp_priority']}. Out of scope: {plan['out_of_scope']}. "
            f"Visual style: {plan['visual_style']}."
        )

    @staticmethod
    def _parse_model_dag_proposal(final_message: dict | str | None) -> tuple[dict | None, dict | None]:
        if isinstance(final_message, dict):
            content = str(final_message.get("content") or "").strip()
        else:
            content = str(final_message or "").strip()

        if not content:
            return None, {"error": "empty_model_dag_proposal_response"}

        try:
            data = json.loads(content)
        except Exception:
            match = re.search(r"\{.*\}", content, flags=re.S)
            if not match:
                return None, {
                    "error": "model_dag_proposal_response_not_json",
                    "raw": content[:500],
                }
            try:
                data = json.loads(match.group(0))
            except Exception:
                return None, {
                    "error": "model_dag_proposal_json_parse_failed",
                    "raw": content[:500],
                }

        if isinstance(data, dict) and isinstance(data.get("dag_proposal"), dict):
            data = data["dag_proposal"]

        if not isinstance(data, dict):
            return None, {"error": "model_dag_proposal_not_object"}

        if data.get("kind") not in {"model_generated_dag", "template_dag_proposal"}:
            return None, {
                "error": "model_dag_proposal_invalid_kind",
                "kind": data.get("kind"),
            }

        tasks = data.get("tasks")
        if not isinstance(tasks, list) or not tasks:
            return None, {"error": "model_dag_proposal_missing_tasks"}

        return data, None

    def _validate_model_dag_semantic_policy(
        self,
        *,
        proposal: dict,
        generated_plan: dict | None = None,
    ) -> list[dict]:
        plan = self._normalize_generated_plan(generated_plan)
        backend = plan.get("backend", "").lower()
        database = plan.get("database", "").lower()
        task_types = [
            str(item.get("task_type") or "")
            for item in (proposal.get("tasks") or [])
            if isinstance(item, dict)
        ]

        no_backend_signals = {"", "none", "no backend", "sin backend", "static", "backend not defined"}
        no_database_signals = {"", "none", "no database", "sin database", "static", "database not defined"}

        has_real_backend = backend not in no_backend_signals
        has_real_database = database not in no_database_signals

        errors: list[dict] = []
        if (has_real_backend or has_real_database) and "create_static_app" in task_types:
            errors.append(
                {
                    "error": "semantically_incompatible_task_type",
                    "task_type": "create_static_app",
                    "reason": "Model proposed static app creation for a plan with backend or database requirements.",
                    "backend": plan.get("backend"),
                    "database": plan.get("database"),
                }
            )

        return errors

    def _build_validated_model_dag_proposal_state(
        self,
        *,
        base_swarm: SwarmState,
        final_message: dict | str | None,
        generated_plan: dict | None = None,
    ) -> tuple[SwarmState, list[dict]]:
        proposal, parse_error = self._parse_model_dag_proposal(final_message)
        materialized = base_swarm.model_copy(deep=True)

        if parse_error:
            materialized = self._record_dag_proposal_decision(
                swarm=materialized,
                source="model_dag_proposal",
                proposal_kind="model_generated_dag",
                validation_errors=[parse_error],
                metadata={"parse_status": "failed"},
            )
            return materialized, [parse_error]

        materialized = self._materialize_dag_proposal_state(base_swarm=materialized, proposal=proposal or {})
        validation_errors = [
            *self._validate_dag_proposal_state(materialized),
            *self._validate_model_dag_semantic_policy(proposal=proposal or {}, generated_plan=generated_plan),
        ]
        proposal_tasks = [item for item in ((proposal or {}).get("tasks") or []) if isinstance(item, dict)]
        materialized = self._record_dag_proposal_decision(
            swarm=materialized,
            source="model_dag_proposal",
            proposal_kind=str((proposal or {}).get("kind") or "model_generated_dag"),
            validation_errors=validation_errors,
            metadata={
                "parse_status": "accepted",
                "task_count": len(proposal_tasks),
                "task_ids": [str(item.get("id") or "") for item in proposal_tasks],
                "task_types": [str(item.get("task_type") or "") for item in proposal_tasks],
                "roles": [str(item.get("role") or "") for item in proposal_tasks],
            },
        )
        return materialized, validation_errors

    def record_model_dag_proposal_preview(
        self,
        *,
        swarm_id: str,
        final_message: dict | str | None,
        generated_plan: dict | None = None,
    ) -> tuple[SwarmState, list[dict]]:
        swarm = self.store.load(swarm_id)
        materialized, validation_errors = self._build_validated_model_dag_proposal_state(
            base_swarm=swarm,
            final_message=final_message,
            generated_plan=generated_plan,
        )

        # Persist only proposal decisions. Do not persist model-generated tasks/contracts yet.
        swarm.decisions = materialized.decisions
        return self.store.save(swarm), validation_errors

    def _build_template_dag_proposal(self, *, template: str, generated_plan: dict | None = None) -> dict:
        plan = self._normalize_generated_plan(generated_plan)
        plan_summary = plan["summary"]
        app_type = plan["app_type"]
        main_goal = plan["main_goal"]
        frontend = plan["frontend"]
        backend = plan["backend"]
        database = plan["database"]
        mvp_priority = plan["mvp_priority"]
        out_of_scope = plan["out_of_scope"]
        visual_style = plan["visual_style"]

        common_prefix = [
            {
                "id": "architecture",
                "task_type": "architecture_plan_execute",
                "role": "ArchitectAgent",
                "title": get_experimental_task_spec("architecture_plan_execute").title,
                "objective": (
                    "Generate an architecture plan from the project intake before creating artifacts. "
                    f"Use the intake context: {plan_summary} "
                    f"App type: {app_type}. Main goal: {main_goal}. "
                    f"Stack: {frontend} + {backend} + {database}. "
                    f"MVP priority: {mvp_priority}. Out of scope: {out_of_scope}."
                ),
            },
            {
                "id": "frontend_plan",
                "task_type": "frontend_plan_execute",
                "role": "FrontendAgent",
                "title": get_experimental_task_spec("frontend_plan_execute").title,
                "objective": (
                    "Generate a frontend plan from the architecture plan before creating artifacts. "
                    f"Frontend: {frontend}. Visual style: {visual_style}. "
                    f"MVP priority: {mvp_priority}. Out of scope: {out_of_scope}."
                ),
                "depends_on": ["architecture"],
            },
            {
                "id": "backend_plan",
                "task_type": "backend_plan_execute",
                "role": "BackendAgent",
                "title": get_experimental_task_spec("backend_plan_execute").title,
                "objective": (
                    "Generate or confirm backend scope from the architecture plan before creating artifacts. "
                    f"Backend: {backend}. Database: {database}. MVP priority: {mvp_priority}. Out of scope: {out_of_scope}."
                ),
                "depends_on": ["frontend_plan"],
            },
            {
                "id": "security_review",
                "task_type": "security_review_execute",
                "role": "SecurityAgent",
                "title": get_experimental_task_spec("security_review_execute").title,
                "objective": (
                    "Generate a security review from architecture, frontend plan, and backend plan before creating artifacts. "
                    f"Stack: {frontend} + {backend} + {database}. MVP priority: {mvp_priority}. Out of scope: {out_of_scope}."
                ),
                "depends_on": ["backend_plan"],
            },
        ]

        if template == "static_app":
            implementation_tasks = [
                {
                    "id": "create_static_app",
                    "task_type": "create_static_app",
                    "role": "FrontendAgent",
                    "title": get_experimental_task_spec("create_static_app").title,
                    "objective": (
                        "Create a real static web app in the workspace using controlled file tools only. "
                        "Create index.html, styles.css, and content.json as mandatory artifacts. "
                        "Do not use shell, npm, package managers, external CDNs, network calls, or backend code. "
                        f"Main goal: {main_goal}. Frontend: {frontend}. Visual style: {visual_style}. "
                        f"MVP priority: {mvp_priority}. Out of scope: {out_of_scope}."
                    ),
                    "depends_on": ["security_review"],
                },
                {
                    "id": "review_static_app",
                    "task_type": "review_static_app",
                    "role": "ReviewerAgent",
                    "title": get_experimental_task_spec("review_static_app").title,
                    "objective": "Read and review created static app files with real read tools.",
                    "depends_on": ["create_static_app"],
                },
            ]
        elif template == "implementation_brief":
            implementation_tasks = [
                {
                    "id": "create_readme",
                    "task_type": "create_readme",
                    "role": "DocumentationAgent",
                    "title": get_experimental_task_spec("create_readme").title,
                    "objective": (
                        "Create an implementation brief README.md in the workspace using a real write tool. "
                        "This is documentation only; do not claim that frontend/backend app files were implemented. "
                        f"Use the project intake plan as source context: {plan_summary} "
                        f"App type: {app_type}. Main goal: {main_goal}. "
                        f"Stack: {frontend} + {backend} + {database}. "
                        f"MVP priority: {mvp_priority}. Out of scope: {out_of_scope}."
                    ),
                    "depends_on": ["security_review"],
                },
                {
                    "id": "review_readme",
                    "task_type": "review_readme",
                    "role": "ReviewerAgent",
                    "title": get_experimental_task_spec("review_readme").title,
                    "objective": "Read the implementation brief README.md with a real read tool and validate that it reflects the project intake plan.",
                    "depends_on": ["create_readme"],
                },
            ]
        else:
            raise ValueError(f"Unknown DAG template: {template}")

        suffix = [
            {
                "id": "validation",
                "task_type": "validation_execute",
                "role": "TesterAgent",
                "title": get_experimental_task_spec("validation_execute").title,
                "objective": "Run safe validation checks before final consolidation.",
                "depends_on": [implementation_tasks[-1]["id"]],
            },
            {
                "id": "consolidate",
                "task_type": "consolidate_final",
                "role": "CoordinatorAgent",
                "title": get_experimental_task_spec("consolidate_final").title,
                "objective": "Summarize work, artifacts, reviewer result, validation result, evidence, and claim guard status for the user.",
                "depends_on": ["validation"],
            },
        ]

        return {
            "kind": "template_dag_proposal",
            "template": template,
            "tasks": [*common_prefix, *implementation_tasks, *suffix],
        }

    def _materialize_dag_proposal_state(
        self,
        *,
        base_swarm: SwarmState,
        proposal: dict,
    ) -> SwarmState:
        contracts_by_key: dict[str, AgentContract] = {}
        tasks: list[TaskNode] = []

        for item in proposal.get("tasks") or []:
            task_type = str(item.get("task_type") or "")
            role = str(item.get("role") or "")
            if not task_type:
                raise ValueError("DAG proposal task is missing task_type")
            if not role:
                raise ValueError("DAG proposal task is missing role")

            spec = get_experimental_task_spec(task_type)
            contract_key = str(item.get("contract_key") or f"{role}:{task_type}")
            contract = contracts_by_key.get(contract_key)
            if contract is None:
                contract = AgentContract(
                    role=role,
                    objective=str(item.get("contract_objective") or item.get("objective") or spec.title),
                    allowed_tools=list(spec.allowed_tools),
                    acceptance_criteria=list(item.get("acceptance_criteria") or []),
                    output_contract=dict(spec.output_contract),
                )
                contracts_by_key[contract_key] = contract

            task_kwargs = {
                "title": spec.title,
                "objective": str(item.get("objective") or spec.title),
                "assigned_contract_id": contract.id,
                "depends_on": [str(dep) for dep in (item.get("depends_on") or [])],
            }
            if item.get("id"):
                task_kwargs["id"] = str(item.get("id"))
            tasks.append(TaskNode(**task_kwargs))

        materialized = base_swarm.model_copy(deep=True)
        materialized.contracts = list(contracts_by_key.values())
        materialized.tasks = tasks
        return materialized

    def _validate_dag_proposal_state(self, swarm: SwarmState) -> list[dict]:
        errors: list[dict] = []

        if not swarm.tasks:
            return [{"error": "dag_proposal_has_no_tasks"}]

        task_ids = [task.id for task in swarm.tasks]
        duplicate_task_ids = sorted({task_id for task_id in task_ids if task_ids.count(task_id) > 1})
        if duplicate_task_ids:
            errors.append({"error": "duplicate_task_ids", "task_ids": duplicate_task_ids})

        contract_ids = [contract.id for contract in swarm.contracts]
        duplicate_contract_ids = sorted({contract_id for contract_id in contract_ids if contract_ids.count(contract_id) > 1})
        if duplicate_contract_ids:
            errors.append({"error": "duplicate_contract_ids", "contract_ids": duplicate_contract_ids})

        tasks_by_id = {task.id: task for task in swarm.tasks}
        for task in swarm.tasks:
            for dep_id in task.depends_on:
                if dep_id not in tasks_by_id:
                    errors.append({"error": "unknown_dependency", "task_id": task.id, "missing_dep": dep_id})

        if not errors:
            visiting: set[str] = set()
            visited: set[str] = set()

            def visit(task_id: str) -> None:
                if task_id in visited:
                    return
                if task_id in visiting:
                    raise ValueError(f"Cycle detected at task {task_id}")
                visiting.add(task_id)
                for dep_id in tasks_by_id[task_id].depends_on:
                    visit(dep_id)
                visiting.remove(task_id)
                visited.add(task_id)

            try:
                for task_id in task_ids:
                    visit(task_id)
            except ValueError as exc:
                errors.append({"error": "invalid_task_dependencies", "detail": str(exc)})

        for task in swarm.tasks:
            try:
                task_type = classify_experimental_task(task)
            except ValueError as exc:
                errors.append({"error": "unknown_task_type", "task_id": task.id, "title": task.title, "detail": str(exc)})
                continue

            try:
                validate_experimental_task_contract(swarm=swarm, task=task, task_type=task_type)
            except ExperimentalTaskContractValidationError as exc:
                errors.append(exc.to_error())

        return errors

    def _build_validated_template_dag_state(
        self,
        *,
        base_swarm: SwarmState,
        template: str,
        generated_plan: dict | None = None,
    ) -> tuple[SwarmState, list[dict]]:
        proposal = self._build_template_dag_proposal(template=template, generated_plan=generated_plan)
        materialized = self._materialize_dag_proposal_state(base_swarm=base_swarm, proposal=proposal)
        validation_errors = self._validate_dag_proposal_state(materialized)
        proposal_tasks = [item for item in (proposal.get("tasks") or []) if isinstance(item, dict)]
        materialized = self._record_dag_proposal_decision(
            swarm=materialized,
            source="template_pipeline",
            proposal_kind=str(proposal.get("kind") or "template_dag_proposal"),
            validation_errors=validation_errors,
            metadata={
                "template": template,
                "task_count": len(proposal_tasks),
                "task_ids": [str(item.get("id") or "") for item in proposal_tasks],
                "task_types": [str(item.get("task_type") or "") for item in proposal_tasks],
                "roles": [str(item.get("role") or "") for item in proposal_tasks],
            },
        )
        return materialized, validation_errors

    def ensure_template_proposal_dag(
        self,
        *,
        swarm_id: str,
        template: str,
        generated_plan: dict | None = None,
    ) -> tuple[SwarmState, list[dict]]:
        swarm = self.store.load(swarm_id)
        self._ensure_workspace_path(swarm)
        if swarm.tasks:
            return self.store.save(swarm), []

        materialized, validation_errors = self._build_validated_template_dag_state(
            base_swarm=swarm,
            template=template,
            generated_plan=generated_plan,
        )
        if validation_errors:
            return materialized, validation_errors

        plan = self._normalize_generated_plan(generated_plan)
        coordinator = next((contract for contract in materialized.contracts if contract.role == "CoordinatorAgent"), None)
        materialized.intent = "task"
        materialized.coordinator_contract_id = coordinator.id if coordinator else None
        message = "static_app_dag_created" if template == "static_app" else "implementation_dag_created"
        materialized.messages.append(
            AgentToAgentMessage(
                type="broadcast_to_swarm",
                from_agent_id=materialized.coordinator_contract_id or materialized.contracts[0].id,
                payload={
                    "message": message,
                    "source": "template_proposal_pipeline",
                    "template": template,
                    "generated_plan_used": bool(generated_plan if isinstance(generated_plan, dict) else {}),
                    "generated_plan_summary": plan["summary"],
                },
                requires_response=False,
            )
        )
        return self.store.save(materialized), []

    def _record_dag_proposal_decision(
        self,
        *,
        swarm: SwarmState,
        source: str,
        proposal_kind: str,
        validation_errors: list[dict],
        metadata: dict | None = None,
    ) -> SwarmState:
        status = "accepted" if not validation_errors else "rejected"
        swarm.decisions.append(
            {
                "kind": "dag_proposal_validation",
                "source": source,
                "proposal_kind": proposal_kind,
                "status": status,
                "validation_errors": validation_errors,
                "metadata": metadata or {},
            }
        )
        return swarm

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
