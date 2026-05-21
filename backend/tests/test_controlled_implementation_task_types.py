from backend.apps.agents.runtime.experimental_task_type_registry import get_experimental_task_spec


def test_frontend_implementation_draft_remains_non_executable():
    spec = get_experimental_task_spec("frontend_implementation_draft")

    assert spec.type == "frontend_implementation_draft"
    assert spec.allowed_tools == []
    assert "Write" not in spec.allowed_tools
    assert "Edit" not in spec.allowed_tools
    assert "SafeShell" not in spec.allowed_tools
    assert spec.allow_idempotent_skip is False
    assert spec.matcher is None
    assert spec.output_contract == {
        "frontend_implementation_plan": {
            "status": "draft|ready",
            "summary": "string",
            "allowed_paths": ["frontend/src"],
            "forbidden_paths": ["backend", "electron", "frontend/package.json", "frontend/package-lock.json"],
            "proposed_files": [],
            "requires_approval": True,
            "executes": False,
        }
    }


def test_frontend_implementation_execute_is_blocked_until_enabled():
    spec = get_experimental_task_spec("frontend_implementation_execute")

    assert spec.type == "frontend_implementation_execute"
    assert spec.allowed_tools == []
    assert "Write" not in spec.allowed_tools
    assert "Edit" not in spec.allowed_tools
    assert "SafeShell" not in spec.allowed_tools
    assert spec.allow_idempotent_skip is False
    assert spec.matcher is None
    assert spec.output_contract == {
        "frontend_implementation_result": {
            "status": "blocked_until_enabled",
            "summary": "string",
            "files_changed": [],
            "diff_summary": [],
            "evidence": [],
            "executes": False,
            "activation_requirement": "Enable scoped write/edit tools and path guard before execution.",
        }
    }


def test_backend_implementation_draft_remains_non_executable():
    spec = get_experimental_task_spec("backend_implementation_draft")

    assert spec.type == "backend_implementation_draft"
    assert spec.allowed_tools == []
    assert "Write" not in spec.allowed_tools
    assert "Edit" not in spec.allowed_tools
    assert "SafeShell" not in spec.allowed_tools
    assert spec.allow_idempotent_skip is False
    assert spec.matcher is None
    assert spec.output_contract == {
        "backend_implementation_plan": {
            "status": "draft|ready",
            "summary": "string",
            "allowed_paths": ["backend/apps/agents"],
            "forbidden_paths": ["frontend", "electron", "backend/requirements.txt", "pyproject.toml"],
            "proposed_files": [],
            "requires_approval": True,
            "executes": False,
        }
    }


def test_backend_implementation_execute_is_blocked_until_enabled():
    spec = get_experimental_task_spec("backend_implementation_execute")

    assert spec.type == "backend_implementation_execute"
    assert spec.allowed_tools == []
    assert "Write" not in spec.allowed_tools
    assert "Edit" not in spec.allowed_tools
    assert "SafeShell" not in spec.allowed_tools
    assert spec.allow_idempotent_skip is False
    assert spec.matcher is None
    assert spec.output_contract == {
        "backend_implementation_result": {
            "status": "blocked_until_enabled",
            "summary": "string",
            "files_changed": [],
            "diff_summary": [],
            "evidence": [],
            "executes": False,
            "activation_requirement": "Enable scoped write/edit tools and path guard before execution.",
        }
    }
