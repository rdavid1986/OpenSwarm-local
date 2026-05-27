from datetime import datetime, timezone

import pytest

from backend.apps.runtime_timing import (
    RuntimeTimerRecord,
    cancel_runtime_timer,
    dump_runtime_timer,
    fail_runtime_timer,
    finish_runtime_timer,
    normalize_runtime_timer_scope,
    normalize_runtime_timer_state,
    normalize_runtime_timer_status,
    runtime_timer_duration_ms,
    start_runtime_timer,
)


START = "2026-05-27T10:00:00Z"
FINISH = "2026-05-27T10:00:01.250Z"


def test_start_runtime_timer_defaults_to_running_without_duration():
    timer = start_runtime_timer(
        timer_id="timer-1",
        scope="mini_agent",
        label="Run task",
        state="thinking",
        started_at=START,
        swarm_id="swarm-1",
        agent_id="agent-1",
        mini_agent_id="mini-1",
        task_id="task-1",
        model="ollama/qwen3.6:latest",
        route="app_builder",
        flow="implementation",
        output_id="out-1",
        candidate_iteration_id="iter-1",
        evidence_refs=["ev-1"],
        metadata={"safe": True},
    )

    assert isinstance(timer, RuntimeTimerRecord)
    assert timer.timer_id == "timer-1"
    assert timer.scope == "mini_agent"
    assert timer.state == "thinking"
    assert timer.status == "running"
    assert timer.started_at == START
    assert timer.finished_at is None
    assert timer.duration_ms is None
    assert timer.evidence_refs == ["ev-1"]
    assert timer.metadata == {"safe": True}


def test_finish_runtime_timer_calculates_duration_ms_without_mutating_original():
    timer = start_runtime_timer(timer_id="timer-2", scope="model_call", label="Call", started_at=START)

    finished = finish_runtime_timer(timer, finished_at=FINISH)

    assert timer.status == "running"
    assert timer.duration_ms is None
    assert finished.status == "completed"
    assert finished.state == "completed"
    assert finished.finished_at == FINISH
    assert finished.duration_ms == 1250


def test_fail_runtime_timer_marks_failed_and_stores_error():
    timer = start_runtime_timer(timer_id="timer-3", scope="tool_call", label="Tool", started_at=START)

    failed = fail_runtime_timer(timer, error="boom", finished_at=FINISH)

    assert failed.status == "failed"
    assert failed.state == "failed"
    assert failed.error == "boom"
    assert failed.duration_ms == 1250


def test_cancel_runtime_timer_marks_cancelled():
    timer = start_runtime_timer(timer_id="timer-4", scope="validation", label="Validate", started_at=START)

    cancelled = cancel_runtime_timer(timer, error="user stopped", finished_at=FINISH)

    assert cancelled.status == "cancelled"
    assert cancelled.state == "cancelled"
    assert cancelled.error == "user stopped"
    assert cancelled.duration_ms == 1250


def test_runtime_timer_duration_ms_accepts_record_dict_and_datetimes():
    timer = start_runtime_timer(timer_id="timer-5", scope="planner", label="Plan", started_at=START)

    assert runtime_timer_duration_ms(timer, FINISH) == 1250
    assert runtime_timer_duration_ms({"started_at": START, "finished_at": FINISH}) == 1250
    assert runtime_timer_duration_ms(
        datetime(2026, 5, 27, 10, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 5, 27, 10, 0, 2, tzinfo=timezone.utc),
    ) == 2000


def test_normalizers_degrade_unknown_values_and_can_reject_strictly():
    assert normalize_runtime_timer_scope("not-real") == "model_call"
    assert normalize_runtime_timer_state("not-real") == "working"
    assert normalize_runtime_timer_status("not-real") == "running"
    assert normalize_runtime_timer_scope(" SWARM ") == "swarm"
    assert normalize_runtime_timer_state(" Loading_Model ") == "loading_model"

    with pytest.raises(ValueError):
        normalize_runtime_timer_scope("not-real", strict=True)
    with pytest.raises(ValueError):
        normalize_runtime_timer_state("not-real", strict=True)
    with pytest.raises(ValueError):
        normalize_runtime_timer_status("not-real", strict=True)


def test_dump_runtime_timer_is_json_safe_dict():
    timer = start_runtime_timer(
        timer_id="timer-6",
        scope="benchmark_test",
        label="Bench",
        started_at=START,
        metadata={"when": datetime(2026, 5, 27, 10, 0, tzinfo=timezone.utc), "items": {1, 2}},
    )
    finished = finish_runtime_timer(timer, finished_at=FINISH)

    dumped = dump_runtime_timer(finished)

    assert dumped["timer_id"] == "timer-6"
    assert dumped["status"] == "completed"
    assert dumped["duration_ms"] == 1250
    assert dumped["metadata"]["when"] == "2026-05-27T10:00:00+00:00"
    assert sorted(dumped["metadata"]["items"]) == [1, 2]
