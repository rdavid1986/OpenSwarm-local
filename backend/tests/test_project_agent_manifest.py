from backend.apps.swarms.project_agent_manifest import (
    build_agent_capability_matrix,
    build_manifest_drift_report,
    build_project_agent_manifest,
    build_skill_routing_table,
    parse_agent_manifest_text,
)


def test_parse_agents_md_manifest_without_materializing_agents():
    entries = parse_agent_manifest_text("""
# Agent: Frontend Agent @frontend
role: FrontendAgent
objective: Build UI
tools: Read, Edit
skills: react, css
handoffs: backend, tester

# Agent: Backend Agent @backend
role: BackendAgent
objective: Build API
tools: Read, Edit, Grep
skills: fastapi, database
memory: read_only
""")

    assert [entry.agent_id for entry in entries] == ["frontend-agent", "backend-agent"]
    assert entries[0].aliases == ["@frontend"]
    assert entries[0].can_create_agent is False
    assert entries[0].can_activate_tools is False
    assert entries[0].can_write_memory is False
    assert "react" in entries[0].skill_refs


def test_manifest_builds_skill_routing_capability_matrix_and_drift_report():
    manifest = build_project_agent_manifest(
        agents=[
            {
                "agent_id": "frontend",
                "aliases": ["@frontend", "@ui"],
                "role": "FrontendAgent",
                "objective": "Build UI",
                "allowed_tools": ["Read", "Edit"],
                "skills": ["react", "css"],
                "capabilities": ["ui", "accessibility"],
                "handoff_targets": ["backend"],
            },
            {
                "agent_id": "backend",
                "aliases": ["@backend"],
                "role": "BackendAgent",
                "objective": "Build API",
                "allowed_tools": ["Read", "Grep"],
                "skills": ["fastapi"],
            },
        ],
        runtime_agents=[{"id": "frontend", "role": "FrontendAgent"}],
        source_uri="file://AGENTS.md",
        source_author="team",
        source_license="MIT",
        metadata={"api_key": "secret"},
    )

    assert manifest.source_kind == "project_agent_manifest"
    assert manifest.can_create_agent is False
    assert manifest.can_activate_tools is False
    assert manifest.metadata["api_key"] == "[redacted]"
    assert manifest.skill_routing_table["routes"]["react"] == ["frontend"]
    assert manifest.skill_routing_table["alias_index"]["@ui"] == "frontend"
    assert manifest.skill_routing_table["can_load_all_skills"] is False
    assert manifest.capability_matrix["agents"]["frontend"]["can_activate_tools"] is False
    assert manifest.drift_report["drift_status"] == "drift_detected"
    assert "backend" in manifest.drift_report["missing_runtime_agents"]


def test_skill_routing_and_capability_contracts_are_lazy_and_inert():
    entries = parse_agent_manifest_text("""
# Agent: QA @qa
role: TesterAgent
skills: pytest, playwright
tools: Read, Grep
""")
    routing = build_skill_routing_table(entries)
    matrix = build_agent_capability_matrix(entries)

    assert routing.lazy_loading_required is True
    assert routing.can_load_all_skills is False
    assert routing.can_activate_tools is False
    assert routing.routes["pytest"] == ["qa"]
    assert matrix.can_create_agent is False
    assert matrix.agents["qa"]["allowed_tools"] == ["Read", "Grep"]


def test_manifest_drift_report_never_mutates_runtime():
    entries = parse_agent_manifest_text("""
# Agent: Reviewer @reviewer
role: ReviewerAgent
""")
    report = build_manifest_drift_report(
        manifest_hash="hash",
        declared_agents=entries,
        runtime_agents=[{"id": "reviewer"}, {"id": "extra"}],
    )

    assert report.drift_status == "drift_detected"
    assert report.undeclared_runtime_agents == ["extra"]
    assert report.can_mutate_runtime is False
    assert "review_manifest_runtime_drift" in report.required_actions
