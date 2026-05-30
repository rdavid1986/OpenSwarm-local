import json
from copy import deepcopy

from backend.apps.swarms.miniagent_task_metrics import (
    METRIC_KIND,
    build_miniagent_task_runtime_metric,
    build_miniagent_task_runtime_timeline_event,
    fail_miniagent_task_runtime_metric,
    finish_miniagent_task_runtime_metric,
    start_miniagent_task_runtime_metric,
    summarize_miniagent_task_runtime_metrics,
)

START = "2026-05-30T10:00:00Z"
FINISH = "2026-05-30T10:00:02.500Z"


def test_build_metric_contract_is_safe_and_counts_refs():
    metric = build_miniagent_task_runtime_metric(
        swarm_id="swarm-1",
        agent_id="agent-1",
        miniagent_id="mini-1",
        task_id="task-1",
        attempt_id="attempt-1",
        skill_id="skill-1",
        mode_id="app_builder",
        model="qwen2.5-coder:14b",
        provider="ollama",
        started_at=START,
        finished_at=FINISH,
        evidence_refs=["ev-1", "ev-2"],
        artifacts=["artifact-1"],
        files_changed=["index.html"],
        blockers=[{"summary": "blocked", "chain_of_thought": "hidden"}],
        metadata={"chain_of_thought": "hidden", "safe": True},
    )

    dumped = json.dumps(metric)
    assert metric["metric_kind"] == METRIC_KIND
    assert metric["status"] == "planned"
    assert metric["duration_ms"] == 2500
    assert metric["evidence_count"] == 2
    assert metric["artifacts_count"] == 1
    assert metric["files_changed_count"] == 1
    assert metric["blockers_count"] == 1
    assert "chain_of_thought" not in dumped


def test_start_metric_uses_runtime_timer_without_persistence():
    metric = start_miniagent_task_runtime_metric(
        swarm_id="swarm-1",
        agent_id="agent-1",
        miniagent_id="mini-1",
        task_id="task-1",
        started_at=START,
        model="qwen2.5-coder:14b",
    )

    assert metric["status"] == "running"
    assert metric["runtime_timer"]["scope"] == "mini_agent"
    assert metric["runtime_timer"]["mini_agent_id"] == "mini-1"
    assert metric["runtime_timer"]["task_id"] == "task-1"
    assert metric["runtime_timer"]["model"] == "qwen2.5-coder:14b"


def test_finish_metric_calculates_duration_without_mutating_original():
    metric = build_miniagent_task_runtime_metric(task_id="task-1", started_at=START)
    before = deepcopy(metric)

    finished = finish_miniagent_task_runtime_metric(metric, finished_at=FINISH, evidence_refs=["ev-1"])

    assert metric == before
    assert finished["status"] == "completed"
    assert finished["duration_ms"] == 2500
    assert finished["evidence_count"] == 1


def test_fail_metric_marks_failed_and_records_safe_error():
    metric = build_miniagent_task_runtime_metric(task_id="task-1", started_at=START)
    failed = fail_miniagent_task_runtime_metric(metric, error="provider_timeout", finished_at=FINISH)

    assert failed["status"] == "failed"
    assert failed["duration_ms"] == 2500
    assert failed["metadata"]["error"] == "provider_timeout"


def test_summary_aggregates_counts_and_durations_without_mutating():
    metrics = [
        build_miniagent_task_runtime_metric(status="completed", duration_ms=1000, evidence_refs=["ev-1"]),
        build_miniagent_task_runtime_metric(status="failed", duration_ms=3000, blockers=["b1"]),
        build_miniagent_task_runtime_metric(status="running"),
    ]
    before = deepcopy(metrics)

    summary = summarize_miniagent_task_runtime_metrics(metrics)

    assert metrics == before
    assert summary["metric_count"] == 3
    assert summary["completed_count"] == 1
    assert summary["failed_count"] == 1
    assert summary["running_count"] == 1
    assert summary["total_duration_ms"] == 4000
    assert summary["average_duration_ms"] == 2000
    assert summary["total_evidence_count"] == 1
    assert summary["total_blockers_count"] == 1


def test_timeline_event_is_user_visible_and_status_aware():
    metric = build_miniagent_task_runtime_metric(
        status="failed",
        task_id="task-1",
        miniagent_id="mini-1",
        skill_id="skill-1",
        started_at=START,
        finished_at=FINISH,
        evidence_refs=["ev-1"],
    )

    event = build_miniagent_task_runtime_timeline_event(metric)

    assert event["event_type"] == "miniagent_runtime_metric"
    assert event["severity"] == "error"
    assert event["visible_to_user"] is True
    assert event["internal_only"] is False
    assert event["evidence_refs"] == ["ev-1"]
