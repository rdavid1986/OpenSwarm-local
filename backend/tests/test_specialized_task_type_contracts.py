from backend.apps.agents.orchestration.models import AgentContract, TaskNode
from backend.apps.agents.runtime.experimental_task_type_registry import (
    classify_experimental_task,
    get_experimental_task_spec,
)


def test_dormant_specialized_contracts_match_future_task_type_specs():
    pairs = [
        (
            AgentContract(
                role="ArchitectAgent",
                objective="test",
                allowed_tools=[],
                output_contract={
                    "architecture_plan": {
                        "status": "draft|ready",
                        "summary": "string",
                        "constraints": [],
                    }
                },
            ),
            "architecture_plan_draft",
        ),
        (
            AgentContract(
                role="FrontendAgent",
                objective="test",
                allowed_tools=[],
                output_contract={
                    "frontend_plan": {
                        "status": "draft|ready",
                        "summary": "string",
                    }
                },
            ),
            "frontend_plan_draft",
        ),
        (
            AgentContract(
                role="BackendAgent",
                objective="test",
                allowed_tools=[],
                output_contract={
                    "backend_plan": {
                        "status": "draft|ready",
                        "summary": "string",
                    }
                },
            ),
            "backend_plan_draft",
        ),
        (
            AgentContract(
                role="TesterAgent",
                objective="test",
                allowed_tools=[],
                output_contract={
                    "validation_plan": {
                        "status": "draft|ready",
                        "checks": [],
                    }
                },
            ),
            "validation_plan_draft",
        ),
        (
            AgentContract(
                role="SecurityAgent",
                objective="test",
                allowed_tools=[],
                output_contract={
                    "security_review": {
                        "status": "draft|ready",
                        "risks": [],
                    }
                },
            ),
            "security_review_draft",
        ),
    ]

    for contract, task_type in pairs:
        spec = get_experimental_task_spec(task_type)

        assert spec.allowed_tools == []
        assert contract.allowed_tools == spec.allowed_tools
        assert contract.output_contract == spec.output_contract
        assert spec.matcher is None
        assert spec.allow_idempotent_skip is False


def test_future_specialized_task_types_are_not_executable_by_classifier():
    future_titles = [
        "Draft architecture plan",
        "Draft frontend plan",
        "Draft backend plan",
        "Draft validation plan",
        "Draft security review",
    ]

    for title in future_titles:
        try:
            classify_experimental_task(TaskNode(title=title, objective=title))
        except ValueError:
            continue
        raise AssertionError(f"Future task type unexpectedly became executable: {title}")


def test_existing_safe_task_type_classification_still_works():
    known = [
        ("Create README.md", "Create README.md", "create_readme"),
        ("Review README.md", "Review README.md", "review_readme"),
        ("Consolidate final evidence", "Consolidate evidence", "consolidate_final"),
    ]

    for title, objective, expected in known:
        actual = classify_experimental_task(TaskNode(title=title, objective=objective))
        assert actual == expected
