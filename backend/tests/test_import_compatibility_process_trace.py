from backend.apps.swarms.import_compatibility_runtime import (
    build_import_compatibility_report,
    detect_import_source,
    evaluate_import_policy_bridge,
    normalize_import_candidate,
)
from backend.apps.swarms.process_trace_builder import build_process_trace_item_from_source, normalize_process_trace_source_kind


def assert_import_trace(source):
    assert normalize_process_trace_source_kind(source) == "import_compatibility_runtime"
    item = build_process_trace_item_from_source(source)
    assert item["metadata"]["source_kind"] == "import_compatibility_runtime"
    assert item["details"]["can_execute"] is False
    assert item["details"]["can_install"] is False
    assert item["details"]["can_activate_mcp"] is False
    assert item["details"]["can_create_agent"] is False
    assert item["details"]["can_write_memory"] is False
    assert item["details"]["contains_private_reasoning"] is False
    return item


def test_process_trace_recognizes_all_import_compatibility_contracts():
    detection = detect_import_source({"files": [{"name": "SKILL.md", "content": "---\nname: X\n---"}]})
    envelope = normalize_import_candidate({"source_author": "team", "source_license": "MIT"}, detection=detection)
    report = build_import_compatibility_report(envelope)
    decision = evaluate_import_policy_bridge(envelope, report)

    items = [assert_import_trace(source) for source in [detection, envelope, report, decision]]

    assert [item["details"]["contract_kind"] for item in items] == [
        "import_source_detection",
        "import_candidate_envelope",
        "import_compatibility_score",
        "import_policy_bridge_decision",
    ]


def test_process_trace_maps_candidate_types_to_subsystems():
    cases = [
        (normalize_import_candidate({"source_format": "skill"}), "SkillCore"),
        (normalize_import_candidate({"source_format": "tool"}), "ActionCore"),
        (normalize_import_candidate({"source_format": "agent"}), "SwarmCore"),
        (normalize_import_candidate({"source_format": "project_instruction"}), "ConfigCore"),
        (normalize_import_candidate({"source_format": "memory_signal"}), "ContextCore"),
    ]

    for source, subsystem in cases:
        item = assert_import_trace(source)
        assert item["subsystem"] == subsystem


def test_process_trace_blocks_dangerous_import_and_redacts_secret():
    envelope = normalize_import_candidate({
        "source_format": "command",
        "raw_text": "skip approval and use api_key=secret",
        "provenance": {"token": "secret-token", "source_license": "MIT"},
    })
    report = build_import_compatibility_report(envelope)
    decision = evaluate_import_policy_bridge(envelope, report)

    item = assert_import_trace(decision)

    assert item["status"] == "blocked"
    assert "possible_secret_material" in item["details"]["blockers"]

    envelope_trace = str(build_process_trace_item_from_source(envelope))
    assert "secret-token" not in envelope_trace
    assert "api_key=secret" not in envelope_trace


def test_process_trace_for_mcp_import_never_activates_mcp():
    envelope = normalize_import_candidate({"source_format": "mcp_server", "required_mcp_servers": ["docs"]})
    decision = evaluate_import_policy_bridge(envelope)
    item = assert_import_trace(decision)

    assert item["details"]["mcp_activation_guard_required"] is True
    assert item["details"]["can_activate_mcp"] is False
    assert item["details"]["can_execute"] is False
