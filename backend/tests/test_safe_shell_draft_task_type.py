from backend.apps.agents.runtime.experimental_task_type_registry import get_experimental_task_spec


def test_safe_shell_draft_is_registered_but_non_executable():
    spec = get_experimental_task_spec("safe_shell_draft")

    assert spec.type == "safe_shell_draft"
    assert spec.allowed_tools == []
    assert spec.allow_idempotent_skip is False
    assert "safe_shell_plan" in spec.output_contract
    assert "allowed_commands" in spec.output_contract["safe_shell_plan"]
    assert "blocked_patterns" in spec.output_contract["safe_shell_plan"]
