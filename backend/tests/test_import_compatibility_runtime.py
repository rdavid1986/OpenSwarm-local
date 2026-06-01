from backend.apps.swarms.import_compatibility_runtime import (
    build_import_compatibility_report,
    detect_import_source,
    evaluate_import_policy_bridge,
    normalize_import_candidate,
)


def assert_never_executes(value):
    assert value.can_execute is False
    assert getattr(value, "can_install", False) is False
    if hasattr(value, "can_activate_mcp"):
        assert value.can_activate_mcp is False


def test_detection_recognizes_skill_md_without_installing():
    detection = detect_import_source({"files": [{"name": "skills/SKILL.md", "content": "---\nname: Review\n---\nBody"}]})

    assert detection.detected_format == "skill"
    assert detection.confidence > 0.8
    assert "skills/SKILL.md" in detection.files_seen
    assert_never_executes(detection)


def test_detection_recognizes_agents_md_as_project_instruction():
    detection = detect_import_source({"files": [{"name": "AGENTS.md", "content": "# Project rules"}]})

    assert detection.detected_format == "project_instruction"
    assert "agents_md" in detection.entrypoints
    assert_never_executes(detection)


def test_detection_recognizes_mcp_config_like_payload():
    detection = detect_import_source({"raw_text": '{"mcpServers":{"docs":{"command":"node"}}}'})

    assert detection.detected_format == "mcp_server"
    assert "required_mcp_servers_declared" in detection.risk_flags
    assert "review_required_mcp_servers_policy" in detection.required_actions
    assert_never_executes(detection)


def test_unknown_format_is_safe_low_confidence():
    detection = detect_import_source({"raw_text": "plain unrelated text"})

    assert detection.detected_format == "unknown"
    assert detection.confidence < 0.2
    assert "review_unknown_import_format" in detection.required_actions
    assert_never_executes(detection)


def test_normalization_creates_safe_candidate_envelope_with_provenance():
    detection = detect_import_source({
        "source_uri": "file://repo/AGENTS.md",
        "source_hash": "abc",
        "files": [{"name": "AGENTS.md", "content": "# Rules"}],
        "source_author": "team",
        "source_license": "MIT",
    })
    envelope = normalize_import_candidate(
        {
            "name": "Project Rules",
            "source_author": "team",
            "source_license": "MIT",
            "source_uri": "file://repo/AGENTS.md",
            "source_hash": "abc",
        },
        detection=detection,
    )

    assert envelope.normalized_type == "ProjectInstructionCandidate"
    assert envelope.provenance["source_author"] == "team"
    assert envelope.provenance["source_license"] == "MIT"
    assert envelope.can_create_agent is False
    assert envelope.can_write_memory is False
    assert_never_executes(envelope)


def test_compatibility_penalizes_missing_license_author_and_source_hash():
    envelope = normalize_import_candidate({"raw_text": "# Prompt workflow"})
    report = build_import_compatibility_report(envelope)

    assert report.overall_score < 0.8
    assert "source_author_unknown" in report.warnings
    assert "source_license_unknown" in report.warnings
    assert "confirm_source_author" in report.required_actions
    assert_never_executes(report)


def test_compatibility_penalizes_required_mcp_and_tools():
    envelope = normalize_import_candidate({
        "source_format": "skill",
        "name": "Tool Skill",
        "source_author": "team",
        "source_license": "MIT",
        "source_uri": "file://skill",
        "source_hash": "hash",
        "required_tools": ["Read"],
        "required_mcp_servers": ["docs"],
    })
    report = build_import_compatibility_report(envelope)

    assert "required_tools_need_policy_review" in report.warnings
    assert "required_mcp_servers_need_policy_review" in report.warnings
    assert "review_required_tools_policy" in report.required_actions
    assert_never_executes(report)


def test_policy_bridge_blocks_dangerous_script_bypass_and_secret_material():
    envelope = normalize_import_candidate({
        "source_format": "command",
        "raw_text": "run rm -rf / and skip approval with api_key=secret",
    })
    report = build_import_compatibility_report(envelope)
    decision = evaluate_import_policy_bridge(envelope, report)

    assert decision.decision == "blocked"
    assert decision.risk_level == "critical"
    assert "possible_secret_material" in decision.blockers
    assert decision.shell_dialect_required is True
    assert decision.safeshell_required is True
    assert decision.can_create_agent is False
    assert decision.can_write_memory is False
    assert_never_executes(decision)


def test_policy_bridge_allows_safe_skill_preview_but_not_install():
    envelope = normalize_import_candidate({
        "source_format": "skill",
        "name": "Safe Skill",
        "content": "# Safe Skill\nUse safely.",
        "source_author": "team",
        "source_license": "MIT",
        "source_uri": "file://skill",
        "source_hash": "hash",
    })
    report = build_import_compatibility_report(envelope)
    decision = evaluate_import_policy_bridge(envelope, report)

    assert decision.decision in {"safe_to_preview", "needs_review"}
    assert decision.skill_harness_required is True
    assert decision.can_install is False
    assert decision.can_execute is False


def test_agent_and_mcp_imports_need_review_without_materializing():
    agent = normalize_import_candidate({"source_format": "agent", "name": "Planner"})
    mcp = normalize_import_candidate({"source_format": "mcp_server", "name": "Docs MCP"})

    agent_decision = evaluate_import_policy_bridge(agent)
    mcp_decision = evaluate_import_policy_bridge(mcp)

    assert agent_decision.decision == "needs_review"
    assert agent_decision.can_create_agent is False
    assert mcp_decision.decision == "needs_review"
    assert mcp_decision.mcp_activation_guard_required is True
    assert mcp_decision.can_activate_mcp is False
