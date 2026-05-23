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


def _safe_preview(value: Any, *, limit: int = 220) -> str:
    if value is None:
        return ""
    text = str(value).replace("\r", " ").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _message_text(message: Any) -> str:
    payload = _as_dict(getattr(message, "payload", None))
    content = payload.get("content") or payload.get("message") or payload.get("response") or ""
    return _safe_preview(content, limit=260)


def _message_role(message: Any) -> str:
    payload = _as_dict(getattr(message, "payload", None))
    return str(payload.get("role") or getattr(message, "type", "") or "").strip().lower()


def _artifact_label(artifact: Any, index: int) -> str:
    data = _as_dict(artifact)
    return _first_non_empty(
        data.get("name"),
        data.get("title"),
        data.get("path"),
        data.get("id"),
        f"artifact_{index + 1}",
    ) or f"artifact_{index + 1}"


def _evidence_label(evidence: Any, index: int) -> str:
    if hasattr(evidence, "model_dump"):
        data = evidence.model_dump(mode="json")
    else:
        data = _as_dict(evidence)
    return _first_non_empty(
        data.get("id"),
        data.get("summary"),
        data.get("kind"),
        data.get("type"),
        f"evidence_{index + 1}",
    ) or f"evidence_{index + 1}"


def build_response_context(
    swarm: Any,
    *,
    route: str | None = None,
    user_message: str | None = None,
    payload: dict[str, Any] | None = None,
    max_messages: int = 8,
    max_items: int = 6,
) -> str:
    """Build a compact grounded response context for future model-authored replies.

    This context is not a chain-of-thought. It is an explicit state summary for
    grounding assistant responses and preventing false action claims.
    """

    snapshot = build_ri_state_snapshot(
        swarm,
        route=route,
        user_message=user_message,
        payload=payload,
    )

    final_result = dict(_as_dict(getattr(swarm, "final_result", None)))
    payload = _as_dict(payload)
    if "refinement_request" in payload:
        final_result["refinement_request"] = payload["refinement_request"]
    if "project_intake_state" in payload:
        final_result["project_intake_state"] = payload["project_intake_state"]

    project_intake_state = dict(_as_dict(getattr(swarm, "project_intake_state", None)))
    if "project_intake_state" in payload:
        project_intake_state = _as_dict(payload["project_intake_state"])

    refinement_request = _as_dict(final_result.get("refinement_request"))
    artifacts = list(getattr(swarm, "artifacts", []) or [])
    evidence = list(getattr(swarm, "evidence", []) or [])
    final_evidence = list(getattr(swarm, "final_evidence", []) or [])
    messages = list(getattr(swarm, "messages", []) or [])

    lines: list[str] = [
        "[response_context]",
        "Use this state as grounding. Do not claim actions were executed unless artifacts/evidence/events prove it.",
        "",
        "[ri_state]",
        f"- route: {snapshot.current_route or 'unknown'}",
        f"- pending_action: {snapshot.pending_action or 'none'}",
        f"- target_output_id: {snapshot.target_output_id or 'none'}",
        f"- source_swarm_id: {snapshot.source_swarm_id or 'none'}",
        f"- project_intake_status: {snapshot.project_intake_status or 'none'}",
        f"- implementation_status: {snapshot.implementation_status or 'none'}",
        f"- claim_guard_status: {snapshot.claim_guard_status or 'none'}",
        f"- available_actions: {', '.join(snapshot.available_actions) if snapshot.available_actions else 'none'}",
        "",
        "[current_user_message]",
        _safe_preview(user_message, limit=500) or "none",
        "",
    ]

    if refinement_request:
        lines.extend([
            "[refinement_request]",
            f"- output_id: {_safe_preview(refinement_request.get('output_id')) or 'none'}",
            f"- source_swarm_id: {_safe_preview(refinement_request.get('source_swarm_id')) or 'none'}",
            f"- requested_change: {_safe_preview(refinement_request.get('requested_change'), limit=500) or 'none'}",
            f"- status: {_safe_preview(refinement_request.get('status')) or 'none'}",
            f"- next_action: {_safe_preview(refinement_request.get('next_action')) or snapshot.pending_action or 'none'}",
            "",
        ])

    if project_intake_state:
        answers = _as_dict(project_intake_state.get("answers"))
        lines.extend([
            "[project_intake_state]",
            f"- status: {_safe_preview(project_intake_state.get('status')) or 'none'}",
            f"- current_question_id: {_safe_preview(project_intake_state.get('current_question_id')) or 'none'}",
            f"- answered_count: {len(answers)}",
            "",
        ])

    if final_result:
        lines.extend([
            "[final_result]",
            f"- status: {_safe_preview(final_result.get('status')) or 'none'}",
            f"- route: {_safe_preview(final_result.get('route')) or 'none'}",
            f"- artifact_kind: {_safe_preview(final_result.get('artifact_kind')) or 'none'}",
            f"- implementation_performed: {_safe_preview(final_result.get('implementation_performed')) or 'none'}",
            f"- summary: {_safe_preview(final_result.get('summary'), limit=500) or 'none'}",
            "",
        ])

    lines.extend([
        "[artifacts]",
        *(f"- {_safe_preview(_artifact_label(item, idx), limit=240)}" for idx, item in enumerate(artifacts[:max_items])),
        "none" if not artifacts else "",
        "",
        "[evidence]",
        *(f"- {_safe_preview(_evidence_label(item, idx), limit=240)}" for idx, item in enumerate((final_evidence or evidence)[:max_items])),
        "none" if not (final_evidence or evidence) else "",
        "",
        "[recent_messages]",
    ])

    for message in messages[-max_messages:]:
        role = _message_role(message) or "unknown"
        body = _message_text(message)
        if body:
            lines.append(f"- {role}: {body}")

    if not messages:
        lines.append("none")

    return "\n".join(line for line in lines if line is not None)
