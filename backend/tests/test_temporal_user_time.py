from backend.apps.swarms.process_trace_builder import build_process_trace_item_from_source, normalize_process_trace_source_kind
from backend.apps.swarms.temporal_runtime import (
    build_break_reminder_decision,
    build_break_reminder_policy,
    build_personal_work_time_record,
    build_project_dashboard_time_summary,
    build_temporal_user_time_trace_source,
    classify_active_idle_time,
    dump_temporal_user_time_trace_source,
)

START = "2026-05-31T10:00:00Z"
MID = "2026-05-31T10:10:00Z"
LATER = "2026-05-31T11:00:00Z"


def test_active_event_sums_active_work_time():
    record = build_personal_work_time_record(activity_kind="user_input", started_at=START, completed_at=MID, project_id="p1")

    assert record.duration_ms == 600000
    assert record.active_work_ms == 600000
    assert record.idle_ms == 0
    assert record.project_id == "p1"
    assert record.local_only is True


def test_idle_event_does_not_sum_active_work_time():
    record = build_personal_work_time_record(activity_kind="idle", started_at=START, completed_at=MID)

    assert record.active_work_ms == 0
    assert record.idle_ms == 600000


def test_idle_threshold_classifies_idle():
    classification = classify_active_idle_time(last_user_input_at=START, current_time=MID, idle_threshold_ms=300000)

    assert classification.status == "idle_time"
    assert classification.idle_time_ms == 600000
    assert classification.active_work_time_ms == 0


def test_background_does_not_count_when_not_allowed():
    classification = classify_active_idle_time(last_user_input_at=START, current_time=MID, idle_threshold_ms=900000, is_background=True, background_allowed=False)

    assert classification.status == "idle_time"
    assert classification.active_work_time_ms == 0
    assert classification.background_time_ms == 0
    assert "background_activity_not_counted" in classification.warnings


def test_agent_run_sums_separately_from_user_active_time():
    classification = classify_active_idle_time(active_agent_run_started_at=START, current_time=MID, last_user_input_at=START)
    record = build_personal_work_time_record(activity_kind="agent_run", started_at=START, completed_at=MID)

    assert classification.agent_run_time_ms == 600000
    assert classification.active_work_time_ms == 0
    assert record.agent_run_ms == 600000
    assert record.active_work_ms == 0


def test_project_dashboard_summary_orders_by_most_time_and_averages_sessions():
    records = [
        build_personal_work_time_record(activity_kind="user_input", started_at=START, completed_at=MID, project_id="p1", dashboard_id="d1", swarm_id="s1", agent_id="a1"),
        build_personal_work_time_record(activity_kind="qa_run", duration_ms=1200000, project_id="p2", dashboard_id="d2", agent_id="a2"),
        build_personal_work_time_record(activity_kind="agent_run", duration_ms=300000, project_id="p1", dashboard_id="d1", agent_id="a1"),
    ]
    summary = build_project_dashboard_time_summary(records, sort_key="most_time")

    assert summary.total_by_project["p1"] == 900000
    assert summary.total_by_project["p2"] == 1200000
    assert summary.sorted_refs[0] == "p2"
    assert summary.session_count == 3
    assert summary.longest_session_ms == 1200000
    assert summary.average_session_ms == 700000
    assert summary.total_by_activity_kind["qa_run"] == 1200000


def test_break_reminder_not_due_before_interval():
    policy = build_break_reminder_policy(interval_minutes=60, created_at=START)
    decision = build_break_reminder_decision(policy, current_time=MID, is_active=True)

    assert decision.decision == "not_due"
    assert decision.should_notify is False


def test_break_reminder_notify_after_active_interval():
    policy = build_break_reminder_policy(interval_minutes=30, created_at=START)
    decision = build_break_reminder_decision(policy, current_time=LATER, is_active=True)

    assert decision.decision == "notify"
    assert decision.should_notify is True
    assert "show_break_reminder" in decision.required_actions


def test_break_reminder_snooze_respects_snooze_minutes():
    policy = build_break_reminder_policy(interval_minutes=30, snooze_minutes=15, last_reminder_at=MID)
    decision = build_break_reminder_decision(policy, current_time="2026-05-31T10:20:00Z", is_active=True, snoozed=True)

    assert decision.decision == "snooze"
    assert decision.should_snooze is True
    assert decision.should_notify is False


def test_disabled_policy_does_not_notify():
    policy = build_break_reminder_policy(enabled=False, interval_minutes=1, created_at=START)
    decision = build_break_reminder_decision(policy, current_time=LATER, is_active=True)

    assert decision.decision == "disabled"
    assert decision.should_notify is False


def test_temporal_user_time_trace_is_local_only_and_redacted():
    record = build_personal_work_time_record(activity_kind="approval_review", duration_ms=1000, project_id="p1", dashboard_id="d1", metadata={"prompt": "leak"})
    decision = build_break_reminder_decision(build_break_reminder_policy(interval_minutes=1, created_at=START), current_time=LATER)
    source = build_temporal_user_time_trace_source(record=record, break_decision=decision, metadata={"secret_token": "leak", "trace_id": "trace-user-time"})
    text = str(source).lower()

    assert source["source_kind"] == "temporal_user_time"
    assert source["local_only"] is True
    assert source["can_send_telemetry"] is False
    assert source["can_share_community"] is False
    assert "leak" not in text
    assert "secret_token" not in text
    assert "prompt" not in text


def test_temporal_user_time_process_trace_marks_local_only_and_no_telemetry():
    record = build_personal_work_time_record(activity_kind="agent_run", duration_ms=2000, project_id="p1", dashboard_id="d1")
    source = build_temporal_user_time_trace_source(record=record)
    item = build_process_trace_item_from_source(source)

    assert normalize_process_trace_source_kind(source) == "temporal_user_time"
    assert item["subsystem"] == "RuntimeCore"
    assert item["details"]["local_only"] is True
    assert item["details"]["can_send_telemetry"] is False
    assert item["details"]["can_share_community"] is False
    assert item["details"]["can_execute_model"] is False


def test_dump_temporal_user_time_trace_source_is_safe():
    source = dump_temporal_user_time_trace_source({"source_kind": "temporal_user_time", "active_ms": 1, "raw_response": "leak"})

    assert source["active_ms"] == 1
    assert "raw_response" not in source
