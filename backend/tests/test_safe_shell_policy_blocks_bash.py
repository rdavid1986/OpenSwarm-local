from backend.apps.agents.runtime.experimental_task_type_registry import get_experimental_task_spec


def test_safe_shell_draft_does_not_allow_bash():
    spec = get_experimental_task_spec("safe_shell_draft")

    assert "Bash" not in spec.allowed_tools
    assert spec.allowed_tools == []
