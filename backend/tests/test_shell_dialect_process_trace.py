from backend.apps.swarms.process_trace_builder import build_process_trace_item_from_source, normalize_process_trace_source_kind
from backend.apps.swarms.shell_dialect_runtime import (
    build_shell_profile,
    build_shell_profile_trace_source,
    build_structured_shell_command,
    classify_shell_dialect_error,
    decide_shell_dialect_retry,
    preflight_shell_dialect_command,
    translate_structured_shell_command,
)


def test_process_trace_recognizes_shell_dialect_runtime():
    profile = build_shell_profile(shell_id="git_bash")
    source = build_shell_profile_trace_source(profile)

    assert normalize_process_trace_source_kind(source) == "shell_dialect_runtime"

    item = build_process_trace_item_from_source(source)

    assert item["kind"] == "config"
    assert item["subsystem"] == "ConfigCore"
    assert item["metadata"]["source_kind"] == "shell_dialect_runtime"
    assert item["details"]["shell_id"] == "git_bash"
    assert item["details"]["can_execute"] is False
    assert item["details"]["detection_executed_process"] is False


def test_process_trace_blocks_unknown_shell_profile():
    profile = build_shell_profile(shell_id="unknown")
    source = build_shell_profile_trace_source(profile)

    item = build_process_trace_item_from_source(source)

    assert item["status"] == "blocked"
    assert item["details"]["shell_id"] == "unknown"
    assert "select_shell_profile_before_execution" in item["details"]["required_actions"]


def test_process_trace_warns_for_powershell_5_and_operator_block():
    profile = build_shell_profile(shell_id="powershell_5", shell_version="5.1.19041")
    source = build_shell_profile_trace_source(profile)

    item = build_process_trace_item_from_source(source)

    assert item["status"] == "warning"
    assert item["details"]["shell_id"] == "powershell_5"
    assert item["details"]["capability"]["supports_and_operator"] is False
    assert "block_bash_and_operator" in item["details"]["required_actions"]
    assert "&&" in item["summary"]


def test_process_trace_redacts_shell_profile_metadata():
    profile = build_shell_profile(shell_id="git_bash", metadata={"token": "leak", "safe": "ok"})
    source = build_shell_profile_trace_source(profile)

    item = build_process_trace_item_from_source(source)
    rendered = str(item).lower()

    assert "leak" not in rendered
    assert item["details"]["can_execute"] is False


def test_process_trace_recognizes_structured_shell_command():
    command = build_structured_shell_command(
        intent="inspect",
        command_name="git",
        args=["status", "--short"],
        shell_id="git_bash",
    )

    assert normalize_process_trace_source_kind(command) == "shell_dialect_runtime"

    item = build_process_trace_item_from_source(command)

    assert item["kind"] == "action"
    assert item["details"]["contract_kind"] == "structured_shell_command"
    assert item["details"]["command_name"] == "git"
    assert item["details"]["can_execute"] is False
    assert item["evidence_refs"] == []


def test_process_trace_recognizes_translation_preflight_error_and_retry_contracts():
    command = build_structured_shell_command(
        intent="test",
        command_name="npm",
        args=["test", "&&", "npm", "run", "lint"],
        shell_id="git_bash",
    )
    translation = translate_structured_shell_command(command, target_shell_id="powershell_5")
    preflight = preflight_shell_dialect_command(translation)
    classified = classify_shell_dialect_error("&& is not a valid statement separator", shell_id="powershell_5")
    decision = decide_shell_dialect_retry(preflight)

    for source in (translation, preflight, classified, decision):
        assert normalize_process_trace_source_kind(source) == "shell_dialect_runtime"
        item = build_process_trace_item_from_source(source)
        assert item["details"]["can_execute"] is False
        assert item["details"]["execution_permission_granted"] is False
        assert item["details"]["should_retry"] is False
        assert item["evidence_refs"] == []

    preflight_item = build_process_trace_item_from_source(preflight)
    assert preflight_item["status"] == "blocked"
    assert preflight_item["details"]["preflight_status"] == "blocked"
    assert "powershell_5_invalid_and_operator" in preflight_item["details"]["diagnostics"]


def test_process_trace_does_not_leak_shell_error_secret():
    classified = classify_shell_dialect_error(
        "token secret command not found",
        shell_id="git_bash",
    )

    item = build_process_trace_item_from_source(classified)
    rendered = str(item).lower()

    assert "secret" not in rendered
    assert item["details"]["sanitized_error"] == "[redacted]"
    assert item["details"]["classification"] == "command_not_found"
