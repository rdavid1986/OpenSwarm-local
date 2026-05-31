from backend.apps.agents.runtime.context_compaction_runtime import (
    build_compaction_loop_guard,
    build_compaction_recovery,
    build_context_compaction_state,
    build_context_compaction_trace_source,
    build_evidence_preserving_summary,
)
from backend.apps.swarms.process_trace_builder import build_process_trace_item_from_source, normalize_process_trace_source_kind


def test_process_trace_recognizes_context_compaction():
    state = build_context_compaction_state(original_message_count=3, compacted_message_count=2, compacted_through_msg_id="m2")
    summary = build_evidence_preserving_summary([{"id": "m1", "evidence_refs": ["ev1"], "task_id": "task1", "agent_id": "agent1"}], compacted_through_msg_id="m1")
    source = build_context_compaction_trace_source(state=state, summary=summary)

    assert normalize_process_trace_source_kind(source) == "context_compaction"
    item = build_process_trace_item_from_source(source)

    assert item["kind"] == "memory"
    assert item["subsystem"] == "MemoryCore"
    assert item["details"]["source_kind"] == "context_compaction"
    assert item["evidence_refs"] == ["ev1"]
    assert item["related_task_id"] == "task1"


def test_context_compaction_process_trace_details_are_redacted():
    source = {
        "source_kind": "context_compaction",
        "compaction_kind": "context_compaction_runtime",
        "state": {"status": "compacted", "prompt": "leak"},
        "summary": {"status": "compacted", "raw_response": "leak", "pinned_context": {"evidence_refs": ["ev1"], "secret_token": "leak"}},
    }

    item = build_process_trace_item_from_source(source)
    text = str(item).lower()

    for forbidden in ("leak", "prompt", "raw_response", "secret_token"):
        assert forbidden not in text


def test_context_compaction_process_trace_status_reflects_recovery_required():
    state = build_context_compaction_state(status="recovery_required", reason="missing_refs")
    summary = build_evidence_preserving_summary([{"id": "m1", "output_id": "out1"}], evidence_count=1)
    recovery = build_compaction_recovery(required_refs=["ev1"], preserved_refs=[])
    guard = build_compaction_loop_guard(previous_status="recovery_required")
    item = build_process_trace_item_from_source(build_context_compaction_trace_source(state=state, summary=summary, loop_guard=guard, recovery=recovery))

    assert item["status"] == "blocked"
    assert item["details"]["recovery"]["status"] == "recovery_required"
    assert item["details"]["loop_guard"]["should_block"] is True
