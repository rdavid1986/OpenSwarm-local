from backend.apps.swarms.process_trace_builder import build_process_trace_item_from_source, normalize_process_trace_source_kind
from backend.apps.swarms.project_agent_manifest import build_project_agent_manifest


def test_project_agent_manifest_process_trace_is_safe_and_visible():
    manifest = build_project_agent_manifest(
        agents=[
            {
                "agent_id": "frontend",
                "aliases": ["@frontend"],
                "role": "FrontendAgent",
                "skills": ["react"],
                "allowed_tools": ["Read", "Edit"],
            }
        ],
        metadata={"token": "secret"},
    )

    assert normalize_process_trace_source_kind(manifest) == "project_agent_manifest"
    item = build_process_trace_item_from_source(manifest)

    assert item["metadata"]["source_kind"] == "project_agent_manifest"
    assert item["subsystem"] == "SwarmCore"
    assert item["details"]["agent_count"] == 1
    assert item["details"]["can_create_agent"] is False
    assert item["details"]["can_create_miniagent"] is False
    assert item["details"]["can_activate_tools"] is False
    assert item["details"]["can_write_memory"] is False
    assert item["details"]["contains_private_reasoning"] is False
    assert item["details"]["skill_routing_table"]["routes"]["react"] == ["frontend"]
    rendered = str(item).lower()
    assert "secret" not in rendered
    assert "secret-value" not in rendered


def test_project_agent_manifest_process_trace_reports_drift_review():
    manifest = build_project_agent_manifest(
        agents=[{"agent_id": "backend", "role": "BackendAgent"}],
        runtime_agents=[],
    )

    item = build_process_trace_item_from_source(manifest)

    assert item["status"] == "warning"
    assert item["details"]["drift_report"]["drift_status"] == "not_checked"
    assert "provide_runtime_agents_for_drift_check" in item["details"]["required_actions"]
