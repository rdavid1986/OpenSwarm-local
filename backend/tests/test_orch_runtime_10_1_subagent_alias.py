from backend.apps.swarms.process_trace_item import build_process_trace_item
from backend.apps.swarms.process_trace_builder import build_process_trace_item_from_source
from backend.apps.swarms.process_trace_subsystems import apply_subsystem_identity_to_trace_item


def test_subagent_kind_maps_to_miniagent_core():
    item = build_process_trace_item(kind="subagent", title="Subagent trace", summary="Visible subagent trace")
    mapped = apply_subsystem_identity_to_trace_item(item)

    assert item["kind"] == "subagent"
    assert mapped["subsystem"] == "MiniAgentCore"
    assert mapped["metadata"]["subsystem_description"] == "MiniAgent task execution and worker-level trace."


def test_project_orientation_agent_blueprint_emits_subagent_kind():
    item = build_process_trace_item_from_source(
        {
            "source_kind": "project_orientation_agent_blueprint",
            "trace_id": "trace-10-1",
            "project_type": "web_app",
            "selected_pattern": "single_swarm",
            "evidence_refs": ["evidence-1"],
        }
    )

    assert item["kind"] == "subagent"
    assert item["subsystem"] == "SwarmCore"
