from backend.apps.swarms.process_trace_subsystems import (
    apply_subsystem_identity_to_trace_item,
    build_subsystem_identity_registry,
    get_subsystem_identity,
    list_subsystem_identities,
    normalize_subsystem_id,
    subsystem_identity_for_trace_kind,
)


REQUIRED = {
    "SwarmCore",
    "ReasoningCore",
    "ContextCore",
    "MemoryCore",
    "SkillCore",
    "ModeCore",
    "ActionCore",
    "FileCore",
    "EvidenceCore",
    "TraceCore",
    "MetricCore",
    "HandoffCore",
    "MiniAgentCore",
    "ValidationCore",
    "OutputCore",
    "ReviewCore",
    "BrowserCore",
    "ConfigCore",
    "ModelCore",
}


def test_registry_contains_required_subsystems():
    registry = build_subsystem_identity_registry()

    assert REQUIRED.issubset(registry)
    assert {item["subsystem_id"] for item in list_subsystem_identities()} == set(registry)
    assert get_subsystem_identity("SwarmCore")["description"] == "Multi-agent orchestration."
    assert get_subsystem_identity("ReasoningCore")["icon_id"] == "reasoning-core"
    assert get_subsystem_identity("OutputCore")["icon_id"] == "output-core"


def test_normalize_subsystem_id_falls_back_to_tracecore():
    assert normalize_subsystem_id("MemoryCore") == "MemoryCore"
    assert normalize_subsystem_id("memorycore") == "MemoryCore"
    assert normalize_subsystem_id("reasoningcore") == "ReasoningCore"
    assert normalize_subsystem_id("missing") == "TraceCore"


def test_subsystem_identity_for_trace_kind_maps_expected_kinds():
    expected = {
        "reasoning": "ReasoningCore",
        "thinking": "ReasoningCore",
        "context": "ContextCore",
        "memory": "MemoryCore",
        "skill": "SkillCore",
        "mode": "ModeCore",
        "action": "ActionCore",
        "tool": "ActionCore",
        "file": "FileCore",
        "diff": "FileCore",
        "workspace": "FileCore",
        "evidence": "EvidenceCore",
        "handoff": "HandoffCore",
        "miniagent": "MiniAgentCore",
        "metric": "MetricCore",
        "review": "ReviewCore",
        "browser": "BrowserCore",
        "config": "ConfigCore",
        "model": "ModelCore",
        "timeline": "TraceCore",
        "worklog": "TraceCore",
        "validation": "ValidationCore",
        "output": "OutputCore",
        "artifact": "OutputCore",
        "unknown": "TraceCore",
    }

    for kind, subsystem in expected.items():
        assert subsystem_identity_for_trace_kind(kind)["subsystem_id"] == subsystem


def test_apply_subsystem_identity_to_trace_item_does_not_mutate_and_sets_missing_fields():
    item = {"kind": "skill", "title": "Skill"}
    original = dict(item)

    updated = apply_subsystem_identity_to_trace_item(item)

    assert item == original
    assert updated["subsystem"] == "SkillCore"
    assert updated["icon_id"] == "skill-core"
    assert updated["badge"] == "SkillCore"
    assert updated["metadata"]["color_token"] == "trace.skill"


def test_apply_subsystem_identity_preserves_explicit_known_subsystem():
    item = {"kind": "tool", "subsystem": "ReasoningCore", "title": "Reasoning"}

    updated = apply_subsystem_identity_to_trace_item(item)

    assert updated["subsystem"] == "ReasoningCore"
    assert updated["icon_id"] == "reasoning-core"
    assert updated["metadata"]["color_token"] == "trace.reasoning"
