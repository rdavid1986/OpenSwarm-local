from backend.apps.swarms.project_bootstrap_profile import (
    build_project_bootstrap_profile,
    build_project_command_contract,
    build_project_stack_profile,
    decide_project_artifact_store_mode,
)


def test_stack_profile_detects_backend_frontend_npm_pytest():
    profile = build_project_stack_profile(markers=[
        "package-lock.json",
        "frontend/package.json",
        "backend",
        "backend/tests",
        "AGENTS.md",
    ])

    assert "backend" in profile.detected_stacks
    assert "frontend" in profile.detected_stacks
    assert "npm" in profile.package_managers
    assert "pytest" in profile.frameworks
    assert "agents_md" in profile.conventions
    assert profile.can_execute is False
    assert profile.can_write_files is False


def test_command_contract_suggests_without_execution():
    profile = build_project_stack_profile(markers=["frontend/package.json", "backend/tests"])
    contract = build_project_command_contract(profile)

    assert "python -m pytest -q backend/tests" in contract.test_commands
    assert "npm --prefix frontend run build" in contract.build_commands
    assert contract.commands_are_suggestions is True
    assert contract.execution_required is False
    assert contract.requires_user_approval is True
    assert contract.can_execute is False


def test_artifact_decision_for_frontend_requires_preview_diff_and_rollback():
    profile = build_project_stack_profile(markers=["frontend/package.json", "vite.config.ts"])
    commands = build_project_command_contract(profile)
    decision = decide_project_artifact_store_mode(profile, commands)

    assert decision.artifact_mode == "output_workspace_with_preview"
    assert decision.preview_required is True
    assert decision.diff_required is True
    assert decision.rollback_required is True
    assert "validation_result" in decision.evidence_required
    assert decision.can_execute is False
    assert decision.can_write_files is False


def test_bootstrap_profile_combines_sections_without_running_commands():
    profile = build_project_bootstrap_profile(markers=[
        "package-lock.json",
        "frontend/package.json",
        "backend/tests",
    ])

    assert profile.stack_profile["source_kind"] == "project_bootstrap_profile"
    assert profile.command_contract["command_kind"] == "project_test_build_lint_contract"
    assert profile.artifact_decision["artifact_kind"] == "project_artifact_store_mode_decision"
    assert profile.can_execute is False
    assert profile.can_write_files is False
    assert profile.can_run_tests is False
    assert profile.can_run_build is False
    assert profile.can_run_lint is False


def test_low_information_profile_requires_review():
    profile = build_project_bootstrap_profile(markers=[])

    assert "provide_project_root_markers" in profile.required_actions
    assert profile.artifact_decision["artifact_mode"] == "manual_review"
    assert profile.can_execute is False


def test_metadata_is_redacted():
    profile = build_project_stack_profile(markers=["package.json"], metadata={"secret_token": "leak"})

    assert "leak" not in str(profile)
