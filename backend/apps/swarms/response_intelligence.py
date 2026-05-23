"""Response Intelligence helpers for Swarm chat.

This module is intentionally state-only for RI-1.A.
It summarizes Swarm state into a small semantic snapshot without executing tools,
calling providers, mutating files, or changing routing behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RIStateSnapshot:
    swarm_id: str
    swarm_intent: str
    swarm_status: str
    current_route: str | None = None
    project_intake_status: str | None = None
    pending_action: str | None = None
    target_output_id: str | None = None
    source_swarm_id: str | None = None
    implementation_status: str | None = None
    claim_guard_status: str | None = None
    artifact_count: int = 0
    evidence_count: int = 0
    final_evidence_count: int = 0
    approval_count: int = 0
    available_actions: list[str] = field(default_factory=list)
    reason: str = ""


@dataclass(frozen=True)
class RIResult:
    route: str
    source: str
    response_source: str
    requires_provider: bool
    assistant_content: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    context: str = ""
    answer_guard_applied: bool = False
    answer_guard_reason: str | None = None
    state: RIStateSnapshot | None = None


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _first_non_empty(*values: Any) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def build_ri_state_snapshot(
    swarm: Any,
    *,
    route: str | None = None,
    user_message: str | None = None,
    payload: dict[str, Any] | None = None,
) -> RIStateSnapshot:
    payload = _as_dict(payload)
    final_result = dict(_as_dict(getattr(swarm, "final_result", None)))
    if "refinement_request" in payload:
        final_result["refinement_request"] = payload["refinement_request"]
    if "project_intake_state" in payload:
        final_result["project_intake_state"] = payload["project_intake_state"]

    project_intake_state = dict(_as_dict(getattr(swarm, "project_intake_state", None)))
    if "project_intake_state" in payload:
        project_intake_state = _as_dict(payload["project_intake_state"])

    refinement_request = _as_dict(final_result.get("refinement_request"))

    claim_guard = _as_dict(final_result.get("claim_guard"))
    validation_result = _as_dict(final_result.get("validation_result"))

    target_output_id = _first_non_empty(
        refinement_request.get("output_id"),
        final_result.get("output_id"),
    )
    source_swarm_id = _first_non_empty(
        refinement_request.get("source_swarm_id"),
        final_result.get("source_swarm_id"),
        getattr(swarm, "id", None),
    )

    pending_action = classify_pending_action(
        swarm,
        route=route,
        final_result=final_result,
        project_intake_state=project_intake_state,
        refinement_request=refinement_request,
    )

    available_actions = build_available_actions(
        route=route,
        final_result=final_result,
        project_intake_state=project_intake_state,
        refinement_request=refinement_request,
        pending_action=pending_action,
    )

    reason_parts: list[str] = []
    if pending_action:
        reason_parts.append(f"pending_action={pending_action}")
    if target_output_id:
        reason_parts.append(f"target_output_id={target_output_id}")
    if project_intake_state.get("status"):
        reason_parts.append(f"project_intake_status={project_intake_state.get('status')}")
    if route:
        reason_parts.append(f"route={route}")

    return RIStateSnapshot(
        swarm_id=str(getattr(swarm, "id", "") or ""),
        swarm_intent=str(getattr(swarm, "intent", "") or ""),
        swarm_status=str(getattr(swarm, "status", "") or ""),
        current_route=route,
        project_intake_status=_first_non_empty(project_intake_state.get("status")),
        pending_action=pending_action,
        target_output_id=target_output_id,
        source_swarm_id=source_swarm_id,
        implementation_status=_first_non_empty(final_result.get("implementation_status"), final_result.get("status")),
        claim_guard_status=_first_non_empty(claim_guard.get("status")),
        artifact_count=len(getattr(swarm, "artifacts", []) or []),
        evidence_count=len(getattr(swarm, "evidence", []) or []),
        final_evidence_count=len(getattr(swarm, "final_evidence", []) or []),
        approval_count=len(getattr(swarm, "experimental_approvals", []) or []),
        available_actions=available_actions,
        reason="; ".join(reason_parts),
    )


def classify_pending_action(
    swarm: Any,
    *,
    route: str | None,
    final_result: dict[str, Any],
    project_intake_state: dict[str, Any],
    refinement_request: dict[str, Any],
) -> str | None:
    if refinement_request.get("output_id"):
        status = str(refinement_request.get("status") or "received")
        if status == "confirmed":
            return "run_refinement_pipeline"
        return "confirm_refinement"

    if project_intake_state.get("status") == "collecting":
        return "answer_project_intake"

    if project_intake_state.get("status") == "ready_to_implement":
        return "start_implementation"

    if (
        final_result.get("artifact_kind") == "static_app"
        and final_result.get("implementation_performed") is True
        and not final_result.get("output_id")
    ):
        return "create_output_bridge"

    if route == "implementation_request":
        return "start_project_intake"

    return None


def build_available_actions(
    *,
    route: str | None,
    final_result: dict[str, Any],
    project_intake_state: dict[str, Any],
    refinement_request: dict[str, Any],
    pending_action: str | None,
) -> list[str]:
    actions: list[str] = []

    if pending_action:
        actions.append(pending_action)

    if refinement_request.get("output_id"):
        actions.extend(["open_preview", "edit_refinement_request"])
        return list(dict.fromkeys(actions))

    if project_intake_state.get("status") == "ready_to_implement":
        actions.append("start_implementation")

    if (
        final_result.get("artifact_kind") == "static_app"
        and final_result.get("implementation_performed") is True
    ):
        actions.append("open_or_create_preview")

    return list(dict.fromkeys(actions))


def snapshot_payload(snapshot: RIStateSnapshot) -> dict[str, Any]:
    return {
        "ri_state": {
            "swarm_id": snapshot.swarm_id,
            "swarm_intent": snapshot.swarm_intent,
            "swarm_status": snapshot.swarm_status,
            "current_route": snapshot.current_route,
            "project_intake_status": snapshot.project_intake_status,
            "pending_action": snapshot.pending_action,
            "target_output_id": snapshot.target_output_id,
            "source_swarm_id": snapshot.source_swarm_id,
            "implementation_status": snapshot.implementation_status,
            "claim_guard_status": snapshot.claim_guard_status,
            "artifact_count": snapshot.artifact_count,
            "evidence_count": snapshot.evidence_count,
            "final_evidence_count": snapshot.final_evidence_count,
            "approval_count": snapshot.approval_count,
            "available_actions": snapshot.available_actions,
            "reason": snapshot.reason,
        }
    }
