from backend.apps.swarms.agent_mention_routing import decide_agent_mention_route, parse_agent_mentions, resolve_agent_mentions
from backend.apps.swarms.process_trace_builder import build_process_trace_item_from_source, normalize_process_trace_source_kind
from backend.apps.swarms.project_agent_manifest import build_project_agent_manifest


def _manifest():
    return build_project_agent_manifest(
        agents=[{"agent_id": "frontend", "aliases": ["@frontend"], "role": "FrontendAgent", "skills": ["react"]}],
        metadata={"api_key": "secret-value"},
    )


def assert_agent_mention_trace(source):
    assert normalize_process_trace_source_kind(source) == "agent_mention_routing"
    item = build_process_trace_item_from_source(source)
    assert item["metadata"]["source_kind"] == "agent_mention_routing"
    assert item["subsystem"] == "SwarmCore"
    assert item["details"]["can_execute"] is False
    assert item["details"]["can_create_agent"] is False
    assert item["details"]["can_create_miniagent"] is False
    assert item["details"]["can_execute_handoffs"] is False
    assert item["details"]["can_activate_tools"] is False
    assert item["details"]["can_write_memory"] is False
    assert item["details"]["contains_private_reasoning"] is False
    return item


def test_process_trace_supports_parse_resolve_and_decision_contracts():
    manifest = _manifest()
    parsed = parse_agent_mentions("@frontend implement this")
    resolved = resolve_agent_mentions(message="@frontend implement this", manifest=manifest)
    decision = decide_agent_mention_route(message="@frontend implement this", manifest=manifest)

    items = [assert_agent_mention_trace(source) for source in [parsed, resolved, decision]]

    assert [item["details"]["contract_kind"] for item in items] == [
        "agent_mention_parse_result",
        "agent_mention_resolver_result",
        "agent_mention_routing_decision",
    ]
    assert items[-1]["details"]["target_agent_id"] == "frontend"
    assert items[-1]["details"]["policy_matrix_required"] is True
    assert items[-1]["details"]["context_packets_required"] is True
    assert items[-1]["details"]["handoff_required"] is True
    assert items[-1]["details"]["evidence_required"] is True


def test_process_trace_blocks_unknown_agent_without_secret_leak():
    decision = decide_agent_mention_route(message="@unknown use api_key=secret", manifest=_manifest())
    item = assert_agent_mention_trace(decision)
    rendered = str(item).lower()

    assert item["status"] == "blocked"
    assert "unresolved_agent_mentions" in item["details"]["blockers"]
    assert "secret-value" not in rendered
    assert "api_key=secret" not in rendered
