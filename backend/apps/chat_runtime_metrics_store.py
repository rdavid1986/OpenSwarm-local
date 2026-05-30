"""Append-only local store for privacy-safe chat response metrics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.apps.chat_runtime_metrics import (
    ChatResponseMetric,
    dump_chat_response_metric,
    sanitize_chat_metric_metadata,
)
from backend.config.paths import DATA_ROOT

_REDACTED = "[redacted]"
_METADATA_REDACT_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "auth",
    "bearer",
    "body",
    "chain_of_thought",
    "content",
    "cookie",
    "credential",
    "credentials",
    "message",
    "messages",
    "password",
    "private_key",
    "prompt",
    "raw",
    "request",
    "response",
    "secret",
    "set_cookie",
    "set-cookie",
    "text",
    "token",
}
_METADATA_REDACT_MARKERS = (
    "api_key",
    "apikey",
    "authorization",
    "chain_of_thought",
    "credential",
    "password",
    "private_key",
    "secret",
    "token",
)
_FILTER_KEYS = ("card_type", "mode", "model", "status")


def get_default_chat_response_metrics_path() -> Path:
    """Return the default local JSONL path for persisted chat response metrics."""

    return Path(DATA_ROOT) / "metrics" / "chat_response_metrics.jsonl"


def _metric_path(path: str | Path | None) -> Path:
    return Path(path) if path is not None else get_default_chat_response_metrics_path()


def _is_sensitive_metadata_key(key: Any) -> bool:
    normalized = str(key or "").strip().lower().replace("-", "_")
    return normalized in _METADATA_REDACT_KEYS or any(marker in normalized for marker in _METADATA_REDACT_MARKERS)


def _redact_sensitive_metadata(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if _is_sensitive_metadata_key(key):
                redacted[str(key)] = _REDACTED
            else:
                redacted[str(key)] = _redact_sensitive_metadata(item)
        return redacted
    if isinstance(value, list):
        return [_redact_sensitive_metadata(item) for item in value]
    return value


def _prepare_metric_for_persistence(metric: ChatResponseMetric | dict[str, Any]) -> dict[str, Any]:
    dumped = dump_chat_response_metric(metric)
    dumped.pop("chain_of_thought", None)
    dumped["metadata"] = _redact_sensitive_metadata(
        sanitize_chat_metric_metadata(dumped.get("metadata") if isinstance(dumped.get("metadata"), dict) else {})
    )
    return dumped


def append_chat_response_metric(metric: ChatResponseMetric | dict[str, Any], path: str | Path | None = None) -> dict[str, Any]:
    """Append one privacy-safe chat response metric as JSONL and return the persisted dict."""

    target = _metric_path(path)
    persisted = _prepare_metric_for_persistence(metric)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8", newline="\n") as file:
        file.write(json.dumps(persisted, ensure_ascii=False, sort_keys=True) + "\n")
    return persisted


def _read_metrics(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    metrics: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as file:
        for line in file:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                metrics.append(parsed)
    return metrics


def _matches_filters(metric: dict[str, Any], filters: dict[str, Any]) -> bool:
    return all(value is None or metric.get(key) == value for key, value in filters.items())


def list_chat_response_metrics(
    path: str | Path | None = None,
    limit: int = 100,
    card_type: str | None = None,
    mode: str | None = None,
    model: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """List metrics newest first, ignoring corrupt JSONL lines and applying simple equality filters."""

    filters = {"card_type": card_type, "mode": mode, "model": model, "status": status}
    metrics = [metric for metric in _read_metrics(_metric_path(path)) if _matches_filters(metric, filters)]
    newest_first = list(reversed(metrics))
    if limit is None:  # type: ignore[unreachable]
        return newest_first
    safe_limit = max(0, int(limit))
    return newest_first[:safe_limit]


def _count_by(metrics: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for metric in metrics:
        group = str(metric.get(key) or "unknown")
        counts[group] = counts.get(group, 0) + 1
    return counts


def _numbers(metrics: list[dict[str, Any]], key: str) -> list[float]:
    values: list[float] = []
    for metric in metrics:
        value = metric.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            values.append(float(value))
    return values


def _average(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _latest(metrics: list[dict[str, Any]], key: str) -> str | None:
    values = [value for metric in metrics if isinstance((value := metric.get(key)), str) and value]
    return max(values) if values else None


def summarize_chat_response_metrics(metrics: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize chat response metrics without mutating the caller-provided list or dicts."""

    snapshot = [dict(metric) for metric in metrics]
    durations = _numbers(snapshot, "duration_ms")
    queues = _numbers(snapshot, "queue_ms")

    return {
        "count": len(snapshot),
        "completed_count": sum(1 for metric in snapshot if metric.get("status") == "completed"),
        "failed_count": sum(1 for metric in snapshot if metric.get("status") == "failed"),
        "error_count": sum(1 for metric in snapshot if bool(metric.get("error_type"))),
        "average_duration_ms": _average(durations),
        "max_duration_ms": max(durations) if durations else None,
        "min_duration_ms": min(durations) if durations else None,
        "average_queue_ms": _average(queues),
        "by_model": _count_by(snapshot, "model"),
        "by_mode": _count_by(snapshot, "mode"),
        "by_card_type": _count_by(snapshot, "card_type"),
        "by_status": _count_by(snapshot, "status"),
        "latest_started_at": _latest(snapshot, "started_at"),
        "latest_finished_at": _latest(snapshot, "finished_at"),
    }
