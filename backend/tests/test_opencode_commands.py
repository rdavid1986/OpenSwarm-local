from pathlib import Path

from backend.apps.swarms.opencode_commands import (
    build_builtin_slash_command_registry,
    build_opencode_command_trace_source,
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
