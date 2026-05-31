"""Side-effect-free local diagnostics feedback contracts.

This module normalizes diagnostics from local tools/LSP-like sources into
redacted evidence, delta summaries and trace metadata. It does not execute
diagnostic tools, start LSP servers, read files, modify files, or claim that
validation passed without explicit diagnostic input.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any


SENSITIVE_KEYS = {
    "api_key",
    "authorization",
    "chain_of_thought",
    "cookie",
    "credential",
    "credentials",
    "hidden_reasoning",
    "password",
    "private_key",
    "prompt",
    "raw_prompt",
    "raw_response",
    "response",
    "secret",
    "session",
    "token",
}
SEVERITIES = {"error", "warning", "information", "hint", "unknown"}
SNAPSHOT_STATUSES = {"clean", "has_errors", "has_warnings", "unknown", "blocked", "empty"}
DECISION_STATUSES = {"passed", "failed", "needs_review", "unmeasured"}


@dataclass
class DiagnosticRecord:
    record_kind: str = "lsp_diagnostic_record"
    diagnostic_id: str = ""
    file_path: str = ""
    start_line: int | None = None
    start_column: int | None = None
    end_line: int | None = None
    end_column: int | None = None
    severity: str = "unknown"
    source: str = "unknown"
    code: str = ""
    message: str = ""
    message_hash: str = ""
    related_information: list[dict[str, Any]] = field(default_factory=list)
    evidence_ref: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DiagnosticSnapshot:
    snapshot_kind: str = "lsp_diagnostic_snapshot"
    snapshot_id: str = ""
    status: str = "unknown"
    workspace_root: str = ""
    source: str = "unknown"
    created_at: str = ""
    diagnostics: list[dict[str, Any]] = field(default_factory=list)
    error_count: int = 0
    warning_count: int = 0
    information_count: int = 0
    hint_count: int = 0
    unknown_count: int = 0
    affected_files: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    can_execute_diagnostics: bool = False
    can_modify_files: bool = False
    can_activate_tools: bool = False
    can_activate_mcp: bool = False


@dataclass
class DiagnosticEvidenceBundle:
    bundle_kind: str = "lsp_diagnostic_evidence_bundle"
    status: str = "unmeasured"
    snapshot_id: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    affected_files: list[str] = field(default_factory=list)
    summary: str = ""
    validation_status: str = "unmeasured"
    failure_reasons: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    can_execute_diagnostics: bool = False
    can_modify_files: bool = False
    can_activate_tools: bool = False
    can_activate_mcp: bool = False


@dataclass
class DiagnosticDelta:
    delta_kind: str = "lsp_diagnostic_delta"
    status: str = "unknown"
    previous_snapshot_id: str = ""
    current_snapshot_id: str = ""
    added_count: int = 0
    resolved_count: int = 0
    unchanged_count: int = 0
    added_diagnostics: list[dict[str, Any]] = field(default_factory=list)
    resolved_diagnostics: list[dict[str, Any]] = field(default_factory=list)
    unchanged_diagnostics: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DiagnosticFeedbackDecision:
    decision_kind: str = "lsp_diagnostic_feedback_decision"
    status: str = "unmeasured"
    reason: str = ""
    snapshot_id: str = ""
    error_count: int = 0
    warning_count: int = 0
    should_block_acceptance: bool = False
    should_request_review: bool = True
    evidence_refs: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    can_execute_diagnostics: bool = False
    can_modify_files: bool = False
    can_activate_tools: bool = False
    can_activate_mcp: bool = False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _text(value: Any, fallback: str = "") -> str:
    text = str(value or "").strip()
    return text or fallback


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return deepcopy(value)
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "model_dump"):
        try:
            return value.model_dump(mode="json")
        except TypeError:
            return value.model_dump()
    return {}


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _safe(value: Any) -> Any:
    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for key, item in list(value.items())[:120]:
            normalized = str(key or "").lower().replace("-", "_")
            if normalized in SENSITIVE_KEYS or any(token in normalized for token in ("secret", "token", "password", "credential", "authorization", "cookie", "api_key", "private_key", "prompt", "response", "chain_of_thought")):
                continue
            output[str(key)] = _safe(item)
        if len(value) > 120:
            output["__truncated__"] = f"+{len(value) - 120} more fields"
        return output
    if isinstance(value, list):
        visible = [_safe(item) for item in value[:120]]
        if len(value) > 120:
            visible.append(f"+{len(value) - 120} more")
        return visible
    if isinstance(value, tuple):
        return [_safe(item) for item in value]
    if isinstance(value, str):
        return value[:1200].rstrip() + ("..." if len(value) > 1200 else "")
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:1200]


def _dedupe(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        text = _text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        output.append(text)
    return output


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return max(0, parsed)


def normalize_diagnostic_severity(value: Any) -> str:
    text = _text(value).lower()
    if text in {"1", "err", "error", "fatal"}:
        return "error"
    if text in {"2", "warn", "warning"}:
        return "warning"
    if text in {"3", "info", "information"}:
        return "information"
    if text in {"4", "hint"}:
        return "hint"
    return text if text in SEVERITIES else "unknown"


def _message_hash(message: str) -> str:
    return sha256(message.encode("utf-8", errors="replace")).hexdigest()[:16]


def _diagnostic_id(payload: dict[str, Any], message_hash: str) -> str:
    seed = "|".join([
        _text(payload.get("file_path") or payload.get("file") or payload.get("path")),
        _text(payload.get("source")),
        _text(payload.get("code")),
        _text(payload.get("line") or payload.get("start_line")),
        message_hash,
    ])
    return f"diag-{sha256(seed.encode('utf-8', errors='replace')).hexdigest()[:16]}"


def normalize_diagnostic_record(value: Any, *, workspace_root: str = "", source: str = "unknown") -> DiagnosticRecord:
    data = _as_dict(value)
    severity = normalize_diagnostic_severity(data.get("severity") or data.get("level"))
    message = _text(data.get("message") or data.get("text") or data.get("detail"))
    msg_hash = _message_hash(message)
    file_path = _text(data.get("file_path") or data.get("file") or data.get("path"))
    start_line = _int_or_none(data.get("start_line") if data.get("start_line") is not None else data.get("line"))
    start_column = _int_or_none(data.get("start_column") if data.get("start_column") is not None else data.get("column"))
    end_line = _int_or_none(data.get("end_line"))
    end_column = _int_or_none(data.get("end_column"))
    resolved_source = _text(data.get("source") or source, "unknown")
    evidence_ref = _text(data.get("evidence_ref") or data.get("evidence_id"))
    if not evidence_ref:
        evidence_ref = f"diagnostic:{_diagnostic_id(data, msg_hash)}"
    return DiagnosticRecord(
        diagnostic_id=_text(data.get("diagnostic_id") or data.get("id"), _diagnostic_id(data, msg_hash)),
        file_path=file_path,
        start_line=start_line,
        start_column=start_column,
        end_line=end_line,
        end_column=end_column,
        severity=severity,
        source=resolved_source,
        code=_text(data.get("code")),
        message=message,
        message_hash=msg_hash,
        related_information=_safe(_as_list(data.get("related_information"))),
        evidence_ref=evidence_ref,
        metadata=_safe({
            "workspace_root": workspace_root,
            "original_source": data.get("source"),
            "raw_kind": data.get("kind") or data.get("type"),
        }),
    )


def dump_diagnostic_record(record: DiagnosticRecord | dict[str, Any]) -> dict[str, Any]:
    return _safe(record)


def build_diagnostic_snapshot(
    diagnostics: list[Any] | None,
    *,
    workspace_root: str = "",
    source: str = "unknown",
    created_at: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> DiagnosticSnapshot:
    records = [dump_diagnostic_record(normalize_diagnostic_record(item, workspace_root=workspace_root, source=source)) for item in diagnostics or []]
    error_count = sum(1 for item in records if item.get("severity") == "error")
    warning_count = sum(1 for item in records if item.get("severity") == "warning")
    information_count = sum(1 for item in records if item.get("severity") == "information")
    hint_count = sum(1 for item in records if item.get("severity") == "hint")
    unknown_count = sum(1 for item in records if item.get("severity") == "unknown")
    affected_files = _dedupe([item.get("file_path") for item in records])
    evidence_refs = _dedupe([item.get("evidence_ref") for item in records])
    if not records:
        status = "empty"
    elif error_count:
        status = "has_errors"
    elif warning_count:
        status = "has_warnings"
    else:
        status = "clean"
    snapshot_time = created_at or _now()
    fingerprint = sha256(repr(records).encode("utf-8", errors="replace")).hexdigest()[:16]
    return DiagnosticSnapshot(
        snapshot_id=f"diagnostic-snapshot-{fingerprint}",
        status=status,
        workspace_root=_text(workspace_root),
        source=_text(source, "unknown"),
        created_at=snapshot_time,
        diagnostics=records,
        error_count=error_count,
        warning_count=warning_count,
        information_count=information_count,
        hint_count=hint_count,
        unknown_count=unknown_count,
        affected_files=affected_files,
        evidence_refs=evidence_refs,
        warnings=[] if records else ["diagnostics_empty"],
        required_actions=["run_diagnostics_or_attach_snapshot"] if not records else [],
        metadata=_safe(metadata or {}),
    )


def dump_diagnostic_snapshot(snapshot: DiagnosticSnapshot | dict[str, Any]) -> dict[str, Any]:
    return _safe(snapshot)


def build_diagnostic_evidence_bundle(snapshot: DiagnosticSnapshot | dict[str, Any], *, metadata: dict[str, Any] | None = None) -> DiagnosticEvidenceBundle:
    data = dump_diagnostic_snapshot(snapshot)
    error_count = int(data.get("error_count") or 0)
    warning_count = int(data.get("warning_count") or 0)
    if data.get("status") == "empty":
        status = "unmeasured"
        validation_status = "unmeasured"
    elif error_count:
        status = "failed"
        validation_status = "failed"
    elif warning_count:
        status = "needs_review"
        validation_status = "needs_review"
    else:
        status = "passed"
        validation_status = "passed"
    failure_reasons = []
    if error_count:
        failure_reasons.append({"code": "diagnostic_errors_present", "count": error_count, "severity": "high"})
    if warning_count and not error_count:
        failure_reasons.append({"code": "diagnostic_warnings_present", "count": warning_count, "severity": "medium"})
    return DiagnosticEvidenceBundle(
        status=status,
        snapshot_id=_text(data.get("snapshot_id")),
        evidence_refs=list(data.get("evidence_refs") or []),
        affected_files=list(data.get("affected_files") or []),
        summary=f"Diagnostics status={data.get('status')}; errors={error_count}; warnings={warning_count}; files={len(data.get('affected_files') or [])}.",
        validation_status=validation_status,
        failure_reasons=failure_reasons,
        warnings=list(data.get("warnings") or []),
        required_actions=list(data.get("required_actions") or []),
        metadata=_safe(metadata or {}),
    )


def dump_diagnostic_evidence_bundle(bundle: DiagnosticEvidenceBundle | dict[str, Any]) -> dict[str, Any]:
    return _safe(bundle)


def _diagnostic_key(item: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        _text(item.get("file_path")),
        _text(item.get("source")),
        _text(item.get("code")),
        _text(item.get("message_hash")),
    )


def build_diagnostic_delta(
    previous_snapshot: DiagnosticSnapshot | dict[str, Any] | None,
    current_snapshot: DiagnosticSnapshot | dict[str, Any] | None,
    *,
    metadata: dict[str, Any] | None = None,
) -> DiagnosticDelta:
    previous = dump_diagnostic_snapshot(previous_snapshot or {})
    current = dump_diagnostic_snapshot(current_snapshot or {})
    prev_items = [item for item in previous.get("diagnostics") or [] if isinstance(item, dict)]
    curr_items = [item for item in current.get("diagnostics") or [] if isinstance(item, dict)]
    prev_by_key = {_diagnostic_key(item): item for item in prev_items}
    curr_by_key = {_diagnostic_key(item): item for item in curr_items}

    added = [item for key, item in curr_by_key.items() if key not in prev_by_key]
    resolved = [item for key, item in prev_by_key.items() if key not in curr_by_key]
    unchanged = [item for key, item in curr_by_key.items() if key in prev_by_key]
    if added and not resolved:
        status = "regressed"
    elif resolved and not added:
        status = "improved"
    elif not added and not resolved:
        status = "unchanged"
    else:
        status = "mixed"
    return DiagnosticDelta(
        status=status,
        previous_snapshot_id=_text(previous.get("snapshot_id")),
        current_snapshot_id=_text(current.get("snapshot_id")),
        added_count=len(added),
        resolved_count=len(resolved),
        unchanged_count=len(unchanged),
        added_diagnostics=_safe(added),
        resolved_diagnostics=_safe(resolved),
        unchanged_diagnostics=_safe(unchanged),
        warnings=[],
        required_actions=["review_added_diagnostics"] if added else [],
        metadata=_safe(metadata or {}),
    )


def dump_diagnostic_delta(delta: DiagnosticDelta | dict[str, Any]) -> dict[str, Any]:
    return _safe(delta)


def build_diagnostic_feedback_decision(
    snapshot: DiagnosticSnapshot | dict[str, Any],
    evidence_bundle: DiagnosticEvidenceBundle | dict[str, Any] | None = None,
    *,
    metadata: dict[str, Any] | None = None,
) -> DiagnosticFeedbackDecision:
    snap = dump_diagnostic_snapshot(snapshot)
    bundle = dump_diagnostic_evidence_bundle(evidence_bundle or build_diagnostic_evidence_bundle(snap))
    error_count = int(snap.get("error_count") or 0)
    warning_count = int(snap.get("warning_count") or 0)
    if snap.get("status") == "empty":
        status = "unmeasured"
        reason = "No diagnostics were provided; validation is unmeasured."
    elif error_count:
        status = "failed"
        reason = "Diagnostic errors are present."
    elif warning_count:
        status = "needs_review"
        reason = "Diagnostic warnings are present."
    else:
        status = "passed"
        reason = "No diagnostic errors or warnings were reported."
    return DiagnosticFeedbackDecision(
        status=status,
        reason=reason,
        snapshot_id=_text(snap.get("snapshot_id")),
        error_count=error_count,
        warning_count=warning_count,
        should_block_acceptance=status == "failed",
        should_request_review=status in {"failed", "needs_review", "unmeasured"},
        evidence_refs=list(bundle.get("evidence_refs") or []),
        required_actions=list(bundle.get("required_actions") or ([] if status == "passed" else ["review_diagnostic_feedback"])),
        warnings=list(bundle.get("warnings") or []),
        metadata=_safe(metadata or {}),
    )


def dump_diagnostic_feedback_decision(decision: DiagnosticFeedbackDecision | dict[str, Any]) -> dict[str, Any]:
    return _safe(decision)


def build_lsp_diagnostic_trace_source(
    *,
    snapshot: DiagnosticSnapshot | dict[str, Any] | None = None,
    evidence_bundle: DiagnosticEvidenceBundle | dict[str, Any] | None = None,
    delta: DiagnosticDelta | dict[str, Any] | None = None,
    decision: DiagnosticFeedbackDecision | dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    snap = dump_diagnostic_snapshot(snapshot or {})
    bundle = dump_diagnostic_evidence_bundle(evidence_bundle or {}) if evidence_bundle else {}
    delta_data = dump_diagnostic_delta(delta or {}) if delta else {}
    decision_data = dump_diagnostic_feedback_decision(decision or build_diagnostic_feedback_decision(snap)) if snap else {}
    warnings = _dedupe(_as_list(snap.get("warnings")) + _as_list(bundle.get("warnings")) + _as_list(delta_data.get("warnings")) + _as_list(decision_data.get("warnings")))
    required = _dedupe(_as_list(snap.get("required_actions")) + _as_list(bundle.get("required_actions")) + _as_list(delta_data.get("required_actions")) + _as_list(decision_data.get("required_actions")))
    return _safe({
        "source_kind": "lsp_diagnostic_feedback",
        "diagnostic_kind": "lsp_diagnostic_feedback",
        "status": decision_data.get("status") or bundle.get("status") or snap.get("status") or "unmeasured",
        "snapshot": snap or None,
        "evidence_bundle": bundle or None,
        "delta": delta_data or None,
        "decision": decision_data or None,
        "warnings": warnings,
        "required_actions": required,
        "can_execute_diagnostics": False,
        "can_modify_files": False,
        "can_activate_tools": False,
        "can_activate_mcp": False,
        "metadata": _safe(metadata or {}),
    })


def attach_lsp_diagnostics_to_metadata(
    metadata: dict[str, Any] | None,
    *,
    snapshot: DiagnosticSnapshot | dict[str, Any] | None = None,
    evidence_bundle: DiagnosticEvidenceBundle | dict[str, Any] | None = None,
    decision: DiagnosticFeedbackDecision | dict[str, Any] | None = None,
) -> dict[str, Any]:
    clone = deepcopy(metadata) if isinstance(metadata, dict) else {}
    clone["lsp_diagnostic_feedback"] = _safe({
        "snapshot": dump_diagnostic_snapshot(snapshot or {}),
        "evidence_bundle": dump_diagnostic_evidence_bundle(evidence_bundle or {}) if evidence_bundle else {},
        "decision": dump_diagnostic_feedback_decision(decision or {}) if decision else {},
    })
    return _safe(clone)
