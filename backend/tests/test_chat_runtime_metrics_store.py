import copy
import json

from backend.apps.chat_runtime_metrics import (
    finish_chat_response_metric,
    start_chat_response_metric,
)
from backend.apps.chat_runtime_metrics_store import (
    append_chat_response_metric,
    get_default_chat_response_metrics_path,
    list_chat_response_metrics,
    summarize_chat_response_metrics,
)


START = "2026-05-30T10:00:00Z"
FINISH = "2026-05-30T10:00:01.000Z"


def _metric(**overrides):
    data = {
        "response_metric_id": "metric-1",
        "card_type": "agent",
        "mode": "ask",
        "model": "model-a",
        "status": "completed",
        "started_at": START,
        "finished_at": FINISH,
        "duration_ms": 1000,
        "queue_ms": 100,
        "metadata": {"safe": True},
    }
    data.update(overrides)
    return data


def test_default_path_uses_backend_data_metrics_jsonl():
    path = get_default_chat_response_metrics_path()

    assert path.name == "chat_response_metrics.jsonl"
    assert path.parent.name == "metrics"
    assert path.parent.parent.name == "data"


def test_append_creates_file_and_directory(tmp_path):
    path = tmp_path / "missing" / "metrics.jsonl"

    persisted = append_chat_response_metric(_metric(), path=path)

    assert path.exists()
    assert persisted["response_metric_id"] == "metric-1"
    assert path.read_text(encoding="utf-8").strip()


def test_append_accepts_chat_response_metric(tmp_path):
    path = tmp_path / "metrics.jsonl"
    metric = finish_chat_response_metric(
        start_chat_response_metric(
            response_metric_id="metric-object",
            card_type="swarm",
            mode="build",
            model="model-b",
            started_at=START,
            metadata={"safe": "ok"},
        ),
        finished_at=FINISH,
    )

    persisted = append_chat_response_metric(metric, path=path)

    assert persisted["response_metric_id"] == "metric-object"
    assert persisted["card_type"] == "swarm"
    assert persisted["status"] == "completed"


def test_append_accepts_dict_and_writes_valid_jsonl(tmp_path):
    path = tmp_path / "metrics.jsonl"

    append_chat_response_metric(_metric(response_metric_id="metric-a"), path=path)
    append_chat_response_metric(_metric(response_metric_id="metric-b"), path=path)

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert [json.loads(line)["response_metric_id"] for line in lines] == ["metric-a", "metric-b"]


def test_list_tolerates_missing_empty_and_corrupt_files(tmp_path):
    missing = tmp_path / "missing.jsonl"
    empty = tmp_path / "empty.jsonl"
    corrupt = tmp_path / "corrupt.jsonl"
    empty.write_text("", encoding="utf-8")
    corrupt.write_text('{"response_metric_id":"ok"}\nnot-json\n[]\n', encoding="utf-8")

    assert list_chat_response_metrics(path=missing) == []
    assert list_chat_response_metrics(path=empty) == []
    assert list_chat_response_metrics(path=corrupt) == [{"response_metric_id": "ok"}]


def test_list_returns_newest_first_and_limit_works(tmp_path):
    path = tmp_path / "metrics.jsonl"
    for index in range(3):
        append_chat_response_metric(_metric(response_metric_id=f"metric-{index}"), path=path)

    metrics = list_chat_response_metrics(path=path, limit=2)

    assert [metric["response_metric_id"] for metric in metrics] == ["metric-2", "metric-1"]


def test_list_filters_by_card_type_mode_model_and_status(tmp_path):
    path = tmp_path / "metrics.jsonl"
    append_chat_response_metric(_metric(response_metric_id="agent-ask", card_type="agent", mode="ask", model="a", status="completed"), path=path)
    append_chat_response_metric(_metric(response_metric_id="swarm-build", card_type="swarm", mode="build", model="b", status="failed"), path=path)

    assert [m["response_metric_id"] for m in list_chat_response_metrics(path=path, card_type="agent")] == ["agent-ask"]
    assert [m["response_metric_id"] for m in list_chat_response_metrics(path=path, mode="build")] == ["swarm-build"]
    assert [m["response_metric_id"] for m in list_chat_response_metrics(path=path, model="a")] == ["agent-ask"]
    assert [m["response_metric_id"] for m in list_chat_response_metrics(path=path, status="failed")] == ["swarm-build"]


def test_append_redacts_sensitive_metadata_and_chain_of_thought(tmp_path):
    path = tmp_path / "metrics.jsonl"
    persisted = append_chat_response_metric(
        _metric(
            chain_of_thought="private reasoning",
            metadata={
                "api_key": "key",
                "token": "token",
                "password": "password",
                "secret": "secret",
                "credential": "credential",
                "private_key": "private",
                "authorization": "bearer token",
                "cookie": "cookie",
                "set-cookie": "set-cookie",
                "nested": {"access_token": "nested-token", "safe": "ok"},
            },
        ),
        path=path,
    )

    assert "chain_of_thought" not in persisted
    metadata = persisted["metadata"]
    for key in ("api_key", "token", "password", "secret", "credential", "private_key", "authorization", "cookie", "set-cookie"):
        assert metadata[key] == "[redacted]"
    assert metadata["nested"]["access_token"] == "[redacted]"
    assert metadata["nested"]["safe"] == "ok"


def test_append_does_not_persist_full_prompt_content_body_message_response(tmp_path):
    path = tmp_path / "metrics.jsonl"
    secret_text = "full private user or assistant text"

    persisted = append_chat_response_metric(
        _metric(metadata={key: secret_text for key in ("prompt", "content", "body", "message", "response", "text", "raw", "request")}),
        path=path,
    )

    assert secret_text not in path.read_text(encoding="utf-8")
    assert all(value == "[redacted]" for value in persisted["metadata"].values())


def test_summarize_calculates_counts_and_duration_stats():
    metrics = [
        _metric(response_metric_id="a", duration_ms=100, queue_ms=10, status="completed"),
        _metric(response_metric_id="b", duration_ms=300, queue_ms=30, status="failed", error_type="provider_timeout"),
        _metric(response_metric_id="c", duration_ms=None, queue_ms=None, status="running"),
    ]

    summary = summarize_chat_response_metrics(metrics)

    assert summary["count"] == 3
    assert summary["completed_count"] == 1
    assert summary["failed_count"] == 1
    assert summary["error_count"] == 1
    assert summary["average_duration_ms"] == 200
    assert summary["max_duration_ms"] == 300
    assert summary["min_duration_ms"] == 100
    assert summary["average_queue_ms"] == 20


def test_summarize_groups_by_model_mode_card_type_and_status():
    metrics = [
        _metric(model="a", mode="ask", card_type="agent", status="completed"),
        _metric(model="a", mode="ask", card_type="swarm", status="failed"),
        _metric(model="b", mode="build", card_type="swarm", status="completed"),
    ]

    summary = summarize_chat_response_metrics(metrics)

    assert summary["by_model"] == {"a": 2, "b": 1}
    assert summary["by_mode"] == {"ask": 2, "build": 1}
    assert summary["by_card_type"] == {"agent": 1, "swarm": 2}
    assert summary["by_status"] == {"completed": 2, "failed": 1}


def test_summarize_latest_timestamps_and_does_not_mutate_input():
    metrics = [
        _metric(started_at="2026-05-30T10:00:00Z", finished_at="2026-05-30T10:00:01Z"),
        _metric(started_at="2026-05-30T10:01:00Z", finished_at="2026-05-30T10:01:01Z"),
    ]
    original = copy.deepcopy(metrics)

    summary = summarize_chat_response_metrics(metrics)

    assert summary["latest_started_at"] == "2026-05-30T10:01:00Z"
    assert summary["latest_finished_at"] == "2026-05-30T10:01:01Z"
    assert metrics == original
