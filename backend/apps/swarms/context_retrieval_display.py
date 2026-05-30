
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any

SENSITIVE_KEYS = {"chain_of_thought", "cot", "private_reasoning", "hidden_reasoning"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items() if str(k) not in SENSITIVE_KEYS}
    if isinstance(value, list):
        return [_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_safe(v) for v in value]
    return value


def _list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return _safe(value)
    return [_safe(value)]


def _text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default

SOURCE_TYPES = {"memory", "session_summary", "file_context", "workspace_context", "evidence", "user_prompt", "system_state"}


def build_context_retrieval_display_item(**kwargs: Any) -> dict[str, Any]:
    source_type = _text(kwargs.get("source_type"), "memory")
    if source_type not in SOURCE_TYPES:
        source_type = "memory"
    return _safe({
        "display_kind": "context_retrieval_display_item",
        "retrieval_id": _text(kwargs.get("retrieval_id"), uuid4().hex),
        "source_type": source_type,
        "title": _text(kwargs.get("title"), "Retrieved context"),
        "summary": _text(kwargs.get("summary"), "No context summary provided."),
        "relevance_reason": _text(kwargs.get("relevance_reason"), "No relevance reason recorded."),
        "freshness": _text(kwargs.get("freshness"), "unknown"),
        "confidence": float(kwargs.get("confidence", 0.0) or 0.0),
        "used_by_agent_id": _text(kwargs.get("used_by_agent_id")),
        "used_by_task_id": _text(kwargs.get("used_by_task_id")),
        "evidence_ref": _text(kwargs.get("evidence_ref")),
        "visible_to_user": bool(kwargs.get("visible_to_user", True)),
        "sensitive": bool(kwargs.get("sensitive", False)),
        "redaction_applied": bool(kwargs.get("redaction_applied", False)),
    })


def summarize_context_retrieval_display(item: dict[str, Any]) -> dict[str, Any]:
    snapshot = deepcopy(_safe(item or {}))
    return {
        "summary_kind": "context_retrieval_display_summary",
        "retrieval_id": snapshot.get("retrieval_id", ""),
        "source_type": snapshot.get("source_type", "memory"),
        "title": snapshot.get("title", "Retrieved context"),
        "summary": snapshot.get("summary", "No context summary provided."),
        "confidence": snapshot.get("confidence", 0.0),
        "redaction_applied": bool(snapshot.get("redaction_applied", False)),
        "visible_to_user": bool(snapshot.get("visible_to_user", True)),
    }


def build_context_retrieval_panel(items: list[dict[str, Any]] | None = None, *, panel_title: str = "Mem / Context") -> dict[str, Any]:
    safe_items = [deepcopy(_safe(item)) for item in (items or [])]
    return {
        "panel_kind": "context_retrieval_panel",
        "title": panel_title,
        "item_count": len(safe_items),
        "items": safe_items,
        "source_types": [item.get("source_type") for item in safe_items],
        "visible_to_user": True,
    }
