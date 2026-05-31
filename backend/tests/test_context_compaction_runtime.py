from backend.apps.agents.runtime.context_compaction_runtime import (
    attach_context_compaction_to_metadata,
    build_compaction_loop_guard,
    build_compaction_recovery,
    build_context_compaction_state,
    build_context_compaction_trace_source,
    build_evidence_preserving_summary,
    collect_pinned_context,
    dump_context_compaction_summary,
    estimate_compaction_token_count,
    normalize_compaction_status,
)


def _messages():
    return [
        {
            "id": "m1",
            "role": "assistant",
            "content": "private response should not be copied",
            "evidence_refs": ["ev1", "ev2"],
            "handoff_refs": ["h1"],
            "decision_refs": ["d1"],
            "blocker_refs": ["b1"],
            "validation_refs": ["v1"],
            "output_id": "out1",
            "candidate_iteration_id": "cand1",
            "task_id": "task1",
            "agent_id": "agent1",
            "swarm_id": "swarm1",
            "selected_model": "ollama/qwen",
            "provider_id": "ollama",
            "policy_gates": ["approval_required"],
        },
        {"id": "m2", "evidence_refs": ["ev2"], "task_ids": ["task1", "task2"]},
    ]


def test_context_compaction_state_normal_near_compacted_skipped():
    normal = build_context_compaction_state(original_message_count=2, trigger_ratio=0.2)
    near = build_context_compaction_state(original_message_count=2, trigger_ratio=0.7)
    compacted = build_context_compaction_state(original_message_count=4, compacted_message_count=2, compacted_through_msg_id="m2")
    skipped = build_context_compaction_state(messages=[])

    assert normal.status == "normal"
    assert near.status == "near_limit"
    assert compacted.status == "compacted"
    assert skipped.status == "skipped"
    assert normalize_compaction_status("bad") == "normal"
    assert estimate_compaction_token_count("abcd") == 1


def test_evidence_preserving_summary_preserves_critical_refs():
    summary = build_evidence_preserving_summary(_messages(), compacted_through_msg_id="m2", preserved_message_ids=["m2"])

    assert summary.status == "compacted"
    assert summary.evidence_refs == ["ev1", "ev2"]
    assert summary.handoff_refs == ["h1"]
    assert summary.decision_refs == ["d1"]
    assert summary.blocker_refs == ["b1"]
    assert summary.validation_refs == ["v1"]
    assert summary.pinned_context["output_ids"] == ["out1"]
    assert summary.pinned_context["selected_model"] == "ollama/qwen"


def test_summary_does_not_contain_sensitive_prompt_response_data():
    summary = build_evidence_preserving_summary([
        {"id": "m1", "prompt": "secret prompt", "raw_response": "secret raw", "token": "secret-token", "chain_of_thought": "hidden", "evidence_refs": ["ev1"]}
    ])
    text = str(dump_context_compaction_summary(summary)).lower()

    for forbidden in ("secret prompt", "secret raw", "secret-token", "chain_of_thought", "raw_response", "prompt"):
        assert forbidden not in text


def test_collect_pinned_context_deduplicates_and_preserves_order():
    pinned = collect_pinned_context({"evidence_refs": ["ev1", "ev2", "ev1"], "task_ids": ["t1", "t2", "t1"]})

    assert pinned.evidence_refs == ["ev1", "ev2"]
    assert pinned.task_ids == ["t1", "t2"]


def test_collect_pinned_context_extracts_runtime_and_policy_fields():
    pinned = collect_pinned_context(_messages())

    assert pinned.output_ids == ["out1"]
    assert pinned.candidate_iteration_ids == ["cand1"]
    assert pinned.task_ids == ["task1", "task2"]
    assert pinned.selected_model == "ollama/qwen"
    assert pinned.provider_id == "ollama"
    assert pinned.policy_gates == ["approval_required"]


def test_missing_evidence_refs_produce_warning_and_missing_refs():
    summary = build_evidence_preserving_summary([{"id": "m1", "output_id": "out1"}], evidence_count=2)

    assert summary.status == "recovery_required"
    assert "evidence_count_without_evidence_refs" in summary.warnings
    assert "evidence_refs" in summary.missing_refs


def test_loop_guard_blocks_same_compacted_through_message_id():
    guard = build_compaction_loop_guard(last_compacted_through_msg_id="m5", requested_compacted_through_msg_id="m5")

    assert guard.status == "blocked_repeated_target"
    assert guard.should_block is True


def test_loop_guard_blocks_max_repeats():
    guard = build_compaction_loop_guard(last_compacted_through_msg_id="m4", requested_compacted_through_msg_id="m5", repeated_compaction_count=3, max_repeated_compactions=3)

    assert guard.status == "blocked_max_repeats"
    assert guard.should_block is True


def test_recovery_ready_when_critical_refs_preserved():
    recovery = build_compaction_recovery(required_refs=["ev1", "h1"], preserved_refs=["ev1", "h1"])

    assert recovery.status == "ready"
    assert recovery.can_continue is True


def test_recovery_required_when_critical_refs_missing():
    recovery = build_compaction_recovery(required_refs=["ev1", "h1"], preserved_refs=["ev1"])

    assert recovery.status == "recovery_required"
    assert recovery.missing_refs == ["h1"]
    assert recovery.should_pause is True


def test_attach_context_compaction_to_metadata_does_not_mutate_original():
    metadata = {"safe": True}
    summary = build_evidence_preserving_summary(_messages())
    attached = attach_context_compaction_to_metadata(metadata, summary=summary)

    assert metadata == {"safe": True}
    assert attached["safe"] is True
    assert attached["context_compaction"]["summary"]["evidence_refs"] == ["ev1", "ev2"]


def test_context_compaction_trace_source_is_safe():
    state = build_context_compaction_state(original_message_count=2, compacted_message_count=1, compacted_through_msg_id="m1")
    summary = build_evidence_preserving_summary([{"id": "m1", "evidence_refs": ["ev1"], "secret_token": "leak"}])
    recovery = build_compaction_recovery(required_refs=["ev1"], preserved_refs=["ev1"])
    trace = build_context_compaction_trace_source(state=state, summary=summary, recovery=recovery, metadata={"prompt": "leak"})
    text = str(trace).lower()

    assert trace["source_kind"] == "context_compaction"
    assert trace["summary"]["evidence_refs"] == ["ev1"]
    for forbidden in ("leak", "secret_token", "prompt", "raw_response", "chain_of_thought"):
        assert forbidden not in text
