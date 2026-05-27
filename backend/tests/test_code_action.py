from backend.apps.swarms.code_action import (
    build_code_action_contract,
    infer_code_action_risk,
    normalize_code_action_command,
    normalize_code_action_file,
    summarize_code_action_contract,
)


def test_build_code_action_contract_defaults_to_draft_without_execution():
    action = build_code_action_contract()

    assert action["action_type"] == "missing"
    assert action["status"] == "draft"
    assert action["risk_level"] == "low"
    assert action["requires_approval"] is False
    assert action["affected_files"] == []
    assert action["suggested_commands"] == []
    assert action["executed"] is False
    assert action["execution_result"] is None


def test_normalize_code_action_file_preserves_allowed_and_reason():
    file_item = normalize_code_action_file(
        {
            "path": "backend/apps/swarms/code_action.py",
            "operation": "write",
            "allowed": True,
            "reason": "target_file",
            "metadata": {"scope": "swarms"},
        }
    )

    assert file_item["path"] == "backend/apps/swarms/code_action.py"
    assert file_item["operation"] == "write"
    assert file_item["allowed"] is True
    assert file_item["reason"] == "target_file"
    assert file_item["metadata"]["scope"] == "swarms"


def test_normalize_code_action_command_never_marks_command_executed():
    command = normalize_code_action_command(
        {
            "command": "python -m pytest backend/tests/test_code_action.py -q",
            "cwd": ".",
            "timeout_seconds": 60,
            "purpose": "validate contract",
        }
    )

    assert command["command"] == "python -m pytest backend/tests/test_code_action.py -q"
    assert command["cwd"] == "."
    assert command["timeout_seconds"] == 60
    assert command["purpose"] == "validate contract"
    assert command["requires_approval"] is True
    assert command["executed"] is False


def test_infer_code_action_risk_is_conservative_for_write_and_dangerous_command():
    assert infer_code_action_risk("edit_file", [], []) == "medium"
    assert infer_code_action_risk("delete_file", [], []) == "high"
    assert infer_code_action_risk("inspect", [], [{"command": "git push --force"}]) == "critical"


def test_build_code_action_contract_adds_permissions_for_file_write_and_commands():
    action = build_code_action_contract(
        action_id="act-1",
        action_type="apply_patch",
        title="Add code action contract",
        description="Create side-effect-free contract.",
        affected_files=[
            {
                "path": "backend/apps/swarms/code_action.py",
                "operation": "create",
                "allowed": True,
            }
        ],
        suggested_commands=[
            {
                "command": "python -m pytest backend/tests/test_code_action.py -q",
                "purpose": "validate tests",
            }
        ],
        expected_evidence=["pytest output", "git diff --check"],
        source="roadmap:ACI-CODE.1",
    )

    assert action["action_id"] == "act-1"
    assert action["action_type"] == "apply_patch"
    assert action["status"] == "draft"
    assert action["risk_level"] == "medium"
    assert action["requires_approval"] is True
    assert action["required_permissions"] == ["filesystem_write"]
    assert action["suggested_commands"][0]["executed"] is False
    assert action["expected_evidence"] == ["pytest output", "git diff --check"]
    assert action["executed"] is False


def test_build_code_action_contract_adds_command_permission_for_run_command():
    action = build_code_action_contract(
        action_type="run_command",
        suggested_commands=[{"command": "git diff --stat"}],
    )

    assert action["required_permissions"] == ["command_execution"]
    assert action["risk_level"] == "medium"
    assert action["requires_approval"] is True


def test_summarize_code_action_contract_is_compact():
    action = build_code_action_contract(
        action_type="edit_file",
        affected_files=[{"path": "a.py", "operation": "write"}],
        suggested_commands=[{"command": "python -m py_compile a.py"}],
    )

    summary = summarize_code_action_contract(action)

    assert "type=edit_file" in summary
    assert "status=draft" in summary
    assert "risk=medium" in summary
    assert "files=1" in summary
    assert "commands=1" in summary
    assert "executed=False" in summary
