"""Experimental Task Type Registry.

Registry explícito para tipos seguros del DAG experimental.
No ejecuta tareas. Solo centraliza clasificación, contratos mínimos
y validación idempotente por tipo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from backend.apps.agents.orchestration.models import AgentContract, SwarmState, TaskNode


ExperimentalTaskType = Literal[
    "plan_reused",
    "create_readme",
    "review_readme",
    "consolidate_final",
    "inspect_readme",
    "architecture_plan_draft",
    "frontend_plan_draft",
    "backend_plan_draft",
    "validation_plan_draft",
    "security_review_draft",
]


@dataclass(frozen=True)
class ExperimentalTaskTypeSpec:
    type: ExperimentalTaskType
    title: str
    allowed_tools: list[str] = field(default_factory=list)
    output_contract: dict[str, Any] = field(default_factory=dict)
    allow_idempotent_skip: bool = True
    matcher: Callable[[TaskNode], bool] | None = None


@dataclass(frozen=True)
class ExperimentalTaskContractValidationError(Exception):
    """Fail-closed contract validation error for experimental task execution."""

    code: str
    message: str
    task_id: str
    task_title: str
    task_type: str | None = None
    contract_id: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.message

    def to_error(self) -> dict[str, Any]:
        error = {
            "error": "contract_validation_failed",
            "code": self.code,
            "message": self.message,
            "task_id": self.task_id,
            "title": self.task_title,
        }
        if self.task_type:
            error["type"] = self.task_type
        if self.contract_id:
            error["contract_id"] = self.contract_id
        if self.detail:
            error["detail"] = self.detail
        return error


def _task_text(task: TaskNode) -> str:
    return f"{task.title} {task.objective}".lower()


def _matches_plan_reused(task: TaskNode) -> bool:
    text = _task_text(task)
    return "plan" in text and ("dag" in text or "task" in text)


def _matches_create_readme(task: TaskNode) -> bool:
    text = _task_text(task)
    return "readme" in text and any(word in text for word in ("create", "crea"))


def _matches_review_readme(task: TaskNode) -> bool:
    text = _task_text(task)
    return "review" in text and "readme" in text


def _matches_consolidate_final(task: TaskNode) -> bool:
    text = _task_text(task)
    return "consolidate" in text and "evidence" in text


def _matches_inspect_readme(task: TaskNode) -> bool:
    text = _task_text(task)
    return "inspect" in text and "readme" in text


TASK_TYPE_REGISTRY: dict[ExperimentalTaskType, ExperimentalTaskTypeSpec] = {
    "plan_reused": ExperimentalTaskTypeSpec(
        type="plan_reused",
        title="Plan task DAG",
        allowed_tools=[],
        output_contract={"planner_result": {"status": "plan_validated|plan_rejected", "reason": "string"}},
        matcher=_matches_plan_reused,
    ),
    "create_readme": ExperimentalTaskTypeSpec(
        type="create_readme",
        title="Create README.md",
        allowed_tools=["Read", "Write", "Edit", "SearchFiles", "SearchText"],
        output_contract={"submit_artifact": {"path": "README.md", "kind": "documentation"}},
        matcher=_matches_create_readme,
    ),
    "review_readme": ExperimentalTaskTypeSpec(
        type="review_readme",
        title="Review README.md",
        allowed_tools=["Read", "SearchFiles", "SearchText"],
        output_contract={"review_result": {"status": "approved|rejected", "artifact_path": "README.md", "evidence": []}},
        matcher=_matches_review_readme,
    ),
    "consolidate_final": ExperimentalTaskTypeSpec(
        type="consolidate_final",
        title="Consolidate final evidence",
        allowed_tools=[],
        output_contract={"final_result": {"status": "completed|failed", "summary": "string"}},
        matcher=_matches_consolidate_final,
    ),
    "inspect_readme": ExperimentalTaskTypeSpec(
        type="inspect_readme",
        title="Inspect README.md",
        allowed_tools=["Read"],
        output_contract={
            "readme_inspection": {
                "path": "README.md",
                "bytes": "number",
                "line_count": "number",
                "has_title": "boolean",
            }
        },
        matcher=_matches_inspect_readme,
    ),
    "architecture_plan_draft": ExperimentalTaskTypeSpec(
        type="architecture_plan_draft",
        title="Draft architecture plan",
        allowed_tools=[],
        output_contract={
            "architecture_plan": {
                "status": "draft|ready",
                "summary": "string",
                "constraints": [],
            }
        },
        allow_idempotent_skip=False,
        matcher=None,
    ),
    "frontend_plan_draft": ExperimentalTaskTypeSpec(
        type="frontend_plan_draft",
        title="Draft frontend plan",
        allowed_tools=[],
        output_contract={
            "frontend_plan": {
                "status": "draft|ready",
                "summary": "string",
            }
        },
        allow_idempotent_skip=False,
        matcher=None,
    ),
    "backend_plan_draft": ExperimentalTaskTypeSpec(
        type="backend_plan_draft",
        title="Draft backend plan",
        allowed_tools=[],
        output_contract={
            "backend_plan": {
                "status": "draft|ready",
                "summary": "string",
            }
        },
        allow_idempotent_skip=False,
        matcher=None,
    ),
    "validation_plan_draft": ExperimentalTaskTypeSpec(
        type="validation_plan_draft",
        title="Draft validation plan",
        allowed_tools=[],
        output_contract={
            "validation_plan": {
                "status": "draft|ready",
                "checks": [],
            }
        },
        allow_idempotent_skip=False,
        matcher=None,
    ),
    "security_review_draft": ExperimentalTaskTypeSpec(
        type="security_review_draft",
        title="Draft security review",
        allowed_tools=[],
        output_contract={
            "security_review": {
                "status": "draft|ready",
                "risks": [],
            }
        },
        allow_idempotent_skip=False,
        matcher=None,
    ),
}


def classify_experimental_task(task: TaskNode) -> ExperimentalTaskType:
    for task_type, spec in TASK_TYPE_REGISTRY.items():
        if spec.matcher and spec.matcher(task):
            return task_type
    raise ValueError(f"Unknown safe task type: {task.title}")


def get_experimental_task_spec(task_type: ExperimentalTaskType) -> ExperimentalTaskTypeSpec:
    return TASK_TYPE_REGISTRY[task_type]


def get_experimental_task_allowed_tools(task_type: ExperimentalTaskType) -> list[str]:
    return list(get_experimental_task_spec(task_type).allowed_tools)


def experimental_tool_policy_metadata(*, task: TaskNode, contract: AgentContract) -> dict[str, Any]:
    task_type = classify_experimental_task(task)
    spec = get_experimental_task_spec(task_type)
    return {
        "policy_scope": "experimental",
        "task_type": task_type,
        "task_type_allowed_tools": list(spec.allowed_tools),
        "agent_contract_allowed_tools": list(contract.allowed_tools or []),
    }


def find_assigned_contract(*, swarm: SwarmState, task: TaskNode) -> AgentContract | None:
    if not task.assigned_contract_id:
        return None
    return next((contract for contract in swarm.contracts if contract.id == task.assigned_contract_id), None)


def validate_experimental_task_contract(
    *,
    swarm: SwarmState,
    task: TaskNode,
    task_type: ExperimentalTaskType,
) -> AgentContract:
    spec = get_experimental_task_spec(task_type)
    contract = find_assigned_contract(swarm=swarm, task=task)
    if contract is None:
        raise ExperimentalTaskContractValidationError(
            code="missing_assigned_contract",
            message="Experimental task has no existing assigned contract.",
            task_id=task.id,
            task_title=task.title,
            task_type=task_type,
            contract_id=task.assigned_contract_id,
        )

    extra_tools = sorted(set(contract.allowed_tools or []) - set(spec.allowed_tools or []))
    if extra_tools:
        raise ExperimentalTaskContractValidationError(
            code="allowed_tools_exceed_task_type",
            message="Contract allowed_tools exceeds the Task Type Registry allowed_tools.",
            task_id=task.id,
            task_title=task.title,
            task_type=task_type,
            contract_id=contract.id,
            detail={
                "extra_tools": extra_tools,
                "contract_allowed_tools": list(contract.allowed_tools or []),
                "registry_allowed_tools": list(spec.allowed_tools or []),
            },
        )

    if contract.output_contract != spec.output_contract:
        raise ExperimentalTaskContractValidationError(
            code="output_contract_mismatch",
            message="Contract output_contract does not strictly match the Task Type Registry output_contract.",
            task_id=task.id,
            task_title=task.title,
            task_type=task_type,
            contract_id=contract.id,
            detail={
                "contract_output_contract": contract.output_contract,
                "registry_output_contract": spec.output_contract,
            },
        )

    return contract


def validate_experimental_task_completion(
    *,
    swarm: SwarmState,
    task: TaskNode,
    task_type: ExperimentalTaskType,
    planner_agent_runtime_enabled: bool,
    readme_artifact_finder: Callable[[SwarmState, str], dict[str, Any] | None],
    task_finder: Callable[[SwarmState, ExperimentalTaskType], TaskNode],
    approved_review_finder: Callable[[TaskNode, dict[str, Any]], dict[str, Any] | None],
) -> bool:
    spec = get_experimental_task_spec(task_type)
    if not spec.allow_idempotent_skip:
        return False

    if task_type == "plan_reused":
        if planner_agent_runtime_enabled:
            return any(item.get("kind") == "planner_result" and item.get("status") == "validated" for item in task.evidence)
        return any(item.get("kind") == "plan_reused" for item in task.evidence)

    if task_type == "create_readme":
        return readme_artifact_finder(swarm, task.id) is not None

    if task_type == "review_readme":
        worker = task_finder(swarm, "create_readme")
        artifact = readme_artifact_finder(swarm, worker.id)
        return bool(artifact and approved_review_finder(task, artifact))

    if task_type == "consolidate_final":
        if swarm.final_result.get("status") != "completed" or not swarm.final_evidence:
            return False
        claim_guard = swarm.final_result.get("claim_guard")
        if isinstance(claim_guard, dict):
            return claim_guard.get("status") == "verified"
        return True

    if task_type == "inspect_readme":
        return any(item.get("kind") == "readme_inspection" and item.get("path") == "README.md" for item in task.evidence)

    return False
