from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any


E2E_VERSION = "1.0"


def _safe(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _contract_dict(value: Any) -> dict[str, Any]:
    safe = _safe(value)
    return safe if isinstance(safe, dict) else {}


def _text(value: Any, default: str = "", *, limit: int = 1000) -> str:
    if value is None:
        return default
    text = str(value).strip()
    return (text or default)[:limit]


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _dedupe_text(values: list[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _text(value, limit=500)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


@dataclass(frozen=True)
class SddTddMaterializationE2EGate:
    source_kind: str = "sdd_tdd_materialization_e2e"
    e2e_kind: str = "sdd_tdd_materialization_e2e_gate"
    e2e_version: str = E2E_VERSION
    candidate_id: str = ""
    gate_status: str = "blocked"
    sdd_status: str = "missing"
    tdd_status: str = "missing"
    materialization_status: str = "missing"
    completion_conditions: dict[str, bool] = field(default_factory=dict)
    evidence_refs: list[str] = field(default_factory=list)
    process_trace_refs: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    required_actions: list[str] = field(default_factory=list)
    can_mark_change_completed: bool = False
    can_execute: bool = False
    can_write_files: bool = False
    can_apply_patch: bool = False
    can_execute_commands: bool = False
    can_activate_tools: bool = False
    can_activate_mcp: bool = False
    can_write_memory: bool = False
    contains_private_reasoning: bool = False


@dataclass(frozen=True)
class SddTddMaterializationE2ESummary:
    source_kind: str = "sdd_tdd_materialization_e2e"
    e2e_kind: str = "sdd_tdd_materialization_e2e_summary"
    e2e_version: str = E2E_VERSION
    candidate_id: str = ""
    summary_status: str = "blocked"
    gate: dict[str, Any] = field(default_factory=dict)
    sdd_gate: dict[str, Any] = field(default_factory=dict)
    tdd_gate: dict[str, Any] = field(default_factory=dict)
    materialization_gate: dict[str, Any] = field(default_factory=dict)
    required_actions: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    can_mark_change_completed: bool = False
    contains_private_reasoning: bool = False


def dump_sdd_tdd_materialization_e2e_contract(value: Any) -> dict[str, Any]:
    dumped = _safe(value)
    return dumped if isinstance(dumped, dict) else {}


def build_sdd_tdd_materialization_e2e_gate(
    *,
    candidate_id: Any = "",
    sdd_completion_gate: Any = None,
    tdd_runtime_gate: Any = None,
    materialization_gate: Any = None,
    require_tdd: bool = True,
    require_materialization: bool = True,
    process_trace_refs: list[Any] | None = None,
) -> SddTddMaterializationE2EGate:
    sdd = _contract_dict(sdd_completion_gate)
    tdd = _contract_dict(tdd_runtime_gate)
    materialization = _contract_dict(materialization_gate)

    sdd_ok = bool(
        sdd.get("can_mark_completed") is True
        and _text(sdd.get("gate_status"), "").lower() == "completed"
        and not _as_list(sdd.get("blockers"))
    )
    tdd_ok = bool(
        not require_tdd
        or (
            tdd.get("can_complete_tdd_cycle") is True
            and _text(tdd.get("gate_status"), "").lower() == "completed"
            and not _as_list(tdd.get("blockers"))
        )
    )
    materialization_ok = bool(
        not require_materialization
        or (
            materialization.get("can_mark_materialization_safe") is True
            and _text(materialization.get("gate_status"), "").lower() == "completed"
            and not _as_list(materialization.get("blockers"))
        )
    )

    conditions = {
        "sdd_completion_ok": sdd_ok,
        "tdd_runtime_ok": tdd_ok,
        "materialization_safe_ok": materialization_ok,
        "tdd_required": require_tdd,
        "materialization_required": require_materialization,
    }

    blockers: list[str] = []
    required: list[str] = ["review_sdd_tdd_materialization_e2e_gate"]

    if not sdd_ok:
        blockers.append("sdd_completion_gate_not_confirmed")
        required.append("attach_completed_sdd_completion_gate")
    if require_tdd and not tdd_ok:
        blockers.append("tdd_runtime_gate_not_confirmed")
        required.append("attach_completed_tdd_runtime_gate")
    if require_materialization and not materialization_ok:
        blockers.append("materialization_safe_gate_not_confirmed")
        required.append("attach_completed_action_materialization_post_validation_gate")

    evidence_refs: list[str] = []
    evidence_refs.extend(_as_list(sdd.get("evidence_refs")))
    evidence_refs.extend(_as_list(tdd.get("evidence_refs")))
    evidence_refs.extend(_as_list(materialization.get("evidence_refs")))

    traces = _dedupe_text(_as_list(process_trace_refs))
    completed = all(conditions[key] for key in ["sdd_completion_ok", "tdd_runtime_ok", "materialization_safe_ok"]) and not blockers

    return SddTddMaterializationE2EGate(
        candidate_id=_text(candidate_id or sdd.get("candidate_id") or tdd.get("candidate_id") or materialization.get("candidate_id"), limit=240),
        gate_status="completed" if completed else "blocked",
        sdd_status=_text(sdd.get("gate_status"), "missing", limit=120),
        tdd_status=_text(tdd.get("gate_status"), "missing", limit=120),
        materialization_status=_text(materialization.get("gate_status"), "missing", limit=120),
        completion_conditions=conditions,
        evidence_refs=_dedupe_text(evidence_refs),
        process_trace_refs=traces,
        blockers=_dedupe_text(blockers),
        required_actions=_dedupe_text(required),
        can_mark_change_completed=completed,
    )


def build_sdd_tdd_materialization_e2e_summary(
    *,
    gate: Any,
    sdd_completion_gate: Any = None,
    tdd_runtime_gate: Any = None,
    materialization_gate: Any = None,
) -> SddTddMaterializationE2ESummary:
    gate_data = _contract_dict(gate)
    sdd = _contract_dict(sdd_completion_gate)
    tdd = _contract_dict(tdd_runtime_gate)
    materialization = _contract_dict(materialization_gate)

    completed = bool(gate_data.get("can_mark_change_completed") is True and gate_data.get("gate_status") == "completed")

    return SddTddMaterializationE2ESummary(
        candidate_id=_text(gate_data.get("candidate_id") or sdd.get("candidate_id") or materialization.get("candidate_id"), limit=240),
        summary_status="completed" if completed else "blocked",
        gate=gate_data,
        sdd_gate=sdd,
        tdd_gate=tdd,
        materialization_gate=materialization,
        required_actions=_dedupe_text(_as_list(gate_data.get("required_actions"))),
        blockers=_dedupe_text(_as_list(gate_data.get("blockers"))),
        can_mark_change_completed=completed,
    )
