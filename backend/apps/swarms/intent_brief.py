"""Intent Brief builder for Senior Swarm Team orchestration.

SST.1 keeps this module side-effect free. It does not call models, fetch web
research, mutate SwarmState, persist data, execute tools, or authorize actions.
It only summarizes already-loaded swarm state into a compact intent brief that
future Master Planner and Domain Planner flows can consume.
"""

from __future__ import annotations

from typing import Any

MAX_TEXT = 600
MAX_ITEMS = 8


def _as_text(value: Any, *, max_chars: int = MAX_TEXT) -> str:
    return str(value or "").strip()[:max_chars]


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "model_dump"):
        try:
            dumped = value.model_dump(mode="json")
            return dumped if isinstance(dumped, dict) else {}
        except Exception:
            return {}
    return dict(getattr(value, "__dict__", {}) or {}) if value is not None else {}


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _get(source: Any, key: str, default: Any = None) -> Any:
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


def _message_content(message: Any) -> str:
    payload = _get(message, "payload", {}) or {}
    if isinstance(payload, dict):
        return _as_text(
            payload.get("content")
            or payload.get("message")
            or payload.get("user_message")
            or payload.get("final_message")
        )
    return ""


def _message_role(message: Any) -> str:
    payload = _get(message, "payload", {}) or {}
    if isinstance(payload, dict):
        role = payload.get("role") or payload.get("sender") or payload.get("author")
        if role:
            return _as_text(role, max_chars=60).lower()
    message_type = _as_text(_get(message, "type"), max_chars=80).lower()
    from_agent_id = _as_text(_get(message, "from_agent_id"), max_chars=80).lower()
    if "user" in message_type or from_agent_id in {"user", "human"}:
        return "user"
    if (
        "assistant" in message_type
        or from_agent_id in {"assistant", "system", "openswarm"}
        or "agent" in from_agent_id
        or "swarm" in from_agent_id
    ):
        return "assistant"
    return "unknown"


def extract_user_intent_messages(swarm: Any, *, limit: int = MAX_ITEMS) -> list[str]:
    """Extract recent user-provided intent messages from loaded swarm messages."""

    results: list[str] = []
    for message in _as_list(_get(swarm, "messages", [])):
        content = _message_content(message)
        if not content:
            continue
        role = _message_role(message)
        if role == "user":
            if content not in results:
                results.append(content)
    return results[-limit:]


def extract_intake_summary(swarm: Any) -> dict[str, Any]:
    """Extract compact intake summary without inventing missing answers."""

    state = _as_dict(_get(swarm, "project_intake_state", {}))
    generated_plan = _as_dict(state.get("generated_plan"))
    answers = _as_dict(state.get("answers"))
    return {
        "status": state.get("status"),
        "current_question_id": state.get("current_question_id"),
        "intake_mode": state.get("intake_mode"),
        "question_policy": state.get("question_policy") if isinstance(state.get("question_policy"), dict) else {},
        "answers_keys": sorted(str(key) for key in answers.keys()),
        "generated_plan": generated_plan,
    }


def extract_existing_project_context(swarm: Any) -> dict[str, Any]:
    """Extract already-loaded project context relevant to intent expansion."""

    final_result = _as_dict(_get(swarm, "final_result", {}))
    output_bridge = _as_dict(_get(swarm, "output_bridge", {}))
    implementation_state = _as_dict(_get(swarm, "implementation_state", {}))
    return {
        "has_final_result": bool(final_result),
        "final_result_status": final_result.get("status"),
        "final_result_route": final_result.get("route"),
        "has_output_bridge": bool(output_bridge),
        "output_id": output_bridge.get("output_id") or output_bridge.get("id"),
        "implementation_state": implementation_state.get("state") or implementation_state.get("status"),
        "artifacts_count": len(_as_list(_get(swarm, "artifacts", []))),
        "evidence_count": len(_as_list(_get(swarm, "evidence", []))),
        "final_evidence_count": len(_as_list(_get(swarm, "final_evidence", []))),
        "decisions_count": len(_as_list(_get(swarm, "decisions", []))),
    }


def build_intent_brief(swarm: Any, *, user_message: str | None = None) -> dict[str, Any]:
    """Build a compact intent brief from loaded swarm state."""

    user_prompt = _as_text(_get(swarm, "user_prompt"))
    direct_user_message = _as_text(user_message)
    user_messages = extract_user_intent_messages(swarm)
    intake_summary = extract_intake_summary(swarm)
    project_context = extract_existing_project_context(swarm)

    primary_goal = direct_user_message or user_prompt or (user_messages[-1] if user_messages else "")
    generated_plan = intake_summary.get("generated_plan") if isinstance(intake_summary.get("generated_plan"), dict) else {}
    if not primary_goal and generated_plan:
        primary_goal = _as_text(generated_plan.get("main_goal") or generated_plan.get("summary"))

    return {
        "kind": "intent_brief",
        "status": "ready" if primary_goal else "missing_goal",
        "primary_goal": primary_goal,
        "original_user_prompt": user_prompt,
        "latest_user_message": direct_user_message or None,
        "recent_user_intent_messages": user_messages,
        "intake_summary": intake_summary,
        "project_context": project_context,
        "known_constraints": extract_known_constraints(swarm),
        "open_questions": extract_open_questions(swarm),
        "research_status": "not_requested",
        "source": "loaded_swarm_state",
    }


def extract_known_constraints(swarm: Any) -> list[str]:
    """Extract explicit constraints from loaded intake/generated plan state."""

    constraints: list[str] = []
    intake = extract_intake_summary(swarm)
    plan = intake.get("generated_plan") if isinstance(intake.get("generated_plan"), dict) else {}
    for key in ("constraints", "out_of_scope", "mvp_priority", "backend", "database", "frontend", "visual_style"):
        value = plan.get(key)
        if isinstance(value, list):
            for item in value:
                text = _as_text(item, max_chars=240)
                if text and text not in constraints:
                    constraints.append(text)
        else:
            text = _as_text(value, max_chars=240)
            if text and text not in constraints:
                constraints.append(f"{key}: {text}")
    return constraints[:MAX_ITEMS]


def extract_open_questions(swarm: Any) -> list[str]:
    """Extract pending/open questions already present in intake or clarification state."""

    questions: list[str] = []
    intake = _as_dict(_get(swarm, "project_intake_state", {}))
    current_question_id = _as_text(intake.get("current_question_id"), max_chars=120)
    if current_question_id:
        questions.append(f"current_question_id: {current_question_id}")

    final_result = _as_dict(_get(swarm, "final_result", {}))
    clarification = _as_dict(final_result.get("context_clarification"))
    question = _as_text(clarification.get("clarification_question"), max_chars=240)
    if question:
        questions.append(question)

    return questions[:MAX_ITEMS]
