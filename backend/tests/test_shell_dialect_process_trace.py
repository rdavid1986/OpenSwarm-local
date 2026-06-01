from backend.apps.swarms.process_trace_builder import build_process_trace_item_from_source, normalize_process_trace_source_kind
from backend.apps.swarms.shell_dialect_runtime import build_shell_profile, build_shell_profile_trace_source


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
