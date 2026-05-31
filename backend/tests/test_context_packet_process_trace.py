from backend.apps.swarms.context_packets import build_context_packet, build_context_packet_item, build_context_packet_trace_source
from backend.apps.swarms.process_trace_builder import build_process_trace_item_from_source, normalize_process_trace_source_kind


def test_process_trace_recognizes_context_packet():
    item_source = build_context_packet_item(
        source_kind="project_memory",
        source_id="mem1",
        summary="Use accepted project decision.",
        evidence_refs=["ev1"],
        confidence=0.9,
    )
    packet = build_context_packet(
        packet_id="packet1",
        target_id="mini1",
        task_id="task1",
        items=[item_source],
        context_budget_total=1000,
    )
    source = build_context_packet_trace_source(packet)

    assert normalize_process_trace_source_kind(source) == "context_packet"

    item = build_process_trace_item_from_source(source)

    assert item["kind"] == "context"
    assert item["subsystem"] == "ContextCore"
    assert item["details"]["source_kind"] == "context_packet"
    assert item["details"]["packet_id"] == "packet1"
    assert item["related_task_id"] == "task1"
    assert item["related_agent_id"] == "mini1"
    assert item["evidence_refs"] == ["ev1"]


def test_context_packet_process_trace_warns_on_quality_review():
    item_source = build_context_packet_item(
        source_kind="workspace",
        source_id="old",
        summary="Old context.",
        freshness="stale",
    )
    packet = build_context_packet(packet_id="packet2", items=[item_source], context_budget_total=100)
    source = build_context_packet_trace_source(packet)

    item = build_process_trace_item_from_source(source)

    assert item["status"] == "warning"
    assert item["details"]["context_quality_gate"]["status"] == "stale"
    assert "review_context_packet_quality" in item["details"]["required_actions"]


def test_context_packet_process_trace_is_redacted():
    source = {
        "source_kind": "context_packet",
        "packet_kind": "context_packet",
        "packet_id": "packet3",
        "status": "ready",
        "metadata": {"raw_prompt": "leak", "secret_token": "leak"},
        "memory_tiers": {"core_memory": [{"source_id": "m1", "evidence_refs": ["ev1"], "raw_response": "leak"}]},
        "context_quality_gate": {"status": "sufficient"},
    }

    item = build_process_trace_item_from_source(source)
    text = str(item).lower()

    assert item["subsystem"] == "ContextCore"
    assert "leak" not in text
    assert "raw_prompt" not in text
    assert "secret_token" not in text
    assert "raw_response" not in text
