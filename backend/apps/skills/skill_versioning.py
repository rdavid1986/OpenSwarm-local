"""Safe skill version snapshots and rollback plans."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

SAFE_FLAGS = {
    "can_install_skill": False,
    "can_execute_source": False,
    "can_activate_tools": False,
    "can_activate_mcp": False,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return deepcopy(value)
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return {}


def _text(value: Any, fallback: str = "") -> str:
    text = str(value or "").strip()
    return text or fallback


def _hash(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()


def _candidate_and_spec(candidate_or_skill: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    data = _as_dict(candidate_or_skill)
    spec = data.get("skill_spec") if isinstance(data.get("skill_spec"), dict) else data
    return data, _as_dict(spec)


def _skill_ref(data: dict[str, Any], spec: dict[str, Any]) -> str:
    return _text(data.get("candidate_id") or data.get("id") or spec.get("id") or spec.get("command") or spec.get("name"), "unknown")


def build_skill_version_snapshot(candidate_or_skill: dict[str, Any], *, source: str = "candidate", reason: str = "") -> dict[str, Any]:
    data, spec = _candidate_and_spec(candidate_or_skill)
    skill_ref = _skill_ref(data, spec)
    content = _text(spec.get("content") or data.get("content"))
    metadata = {
        "name": spec.get("name") or data.get("name"),
        "description": spec.get("description") or data.get("description"),
        "command": spec.get("command") or data.get("command"),
        "source_format": spec.get("source_format"),
        "required_tools": spec.get("required_tools") or [],
        "required_mcp_servers": spec.get("required_mcp_servers") or [],
        "risks": spec.get("risks") or [],
    }
    content_hash = _hash(content)
    spec_hash = _hash(spec)
    metadata_hash = _hash(metadata)
    snapshot_id = f"skill-snapshot-{skill_ref}-{spec_hash[:12]}".replace(" ", "-")
    harness = data.get("harness_summary") if isinstance(data.get("harness_summary"), dict) else data.get("harness") if isinstance(data.get("harness"), dict) else {}
    install_audit = data.get("install_audit") if isinstance(data.get("install_audit"), dict) else {}
    return {
        "snapshot_kind": "skill_version_snapshot",
        "snapshot_id": snapshot_id,
        "skill_ref": skill_ref,
        "skill_name": _text(spec.get("name") or data.get("name"), "unknown"),
        "source": source if source in {"candidate", "installed_skill", "imported_skill", "unknown"} else "unknown",
        "created_at": _now(),
        "reason": _text(reason, "not_recorded"),
        "content_hash": content_hash,
        "spec_hash": spec_hash,
        "metadata_hash": metadata_hash,
        "provenance": _as_dict(spec.get("provenance")),
        "compatibility_summary": _as_dict(spec.get("compatibility")),
        "harness_summary": {
            "validation_status": harness.get("validation_status") or harness.get("runtime_validation", {}).get("status") if isinstance(harness.get("runtime_validation"), dict) else harness.get("validation_status"),
            "promotion_decision": harness.get("promotion_decision") or harness.get("promotion_gate", {}).get("decision") if isinstance(harness.get("promotion_gate"), dict) else harness.get("promotion_decision"),
        } if harness else {},
        "install_audit_summary": {key: install_audit.get(key) for key in ("event", "skill_id", "candidate_id", "installed_at") if install_audit.get(key)} if install_audit else {},
        "rollback_supported": bool(content_hash and spec_hash),
        "can_restore": bool(content_hash and spec_hash),
        **SAFE_FLAGS,
    }


def build_skill_rollback_plan(current_snapshot: dict[str, Any], target_snapshot: dict[str, Any]) -> dict[str, Any]:
    current = _as_dict(current_snapshot)
    target = _as_dict(target_snapshot)
    changed_fields = []
    for key in ("content_hash", "spec_hash", "metadata_hash"):
        if current.get(key) != target.get(key):
            changed_fields.append(key.replace("_hash", ""))
    blocked = not current or not target or current.get("skill_ref") != target.get("skill_ref")
    decision = "blocked" if blocked else "restore_ready" if changed_fields else "needs_review"
    required_actions = []
    if blocked:
        required_actions.append({"code": "matching_snapshots_required", "message": "Current and target snapshots must exist for the same skill_ref."})
    required_actions.append({"code": "explicit_restore_approval_required", "message": "Rollback restore requires explicit approval and is not performed by this plan."})
    return {
        "plan_kind": "skill_rollback_plan",
        "decision": decision,
        "current_snapshot_id": current.get("snapshot_id") or "not_available",
        "target_snapshot_id": target.get("snapshot_id") or "not_available",
        "changed_fields": changed_fields,
        "diff_summary": "No content is included; compare hashes/metadata only." if changed_fields else "No changed hash fields detected.",
        "required_actions": required_actions,
        "can_restore": decision == "restore_ready",
        "restore_requires_explicit_approval": True,
        "restore_performed": False,
        **SAFE_FLAGS,
    }


def build_skill_version_history_summary(snapshots: list[dict]) -> dict[str, Any]:
    safe = [_as_dict(item) for item in snapshots if isinstance(item, dict)]
    latest = safe[-1] if safe else {}
    return {
        "summary_kind": "skill_version_history_summary",
        "snapshot_count": len(safe),
        "skill_ref": latest.get("skill_ref") or (safe[0].get("skill_ref") if safe else "unknown"),
        "latest_snapshot_id": latest.get("snapshot_id") or "not_available",
        "latest_created_at": latest.get("created_at") or "not_available",
        "latest_content_hash": latest.get("content_hash") or "not_available",
        "rollback_supported_count": sum(1 for item in safe if item.get("rollback_supported")),
        **SAFE_FLAGS,
    }
