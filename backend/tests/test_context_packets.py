import json

from backend.apps.swarms.context_packets import (
    build_context_packet,
    build_context_packet_item,
    build_context_packet_state_context_section,
    build_context_packet_trace_source,
    build_memory_tier_index,
    normalize_context_packet_value,
)


def test_context_packet_item_redacts_sensitive_fields():
    item = build_context_packet_item(
        source_kind="project_memory",
        source_id="mem1",
        summary="Use accepted output.",
        evidence_refs=["ev1"],
        confidence=0.9,
        metadata={"api_key": "secret", "safe": "ok", "raw_prompt": "hidden"},
    )

    text = json.dumps(item)

    assert item["trust"] == "usable"
    assert item["evidence_refs"] == ["ev1"]
    assert "secret" not in text
    assert "raw_prompt" not in text
    assert item["metadata"]["safe"] == "ok"


def test_context_packet_builds_tiers_budget_quality_and_handoff():
    item = build_context_packet_item(
        source_kind="handoff",
        source_id="h1",
        summary="Previous MiniAgent inspected files.",
        memory_tier="handoff_memory",
        evidence_refs=["ev1"],
        confidence=0.8,
        token_cost=50,
    )
    handoff = {
        "handoff_kind": "miniagent_handoff",
        "handoff_version": "openswarm.miniagent_handoff.v1",
        "handoff_id": "h1",
        "target_agent_id": "mini2",
        "completed_work_summary": "Inspected files.",
        "evidence_refs": ["ev1"],
        "recommended_next_steps": ["continue"],
    }

    packet = build_context_packet(
        target_id="mini2",
        task_id="task1",
        goal="Build feature",
        items=[item],
        handoffs=[handoff],
        context_budget_total=1000,
        reserved_response_budget=200,
    )

    assert packet["packet_kind"] == "context_packet"
    assert packet["status"] == "ready"
    assert packet["memory_tiers"]["handoff_memory"][0]["source_id"] == "h1"
    assert packet["handoff_context"]["handoff_ids"] == ["h1"]
    assert packet["context_budget"]["context_budget_status"] == "within_budget"
    assert packet["context_quality_gate"]["ok"] is True


def test_context_packet_marks_stale_context_for_review():
    item = build_context_packet_item(
        source_kind="workspace",
        source_id="old",
        summary="Old workspace snapshot.",
        freshness="stale",
        confidence=0.7,
        token_cost=10,
    )

    packet = build_context_packet(items=[item], context_budget_total=100)

    assert packet["status"] == "needs_review"
    assert "context_quality_stale" in packet["warnings"]
    assert "review_context_packet_quality" in packet["required_actions"]


def test_context_packet_state_context_section_does_not_authorize_actions():
    item = build_context_packet_item(
        source_kind="skill",
        source_id="s1",
        summary="Use summary only.",
        memory_tier="skill_script_memory",
    )
    packet = build_context_packet(items=[item])

    section = build_context_packet_state_context_section(packet)

    assert section["kind"] == "context_packet"
    assert "Use summary only." in section["content"]
    assert section["metadata"]["injection_authorizes_actions"] is False
    assert section["metadata"]["can_execute_tools"] is False
    assert section["metadata"]["can_mutate_memory"] is False


def test_context_packet_trace_source_is_compact():
    item = build_context_packet_item(source_kind="project_memory", source_id="m1", summary="Decision exists.")
    packet = build_context_packet(items=[item], target_id="mini1")

    source = build_context_packet_trace_source(packet)

    assert source["source_kind"] == "context_packet"
    assert source["packet_kind"] == "context_packet"
    assert source["item_count"] == 1
    assert source["target_id"] == "mini1"
    assert "context_budget" in source


def test_memory_tier_index_groups_items():
    a = build_context_packet_item(source_kind="a", source_id="a1", memory_tier="core_memory")
    b = build_context_packet_item(source_kind="b", source_id="b1", memory_tier="core_memory")
    c = build_context_packet_item(source_kind="c", source_id="c1", memory_tier="unknown")

    tiers = build_memory_tier_index([a, b, c])

    assert len(tiers["core_memory"]) == 2
    assert tiers["task_working_memory"][0]["source_id"] == "c1"


def test_normalizer_bounds_and_redacts_nested_values():
    value = {
        "safe": "x" * 2000,
        "nested": {"password": "hidden", "visible": "ok"},
        "items": list(range(60)),
    }

    normalized = normalize_context_packet_value(value)

    assert len(normalized["safe"]) <= 1203
    assert "password" not in normalized["nested"]
    assert normalized["nested"]["visible"] == "ok"
    assert normalized["items"][-1].startswith("+")
