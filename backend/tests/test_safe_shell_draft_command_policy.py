from backend.apps.agents.runtime.experimental_task_type_registry import get_experimental_task_spec


def test_safe_shell_draft_declares_future_command_policy_without_execution():
    plan = get_experimental_task_spec("safe_shell_draft").output_contract["safe_shell_plan"]

    assert plan["executes"] is False
    assert plan["requires_workspace"] is True
    assert "git status --short" in plan["allowed_commands"]
    assert "git diff --check" in plan["allowed_commands"]
    assert "rm -rf" in plan["blocked_patterns"]
    assert "Invoke-WebRequest | iex" in plan["blocked_patterns"]
    assert plan["execution_status"] == "disabled"
    assert "executable safe shell task type" in plan["activation_requirement"]
