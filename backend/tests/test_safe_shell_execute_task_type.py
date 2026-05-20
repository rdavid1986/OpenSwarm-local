from backend.apps.agents.runtime.experimental_task_type_registry import get_experimental_task_spec


def test_safe_shell_execute_is_registered_with_only_safeshell_tool():
    spec = get_experimental_task_spec("safe_shell_execute")

    assert spec.type == "safe_shell_execute"
    assert spec.allowed_tools == ["SafeShell"]
    assert spec.allow_idempotent_skip is False
    assert spec.matcher is None
    assert spec.output_contract == {
        "command_result": {
            "command": "string",
            "exit_code": "number",
            "stdout": "string",
            "stderr": "string",
            "evidence": "command_executed",
        }
    }


def test_safe_shell_draft_remains_non_executable():
    spec = get_experimental_task_spec("safe_shell_draft")

    assert spec.allowed_tools == []
    assert spec.allow_idempotent_skip is False
    assert spec.matcher is None
    assert spec.output_contract["safe_shell_plan"]["executes"] is False
