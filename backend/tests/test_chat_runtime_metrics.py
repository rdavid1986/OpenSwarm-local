from backend.apps.chat_runtime_metrics import (
    METRIC_KIND,
    classify_chat_metric_safe_metadata,
    dump_chat_response_metric,
    fail_chat_response_metric,
    finish_chat_response_metric,
    mark_chat_response_first_token,
    sanitize_chat_metric_metadata,
    start_chat_response_metric,
)


START = "2026-05-30T10:00:00Z"
FIRST = "2026-05-30T10:00:00.250Z"
FINISH = "2026-05-30T10:00:01.500Z"


def test_start_chat_response_metric_defaults_to_running_and_reuses_timer():
    metric = start_chat_response_metric(
        response_metric_id="metric-1",
        conversation_id="conv-1",
        message_id="msg-1",
        card_id="swarm-1",
        card_type="swarm",
        mode="ask",
        route="experimental_chat",
        flow="chat",
        model="qwen2.5-coder:14b",
        provider="ollama",
        started_at=START,
        evidence_refs=["ev-1"],
        metadata={"safe": True},
    )

    assert metric.metric_kind == METRIC_KIND
    assert metric.status == "running"
    assert metric.started_at == START
    assert metric.duration_ms is None
    assert metric.runtime_timer is not None
    assert metric.runtime_timer.swarm_id == "swarm-1"
    assert metric.runtime_timer.model == "qwen2.5-coder:14b"
    assert metric.evidence_refs == ["ev-1"]


def test_mark_first_token_and_finish_calculates_durations_without_mutating_original():
    metric = start_chat_response_metric(response_metric_id="metric-2", started_at=START, card_type="agent")
    with_first = mark_chat_response_first_token(metric, first_token_at=FIRST)
    finished = finish_chat_response_metric(with_first, finished_at=FINISH, model_ms=1000, context_build_ms=125)

    assert metric.first_token_at is None
    assert with_first.queue_ms == 250
    assert finished.status == "completed"
    assert finished.duration_ms == 1500
    assert finished.model_ms == 1000
    assert finished.context_build_ms == 125
    assert finished.runtime_timer is not None
    assert finished.runtime_timer.status == "completed"


def test_fail_chat_response_metric_marks_error_and_duration():
    metric = start_chat_response_metric(response_metric_id="metric-3", started_at=START)
    failed = fail_chat_response_metric(metric, error_type="provider_timeout", finished_at=FINISH)

    assert failed.status == "failed"
    assert failed.error_type == "provider_timeout"
    assert failed.duration_ms == 1500
    assert failed.runtime_timer is not None
    assert failed.runtime_timer.status == "failed"


def test_dump_chat_response_metric_is_json_safe_and_redacts_sensitive_metadata():
    metric = start_chat_response_metric(
        response_metric_id="metric-4",
        started_at=START,
        metadata={
            "safe": {"nested": True},
            "api_key": "secret",
            "prompt": "full user text",
            "items": {2, 1},
        },
    )
    dumped = dump_chat_response_metric(finish_chat_response_metric(metric, finished_at=FINISH))

    assert dumped["response_metric_id"] == "metric-4"
    assert dumped["duration_ms"] == 1500
    assert dumped["metadata"]["api_key"] == "[redacted]"
    assert dumped["metadata"]["prompt"] == "[redacted]"
    assert dumped["metadata"]["safe"]["nested"] is True
    assert sorted(dumped["metadata"]["items"]) == [1, 2]
    assert "chain_of_thought" not in dumped


def test_sanitize_chat_metric_metadata_redacts_nested_sensitive_keys():
    safe = sanitize_chat_metric_metadata({
        "outer": {"token": "abc", "ok": 1},
        "messages": ["should not persist"],
        "normal": "value",
    })

    assert safe["outer"]["token"] == "[redacted]"
    assert safe["outer"]["ok"] == 1
    assert safe["messages"] == "[redacted]"
    assert safe["normal"] == "value"


def test_classify_chat_metric_safe_metadata_uses_mode_route_flow_without_content():
    assert classify_chat_metric_safe_metadata({"mode": "ask", "card_type": "agent"})["task_type"] == "ask"
    assert classify_chat_metric_safe_metadata({"mode": "debug"})["task_type"] == "debug"
    assert classify_chat_metric_safe_metadata({"route": "app_builder", "card_type": "swarm"})["project_type"] == "application"
    assert classify_chat_metric_safe_metadata({"flow": "skill_builder"})["task_type"] == "skill_builder"
    assert classify_chat_metric_safe_metadata({})["task_type"] == "unknown"


def test_classify_chat_metric_safe_metadata_covers_safe_task_categories():
    cases = [
        ({"route": "skill_import"}, "skill_import", "skill", "skill_import"),
        ({"route": "skill_review"}, "skill_review", "skill", "review"),
        ({"flow": "preview_refinement", "created_output": True}, "refinement", "application", "refine"),
        ({"mode": "browser-agent", "requires_research": True}, "research", "research", "research"),
        ({"used_tools": ["SafeShell"], "used_actions": ["run_command"]}, "tool_action", "unknown", "execute"),
        ({"artifact_kind": "unity_game_3d"}, "game_3d", "game_3d", "build"),
        ({"route": "desktop_windows_app"}, "desktop_app", "desktop_app", "build"),
        ({"route": "android_mobile"}, "mobile_app", "mobile_app", "build"),
        ({"artifact_kind": "static_app"}, "app_builder", "application", "build"),
        ({"mode": "configuration"}, "configuration", "unknown", "configure"),
    ]

    for metadata, task_type, project_type, intent_type in cases:
        classified = classify_chat_metric_safe_metadata(metadata)
        assert classified["task_type"] == task_type
        assert classified["project_type"] == project_type
        assert classified["intent_type"] == intent_type


def test_classify_chat_metric_safe_metadata_ignores_private_content_fields():
    classified = classify_chat_metric_safe_metadata({
        "mode": "ask",
        "prompt": "create a unity game",
        "response": "private answer",
        "message": "debug this",
        "body": "skill import request",
        "text": "browser research",
        "raw": {"content": "desktop app"},
    })

    assert classified["task_type"] == "ask"
    assert classified["project_type"] == "unknown"


def test_classify_chat_metric_safe_metadata_warns_when_research_flag_conflicts():
    classified = classify_chat_metric_safe_metadata({"mode": "ask", "requires_research": True})

    assert classified["task_type"] == "ask"
    assert classified["requires_research"] is True
    assert "requires_research_without_research_task_type" in classified["warnings"]
