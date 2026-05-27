from backend.apps.swarms.code_action import (
    apply_code_action_guard,
    build_code_action_contract,
    evaluate_code_action_guard,
    infer_code_action_risk,
    normalize_code_action_command,
    normalize_code_action_contract,
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

def test_evaluate_code_action_guard_moves_safe_write_to_pending_approval():
    action = build_code_action_contract(
        action_type="edit_file",
        affected_files=[
            {
                "path": "backend/apps/swarms/code_action.py",
                "operation": "write",
                "allowed": True,
            }
        ],
    )

    guard = evaluate_code_action_guard(
        action,
        allowed_files=["backend/apps/swarms/code_action.py"],
        granted_permissions=["filesystem_write"],
    )

    assert guard["guard_status"] == "pending_approval"
    assert guard["allowed"] is True
    assert guard["next_status"] == "pending_approval"
    assert guard["execution_allowed"] is False
    assert guard["execution_performed"] is False
    assert guard["reasons"] == []


def test_evaluate_code_action_guard_blocks_missing_permission():
    action = build_code_action_contract(
        action_type="edit_file",
        affected_files=[{"path": "backend/app.py", "operation": "write"}],
    )

    guard = evaluate_code_action_guard(action, allowed_files=["backend/app.py"])

    assert guard["guard_status"] == "blocked"
    assert guard["allowed"] is False
    assert guard["next_status"] == "blocked"
    assert guard["missing_permissions"] == ["filesystem_write"]
    assert guard["reasons"][0]["code"] == "permission_missing"


def test_evaluate_code_action_guard_blocks_forbidden_file_and_path_traversal():
    action = build_code_action_contract(
        action_type="apply_patch",
        affected_files=[
            {"path": "../secrets.env", "operation": "patch"},
            {"path": "backend/secrets.py", "operation": "patch"},
        ],
    )

    guard = evaluate_code_action_guard(
        action,
        allowed_files=["backend"],
        forbidden_files=["backend/secrets.py"],
        granted_permissions=["filesystem_write"],
    )

    codes = {reason["code"] for reason in guard["reasons"]}
    assert guard["guard_status"] == "blocked"
    assert "path_traversal_not_allowed" in codes
    assert "file_forbidden" in codes


def test_evaluate_code_action_guard_blocks_write_outside_allowed_files():
    action = build_code_action_contract(
        action_type="edit_file",
        affected_files=[{"path": "frontend/src/App.tsx", "operation": "write"}],
    )

    guard = evaluate_code_action_guard(
        action,
        allowed_files=["backend"],
        granted_permissions=["filesystem_write"],
    )

    assert guard["guard_status"] == "blocked"
    assert guard["reasons"][0]["code"] == "file_not_allowed"


def test_evaluate_code_action_guard_blocks_dangerous_command():
    action = build_code_action_contract(
        action_type="run_command",
        suggested_commands=[{"command": "git push --force"}],
    )

    guard = evaluate_code_action_guard(action, granted_permissions=["command_execution"])

    assert guard["guard_status"] == "blocked"
    assert guard["risk_level"] == "critical"
    assert guard["reasons"][0]["code"] == "dangerous_command"
    assert "git push" in guard["reasons"][0]["source"]["terms"]


def test_apply_code_action_guard_attaches_guard_without_execution():
    action = build_code_action_contract(
        action_type="run_command",
        suggested_commands=[{"command": "git diff --stat"}],
    )

    guarded = apply_code_action_guard(action, granted_permissions=["command_execution"])

    assert guarded["status"] == "pending_approval"
    assert guarded["guard"]["guard_status"] == "pending_approval"
    assert guarded["executed"] is False
    assert guarded["execution_result"] is None


def test_normalize_code_action_contract_accepts_existing_contract_fields():
    action = build_code_action_contract(
        action_type="edit_file",
        affected_files=[{"path": "backend/app.py", "operation": "write"}],
    )

    normalized = normalize_code_action_contract(action)

    assert normalized["action_type"] == "edit_file"
    assert normalized["affected_files"][0]["path"] == "backend/app.py"
    assert normalized["executed"] is False
    assert normalized["execution_result"] is None
