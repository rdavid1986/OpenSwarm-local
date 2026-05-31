"""Side-effect-free workspace instruction bootstrap contracts.

This module builds a reviewable project instruction candidate from existing
workspace instruction sources. It does not write AGENTS.md, execute commands,
call models, authorize actions, or inject instructions without caller control.
"""

from __future__ import annotations

import hashlib
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.apps.swarms.agents_md import (
    apply_agents_md_guard,
    build_agents_md_context,
    build_agents_md_context_sections,
    discover_agents_md_files,
    parse_discovered_agents_md_files,
)
from backend.apps.swarms.process_trace_item import _safe


BOOTSTRAP_STATUSES = {
    "not_scanned",
    "scanned",
    "candidate_ready",
    "review_required",
    "approved",
    "blocked",
    "stale",
    "refresh_required",
}
DANGEROUS_BOOTSTRAP_KEYS = {
    "api_key",
    "authorization",
    "cookie",
    "credential",
    "credentials",
    "password",
    "private_key",
    "prompt",
    "raw_prompt",
    "raw_response",
    "refresh_token",
    "response",
    "secret",
    "session",
    "token",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _dedupe(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = _as_text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for key, item in list(value.items())[:80]:
            normalized = str(key or "").lower().replace("-", "_")
            if normalized in DANGEROUS_BOOTSTRAP_KEYS or any(token in normalized for token in ("token", "secret", "password", "credential", "authorization", "cookie", "api_key", "private_key")):
                output[str(key)] = "[redacted]"
            else:
                output[str(key)] = _redact(item)
        if len(value) > 80:
            output["__truncated__"] = f"+{len(value) - 80} more fields"
        return output
    if isinstance(value, list):
        visible = [_redact(item) for item in value[:80]]
        if len(value) > 80:
            visible.append(f"+{len(value) - 80} more")
        return visible
    if isinstance(value, str):
        return value[:2000].rstrip() + ("..." if len(value) > 2000 else "")
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:2000]


def normalize_project_instruction_status(value: Any) -> str:
    text = _as_text(value).lower()
    return text if text in BOOTSTRAP_STATUSES else "not_scanned"


def _hash_payload(value: Any) -> str:
    safe = repr(_redact(value)).encode("utf-8", errors="replace")
    return hashlib.sha256(safe).hexdigest()[:16]


def build_project_instruction_scan(
    repo_root: str | Path,
    *,
    target_path: str | None = None,
    forbidden_files: list[Any] | None = None,
    max_files: int = 8,
    max_chars: int = 12_000,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Scan workspace instruction sources without writing or authorizing actions."""

    root = Path(repo_root).resolve()
    discovery = discover_agents_md_files(root, max_results=max(max_files, 1))
    parsed = parse_discovered_agents_md_files(discovery, root) if discovery.get("ok") else {
        "repo_root": root.as_posix(),
        "parsed": [],
        "count": 0,
        "ok": False,
        "reason": discovery.get("reason") or "discovery_failed",
        "injection_ready": False,
    }
    context = build_agents_md_context(parsed, target_path=target_path or ".", max_files=max_files, max_chars=max_chars)
    guarded = apply_agents_md_guard(context, forbidden_files=forbidden_files)
    guard = _as_dict(guarded.get("guard"))

    status = "scanned" if discovery.get("ok") else "blocked"
    if guard.get("guard_status") == "blocked":
        status = "blocked"

    return _redact({
        "bootstrap_kind": "project_instruction_scan",
        "status": status,
        "repo_root": root.as_posix(),
        "target_path": target_path or ".",
        "discovery": discovery,
        "parsed_count": parsed.get("count") or 0,
        "selected_count": guarded.get("selected_count") or 0,
        "context_chars": guarded.get("context_chars") or 0,
        "guard": guard,
        "instruction_sources": [
            {
                "path": item.get("path"),
                "scope_path": item.get("scope_path"),
                "char_count": item.get("char_count"),
                "truncated_for_context": item.get("truncated_for_context") is True,
            }
            for item in guarded.get("selected") or []
            if isinstance(item, dict)
        ],
        "fingerprint": _hash_payload({
            "found": discovery.get("found"),
            "selected": guarded.get("selected"),
            "guard": guard,
        }),
        "created_at": utc_now_iso(),
        "metadata": _redact(metadata or {}),
    })


def build_workspace_rules_candidate(
    scan: dict[str, Any] | None,
    *,
    candidate_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a reviewable workspace instruction candidate from a scan."""

    scan_data = _as_dict(scan)
    guard = _as_dict(scan_data.get("guard"))
    sources = [item for item in scan_data.get("instruction_sources") or [] if isinstance(item, dict)]
    blocked = scan_data.get("status") == "blocked" or guard.get("guard_status") == "blocked"
    candidate_status = "blocked" if blocked else "candidate_ready" if sources else "review_required"
    source_paths = _dedupe([item.get("path") for item in sources])
    candidate = {
        "bootstrap_kind": "workspace_rules_candidate",
        "candidate_id": candidate_id or f"workspace-rules-{_hash_payload(scan_data)}",
        "status": candidate_status,
        "review_required": True,
        "approval_required": True,
        "can_inject": False,
        "can_write_file": False,
        "source_paths": source_paths,
        "source_count": len(source_paths),
        "scan_fingerprint": scan_data.get("fingerprint"),
        "guard_status": guard.get("guard_status") or "unknown",
        "risk_level": guard.get("risk_level") or "unknown",
        "rules_summary": "Workspace instruction candidate prepared for review." if sources else "No workspace instruction sources selected.",
        "diff": {
            "kind": "instruction_candidate_diff",
            "base": "existing_workspace_instructions",
            "candidate": "reviewable_workspace_rules_candidate",
            "changed": bool(sources),
            "source_paths": source_paths,
        },
        "required_actions": ["review_workspace_rules_candidate"],
        "warnings": ["candidate_blocked_by_guard"] if blocked else [],
        "created_at": utc_now_iso(),
        "metadata": _redact(metadata or {}),
    }
    return _redact(candidate)


def build_project_instruction_review(candidate: dict[str, Any] | None, *, approved: bool = False, reviewer: str | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    candidate_data = _as_dict(candidate)
    blocked = candidate_data.get("status") == "blocked"
    status = "blocked" if blocked else "approved" if approved else "review_required"
    return _redact({
        "bootstrap_kind": "project_instruction_review",
        "candidate_id": candidate_data.get("candidate_id"),
        "status": status,
        "approved": bool(approved and not blocked),
        "reviewer": reviewer or "human_required",
        "can_inject": bool(approved and not blocked),
        "can_write_file": False,
        "diff": candidate_data.get("diff") or {},
        "required_actions": [] if approved and not blocked else ["review_workspace_rules_candidate"],
        "warnings": ["candidate_blocked_by_guard"] if blocked else [],
        "metadata": _redact(metadata or {}),
    })


def build_project_instruction_context_sections(scan: dict[str, Any] | None, review: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Convert approved instruction scan into state_context-compatible sections."""

    scan_data = _as_dict(scan)
    review_data = _as_dict(review)
    if not review_data.get("approved"):
        return []
    context = {
        "selected": [
            {
                "path": item.get("path"),
                "scope_path": item.get("scope_path"),
                "content": f"Workspace instruction source: {item.get('path')}",
                "section_count": 0,
                "truncated_for_context": item.get("truncated_for_context") is True,
                "applies_to_target": True,
                "scope_depth": 0 if item.get("scope_path") in {"", "."} else len(Path(_as_text(item.get("scope_path"))).parts),
            }
            for item in scan_data.get("instruction_sources") or []
            if isinstance(item, dict)
        ],
    }
    sections = build_agents_md_context_sections(context)
    for section in sections:
        section["kind"] = "project_instructions"
        metadata = section.setdefault("metadata", {})
        metadata["bootstrap_kind"] = "project_instruction_context_section"
        metadata["approved"] = True
        metadata["scan_fingerprint"] = scan_data.get("fingerprint")
        metadata["candidate_id"] = review_data.get("candidate_id")
        metadata["injection_authorizes_actions"] = False
    return _redact(sections)


def build_project_instruction_refresh_state(previous_scan: dict[str, Any] | None, current_scan: dict[str, Any] | None, *, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    previous = _as_dict(previous_scan)
    current = _as_dict(current_scan)
    previous_fp = previous.get("fingerprint")
    current_fp = current.get("fingerprint")
    changed = bool(previous_fp and current_fp and previous_fp != current_fp)
    status = "refresh_required" if changed else "scanned" if current_fp else "not_scanned"
    return _redact({
        "bootstrap_kind": "project_instruction_refresh_state",
        "status": status,
        "previous_fingerprint": previous_fp,
        "current_fingerprint": current_fp,
        "changed": changed,
        "required_actions": ["review_workspace_rules_refresh"] if changed else [],
        "metadata": _redact(metadata or {}),
    })


def build_project_instruction_trace_source(
    *,
    scan: dict[str, Any] | None = None,
    candidate: dict[str, Any] | None = None,
    review: dict[str, Any] | None = None,
    refresh: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    scan_data = _as_dict(scan)
    candidate_data = _as_dict(candidate)
    review_data = _as_dict(review)
    refresh_data = _as_dict(refresh)
    status = (
        refresh_data.get("status")
        or review_data.get("status")
        or candidate_data.get("status")
        or scan_data.get("status")
        or "not_scanned"
    )
    return _redact({
        "source_kind": "project_instructions_bootstrap",
        "bootstrap_kind": "project_instructions_bootstrap",
        "status": status,
        "scan": scan_data or None,
        "candidate": candidate_data or None,
        "review": review_data or None,
        "refresh": refresh_data or None,
        "warnings": _dedupe(_as_list(candidate_data.get("warnings")) + _as_list(scan_data.get("warnings"))),
        "required_actions": _dedupe(_as_list(candidate_data.get("required_actions")) + _as_list(review_data.get("required_actions")) + _as_list(refresh_data.get("required_actions"))),
        "metadata": _redact(metadata or {}),
    })


def attach_project_instructions_to_metadata(metadata: dict[str, Any] | None, *, scan: dict[str, Any] | None = None, candidate: dict[str, Any] | None = None, review: dict[str, Any] | None = None) -> dict[str, Any]:
    clone = deepcopy(metadata) if isinstance(metadata, dict) else {}
    clone["project_instructions"] = _redact({
        "scan": scan,
        "candidate": candidate,
        "review": review,
    })
    return _redact(clone)
