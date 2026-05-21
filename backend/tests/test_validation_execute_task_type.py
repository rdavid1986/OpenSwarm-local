from backend.apps.agents.runtime.experimental_task_type_registry import get_experimental_task_spec


def test_validation_execute_allows_only_safe_validation_tools():
    spec = get_experimental_task_spec("validation_execute")

    assert spec.type == "validation_execute"
    assert spec.allowed_tools == ["Read", "SearchFiles", "SearchText", "SafeShell"]
    assert "Bash" not in spec.allowed_tools
    assert "Write" not in spec.allowed_tools
    assert "Edit" not in spec.allowed_tools
    assert "Diff" not in spec.allowed_tools
    assert spec.allow_idempotent_skip is False
    assert spec.matcher is not None
    assert spec.output_contract == {
        "validation_result": {
            "status": "passed|failed",
            "commands": [],
            "evidence": ["command_executed"],
        }
    }


def test_validation_plan_draft_remains_non_executable():
    spec = get_experimental_task_spec("validation_plan_draft")

    assert spec.allowed_tools == []
    assert spec.allow_idempotent_skip is False
    assert spec.matcher is None
