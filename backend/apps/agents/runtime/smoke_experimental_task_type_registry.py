"""Smoke del Task Type Registry experimental."""

from __future__ import annotations

import json

from backend.apps.agents.orchestration.models import AgentContract, TaskNode, SwarmState
from backend.apps.agents.runtime.experimental_task_type_registry import (
    TASK_TYPE_REGISTRY,
    ExperimentalTaskContractValidationError,
    classify_experimental_task,
    find_assigned_contract,
    get_experimental_task_spec,
    validate_experimental_task_contract,
    validate_experimental_task_completion,
)


def main() -> int:
    tasks = [
        TaskNode(title="Plan task DAG", objective="Validate task DAG"),
        TaskNode(title="Create README.md", objective="Create a README.md file"),
        TaskNode(title="Review README.md", objective="Review README.md"),
        TaskNode(title="Consolidate final evidence", objective="Consolidate evidence"),
        TaskNode(title="Inspect README.md", objective="Inspect README.md metadata"),
    ]

    classified = [classify_experimental_task(task) for task in tasks]
    expected = ["plan_reused", "create_readme", "review_readme", "consolidate_final", "inspect_readme"]

    unknown_rejected = False
    try:
        classify_experimental_task(TaskNode(title="Unknown experimental task", objective="Do something arbitrary"))
    except ValueError:
        unknown_rejected = True

    specs = {
        task_type: {
            "title": spec.title,
            "allowed_tools": spec.allowed_tools,
            "output_contract": spec.output_contract,
            "allow_idempotent_skip": spec.allow_idempotent_skip,
        }
        for task_type, spec in TASK_TYPE_REGISTRY.items()
    }

    spec_lookup_ok = all(get_experimental_task_spec(task_type).type == task_type for task_type in expected)

    empty_swarm = SwarmState(title="Registry smoke", user_prompt="registry smoke")
    validation_false_for_empty = [
        validate_experimental_task_completion(
            swarm=empty_swarm,
            task=task,
            task_type=task_type,
            planner_agent_runtime_enabled=True,
            readme_artifact_finder=lambda swarm, source_task_id: None,
            task_finder=lambda swarm, task_type: tasks[1],
            approved_review_finder=lambda reviewer, artifact: None,
        )
        for task, task_type in zip(tasks, expected)
    ]

    contract_validation_ok = []
    contract_validation_rejected = []
    for task_type in expected:
        spec = get_experimental_task_spec(task_type)
        contract = AgentContract(
            role="DocumentationAgent" if task_type in {"create_readme", "inspect_readme"} else "ReviewerAgent",
            objective=f"Validate {task_type}",
            allowed_tools=list(spec.allowed_tools),
            output_contract=dict(spec.output_contract),
        )
        task = TaskNode(title=spec.title, objective=spec.title, assigned_contract_id=contract.id)
        swarm = SwarmState(title="Contract smoke", user_prompt="contract smoke", contracts=[contract], tasks=[task])
        contract_validation_ok.append(find_assigned_contract(swarm=swarm, task=task) == contract)
        contract_validation_ok.append(validate_experimental_task_contract(swarm=swarm, task=task, task_type=task_type) == contract)

    negative_spec = get_experimental_task_spec("inspect_readme")
    negative_contract = AgentContract(
        role="ReviewerAgent",
        objective="Inspect README.md metadata.",
        allowed_tools=["Read", "Write"],
        output_contract=dict(negative_spec.output_contract),
    )
    negative_task = TaskNode(title=negative_spec.title, objective=negative_spec.title, assigned_contract_id=negative_contract.id)
    negative_swarm = SwarmState(title="Contract smoke", user_prompt="contract smoke", contracts=[negative_contract], tasks=[negative_task])
    try:
        validate_experimental_task_contract(swarm=negative_swarm, task=negative_task, task_type="inspect_readme")
    except ExperimentalTaskContractValidationError as exc:
        contract_validation_rejected.append(exc.code == "allowed_tools_exceed_task_type")

    missing_task = TaskNode(title=negative_spec.title, objective=negative_spec.title, assigned_contract_id="missing")
    try:
        validate_experimental_task_contract(swarm=negative_swarm, task=missing_task, task_type="inspect_readme")
    except ExperimentalTaskContractValidationError as exc:
        contract_validation_rejected.append(exc.code == "missing_assigned_contract")

    bad_output_contract = negative_contract.model_copy(deep=True)
    bad_output_contract.allowed_tools = ["Read"]
    bad_output_contract.output_contract = {"wrong": True}
    bad_output_swarm = SwarmState(title="Contract smoke", user_prompt="contract smoke", contracts=[bad_output_contract], tasks=[negative_task])
    try:
        validate_experimental_task_contract(swarm=bad_output_swarm, task=negative_task, task_type="inspect_readme")
    except ExperimentalTaskContractValidationError as exc:
        contract_validation_rejected.append(exc.code == "output_contract_mismatch")

    result = {
        "ok": (
            classified == expected
            and unknown_rejected
            and spec_lookup_ok
            and not any(validation_false_for_empty)
            and all(contract_validation_ok)
            and contract_validation_rejected == [True, True, True]
        ),
        "classified": classified,
        "expected": expected,
        "unknown_rejected": unknown_rejected,
        "spec_lookup_ok": spec_lookup_ok,
        "validation_false_for_empty": validation_false_for_empty,
        "contract_validation_ok": contract_validation_ok,
        "contract_validation_rejected": contract_validation_rejected,
        "specs": specs,
    }

    print("########## COPIAR DESDE AQUÍ ##########")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
