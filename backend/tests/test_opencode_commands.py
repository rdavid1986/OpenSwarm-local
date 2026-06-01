from pathlib import Path

from backend.apps.swarms.opencode_commands import (
    build_agent_terminal_request,
    build_builtin_slash_command_registry,
    build_command_family_parity_registry,
    build_command_preview_report,
    build_safe_command_equivalent,
    build_terminal_boundary_decision,
    build_user_terminal_request,
    build_terminal_risk_decision,
    build_opencode_command_trace_source,
    build_opencode_shell_dialect_bridge,
    detect_file_references,
    expand_command_arguments,
    expand_file_references,
    guard_shell_interpolation,
    load_custom_command_file_candidate,
    load_json_config_command_candidate,
    route_command,
)


def test_registry_contains_base_builtins():
    registry = build_builtin_slash_command_registry()
    names = {item["name"] for item in registry.commands}

    assert {"/init", "/undo", "/redo", "/share", "/help"}.issubset(names)
    assert registry.can_execute is False


def test_custom_markdown_candidate_detects_name_and_placeholders(tmp_path: Path):
    command = tmp_path / "review.md"
    command.write_text("# Review\nRun review for $ARGUMENTS and $1. See @src/app.ts", encoding="utf-8")

    candidate = load_custom_command_file_candidate(command, workspace_root=tmp_path)

    assert candidate.command_name == "/review"
    assert "$ARGUMENTS" in candidate.placeholders
    assert "$1" in candidate.placeholders
    assert "src/app.ts" in candidate.file_references
    assert candidate.can_execute is False


def test_json_config_candidate_normalizes_command():
    candidate = load_json_config_command_candidate({
        "commands": {
            "fix": {
                "description": "Fix issue",
                "template": "Fix $ARGUMENTS",
                "agent": "builder",
                "model": "local-model",
                "tools": ["read"],
            }
        }
    }, command_key="fix")

    assert candidate.command_name == "/fix"
    assert candidate.requested_agent == "builder"
    assert candidate.requested_model == "local-model"
    assert "review_command_routing" in candidate.required_actions
    assert candidate.can_execute is False


def test_arguments_expands_without_shell_execution():
    expanded = expand_command_arguments("Do $ARGUMENTS", arguments=["one", "two"])

    assert expanded.expanded_preview == "Do one two"
    assert expanded.shell_executed is False
    assert expanded.can_execute is False


def test_positional_args_expand_and_report_missing():
    expanded = expand_command_arguments("Use $1 then $2 then $3", arguments=["a", "b"])

    assert expanded.expanded_preview == "Use a then b then"
    assert "$3" in expanded.missing_args


def test_shell_interpolation_command_substitution_is_guarded():
    guard = guard_shell_interpolation("Summarize $(cat secret.txt | head)")

    assert "command_substitution" in guard.detected_patterns
    assert guard.decision in {"blocked", "requires_approval"}
    assert guard.shell_interpolation_executed is False
    assert guard.can_execute is False


def test_shell_backticks_are_detected():
    guard = guard_shell_interpolation("Run `whoami`")

    assert "backticks" in guard.detected_patterns
    assert guard.decision == "requires_approval"


def test_file_ref_normalizes_without_reading(tmp_path: Path):
    expansion = expand_file_references("Inspect @src/app.ts", workspace_root=tmp_path)

    assert expansion.requested_refs == ["src/app.ts"]
    assert expansion.normalized_refs == ["src/app.ts"]
    assert expansion.missing_refs == ["src/app.ts"]
    assert expansion.files_read is False


def test_out_of_workspace_file_ref_is_reviewed(tmp_path: Path):
    outside = tmp_path.parent / "outside.txt"
    expansion = expand_file_references(f"Inspect @{outside.as_posix()}", workspace_root=tmp_path)

    assert expansion.out_of_workspace_refs
    assert "review_out_of_workspace_reference" in expansion.required_actions


def test_routing_to_agent_model_requires_action_without_execution():
    route = route_command("/agent", requested_agent="builder", requested_model="local-qwen")

    assert route.target_kind == "agent"
    assert route.requested_agent == "builder"
    assert route.requested_model == "local-qwen"
    assert route.requires_user_approval is True
    assert route.can_execute is False


def test_dangerous_permission_config_is_blocked():
    candidate = load_json_config_command_candidate({
        "name": "unsafe",
        "template": "Do work",
        "permissions": ["--dangerously-skip-permissions"],
    })

    assert candidate.risk_level == "critical"
    assert "--dangerously-skip-permissions" in candidate.blocked_keys
    assert "remove_dangerous_permission_or_config" in candidate.required_actions


def test_trace_source_is_safe_and_non_executable():
    source = build_opencode_command_trace_source(command_name="/init", metadata={"raw_prompt": "leak", "safe": True})
    rendered = str(source).lower()

    assert source["source_kind"] == "opencode_command"
    assert source["can_execute"] is False
    assert source["shell_interpolation_executed"] is False
    assert "leak" not in rendered
    assert "raw_prompt" not in rendered



def test_command_family_registry_contains_required_families():
    registry = build_command_family_parity_registry()
    family_ids = {item["family_id"] for item in registry.families}

    assert {"session", "project", "config", "model", "agent", "tool", "mcp", "skill", "terminal", "preview", "debug", "qa", "help", "share"}.issubset(family_ids)
    assert all(item["can_execute_now"] is False for item in registry.families)


def test_help_safe_equivalent_is_local_help_without_required_execution():
    equivalent = build_safe_command_equivalent("/help")

    assert equivalent.safe_equivalent_id == "local_command_help_palette"
    assert equivalent.action_kind == "show_local_help"
    assert equivalent.execution_supported is True
    assert equivalent.approval_required is False


def test_init_safe_equivalent_requires_preview_and_no_write():
    equivalent = build_safe_command_equivalent("/init")

    assert equivalent.safe_equivalent_id == "project_bootstrap_candidate"
    assert equivalent.preview_required is True
    assert equivalent.execution_supported is False
    assert "do_not_write_files" in equivalent.required_actions


def test_terminal_safe_equivalent_requires_approval_and_no_execution():
    equivalent = build_safe_command_equivalent("/terminal")

    assert equivalent.approval_required is True
    assert equivalent.execution_supported is False
    assert equivalent.blocked_reason == "terminal_runtime_not_connected"


def test_terminal_boundary_differentiates_user_and_agent_terminal():
    user_boundary = build_terminal_boundary_decision(terminal_kind="user_terminal", command_preview="npm test")
    agent_boundary = build_terminal_boundary_decision(terminal_kind="agent_terminal", command_preview="npm test")

    assert user_boundary.user_executes_manually is True
    assert user_boundary.agent_controlled is False
    assert user_boundary.can_execute is False
    assert agent_boundary.agent_controlled is True
    assert agent_boundary.requires_safeshell is True
    assert agent_boundary.requires_policy_matrix is True
    assert agent_boundary.requires_approval is True
    assert agent_boundary.can_execute is False


def test_terminal_request_contracts_are_non_executable():
    user_request = build_user_terminal_request(command_preview="npm test")
    agent_request = build_agent_terminal_request(command_preview="npm test")
    risk = build_terminal_risk_decision(terminal_kind="agent_terminal", command_preview="npm test")

    assert user_request.user_executes_manually is True
    assert user_request.can_execute is False
    assert agent_request.requires_safeshell is True
    assert agent_request.requires_policy_matrix is True
    assert agent_request.requires_approval is True
    assert agent_request.can_execute is False
    assert risk.can_execute is False


def test_preview_report_is_dry_run_only_and_safe(tmp_path: Path):
    report = build_command_preview_report("/terminal $(cat @src/app.ts)", workspace_root=tmp_path, terminal_kind="agent_terminal")

    assert report.command_name == "/terminal"
    assert report.dry_run_only is True
    assert report.can_execute is False
    assert report.shell_executed is False
    assert report.files_read is False
    assert report.tools_called is False
    assert report.mcp_activated is False
    assert report.safe_equivalent["safe_equivalent_id"] == "terminal_boundary_request"
    assert report.terminal_boundary["agent_controlled"] is True
    assert report.shell_interpolation_decision["detected_patterns"]


def test_opencode_shell_dialect_bridge_keeps_execution_disabled():
    bridge = build_opencode_shell_dialect_bridge(
        "/terminal git status && npm test",
        shell_id="powershell_5",
        target_shell_id="powershell_5",
        terminal_kind="agent_terminal",
    )

    assert bridge.bridge_kind == "opencode_shell_dialect_bridge"
    assert bridge.source_kind == "opencode_command"
    assert bridge.command_name == "/terminal"
    assert bridge.can_execute is False
    assert bridge.dry_run_only is True
    assert bridge.shell_executed is False
    assert bridge.tools_called is False
    assert bridge.files_read is False
    assert bridge.mcp_activated is False
    assert bridge.agent_terminal_gate["can_execute"] is False
    assert "keep_opencode_command_execution_disabled" in bridge.required_actions


def test_opencode_trace_source_can_include_shell_dialect_bridge():
    bridge = build_opencode_shell_dialect_bridge(
        "/terminal git status",
        shell_id="git_bash",
        target_shell_id="git_bash",
        terminal_kind="agent_terminal",
        policy_matrix_approved=True,
        safeshell_connected=True,
    )
    source = build_opencode_command_trace_source(command_name="/terminal", shell_dialect_bridge=bridge)

    assert source["source_kind"] == "opencode_command"
    assert source["can_execute"] is False
    assert source["dry_run_only"] is True
    assert "shell_dialect_bridge" in source["preview_report"]
    assert source["preview_report"]["shell_dialect_bridge"]["can_execute"] is False
    assert "keep_opencode_command_execution_disabled" in source["required_actions"]
