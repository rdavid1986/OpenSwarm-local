from backend.apps.swarms.opencode_commands import build_command_preview_report, build_opencode_command_trace_source, build_opencode_command_audit, route_command
from backend.apps.swarms.process_trace_builder import build_process_trace_item_from_source, normalize_process_trace_source_kind


def test_process_trace_recognizes_opencode_command():
    source = build_opencode_command_trace_source(command_name="/help", origin="built_in_registry")

    assert normalize_process_trace_source_kind(source) == "opencode_command"
    item = build_process_trace_item_from_source(source)

    assert item["kind"] == "action"
    assert item["subsystem"] == "ActionCore"
    assert item["metadata"]["source_kind"] == "opencode_command"
    assert item["details"]["can_execute"] is False


def test_process_trace_redacts_sensitive_command_metadata():
    source = {
        "source_kind": "opencode_command",
        "command_name": "/unsafe",
        "origin": "test",
        "raw_prompt": "private prompt",
        "raw_response": "private response",
        "secret_token": "secret",
        "password": "pw",
        "chain_of_thought": "private reasoning",
        "metadata": {"token": "secret", "safe": "ok"},
    }

    item = build_process_trace_item_from_source(source)
    rendered = str(item).lower()

    assert "private prompt" not in rendered
    assert "private response" not in rendered
    assert "secret" not in rendered
    assert "chain_of_thought" not in rendered
    assert item["details"]["can_execute"] is False


def test_process_trace_includes_required_safety_flags():
    audit = build_opencode_command_audit(command_name="/agent", risk_level="high", required_actions=["request_user_approval"])
    routing = route_command("/agent", requested_agent="builder", requested_model="local-qwen")
    source = build_opencode_command_trace_source(command_name="/agent", audit=audit, routing=routing)

    item = build_process_trace_item_from_source(source)

    assert item["details"]["routing_target"] == "agent"
    assert item["details"]["can_execute"] is False
    assert item["details"]["shell_interpolation_executed"] is False
    assert item["details"]["files_read"] is False
    assert item["details"]["tools_called"] is False
    assert item["details"]["mcp_activated"] is False
    assert "request_user_approval" in item["details"]["required_actions"]



def test_process_trace_includes_preview_family_equivalent_and_terminal_boundary(tmp_path):
    preview = build_command_preview_report("/terminal npm test", workspace_root=tmp_path, terminal_kind="agent_terminal")
    source = build_opencode_command_trace_source(command_name="/terminal", preview_report=preview)

    item = build_process_trace_item_from_source(source)
    details = item["details"]

    assert details["command_family"] == "terminal"
    assert details["safe_equivalent"]["safe_equivalent_id"] == "terminal_boundary_request"
    assert details["terminal_boundary"]["agent_controlled"] is True
    assert details["preview_report"]["dry_run_only"] is True
    assert details["dry_run_only"] is True
    assert details["can_execute"] is False


def test_process_trace_redacts_sensitive_preview_metadata():
    preview = build_command_preview_report("/help")
    source = build_opencode_command_trace_source(command_name="/help", preview_report=preview, metadata={"raw_response": "leak", "secret": "no"})

    item = build_process_trace_item_from_source(source)
    rendered = str(item).lower()

    assert "leak" not in rendered
    assert "raw_response" not in rendered
    assert "secret" not in rendered
