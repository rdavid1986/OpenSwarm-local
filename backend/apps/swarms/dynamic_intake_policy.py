"""Model-assisted dynamic intake question policy.

This module is side-effect free. It may ask a local model to decide which intake
questions are relevant, but it never mutates swarm state, executes tools, or
changes generated plans. Callers must keep the deterministic fallback path.
"""

from __future__ import annotations

import json
from typing import Any, Callable

from backend.apps.agents.providers.ollama_adapter import OllamaAdapter
from backend.apps.agents.providers.provider_health import check_local_model_provider_health, is_local_model
from backend.apps.agents.runtime.provider import ProviderTurnContext


CONFIDENCE_THRESHOLD = 0.70
KNOWN_INTAKE_PROFILES = {"static_site", "landing", "dashboard", "full_app", "unknown"}


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _extract_json_object(text: str) -> dict[str, Any] | None:
    raw = (text or "").strip()
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            parsed = json.loads(raw[start : end + 1])
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None


def _question_ids(questions: list[dict[str, Any]]) -> set[str]:
    return {
        _as_text(question.get("id"))
        for question in questions
        if isinstance(question, dict) and _as_text(question.get("id"))
    }


def build_dynamic_intake_policy_prompt(
    *,
    user_message: str,
    questions: list[dict[str, Any]],
    fallback_profile: dict[str, Any],
) -> str:
    payload = {
        "task": "Decide the minimal safe App Builder intake question policy.",
        "user_message": user_message,
        "available_questions": [
            {
                "id": question.get("id"),
                "title": question.get("title"),
                "prompt": question.get("prompt"),
            }
            for question in questions
            if isinstance(question, dict)
        ],
        "fallback_profile": fallback_profile,
        "rules": [
            "Return only one JSON object.",
            "Do not execute tools.",
            "Do not invent question ids.",
            "Only skip questions that are clearly irrelevant to the requested project.",
            "For full apps, dashboards, CRUD, auth, payments, API, backend, users or database requests, do not skip relevant technical questions.",
            "Use skipped_questions only for questions that should not be asked.",
            "Use required_questions for questions that should still be asked.",
            "If unsure, keep the question required.",
        ],
        "expected_json_shape": {
            "profile": "static_site | landing | dashboard | full_app | unknown",
            "confidence": 0.0,
            "skipped_questions": ["question_id"],
            "required_questions": ["question_id"],
            "reason": "short reason",
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def normalize_dynamic_intake_policy(
    model_output: Any,
    *,
    questions: list[dict[str, Any]],
    fallback_profile: dict[str, Any],
) -> dict[str, Any]:
    parsed = model_output if isinstance(model_output, dict) else _extract_json_object(str(model_output or ""))
    valid_question_ids = _question_ids(questions)

    fallback_skipped = [
        question_id for question_id in fallback_profile.get("skipped_questions", [])
        if _as_text(question_id) in valid_question_ids
    ]

    def fallback(reason: str) -> dict[str, Any]:
        return {
            "ok": False,
            "source": "fallback",
            "profile": _as_text(fallback_profile.get("profile")) or "unknown",
            "confidence": float(fallback_profile.get("confidence") or 0.0),
            "skipped_questions": fallback_skipped,
            "required_questions": [
                question_id for question_id in valid_question_ids
                if question_id not in set(fallback_skipped)
            ],
            "reason": reason or _as_text(fallback_profile.get("reason")) or "Using deterministic fallback intake policy.",
        }

    if not parsed:
        return fallback("Model did not return a valid JSON object.")

    profile = _as_text(parsed.get("profile")) or "unknown"
    if profile not in KNOWN_INTAKE_PROFILES:
        return fallback("Model returned an unknown intake profile.")

    try:
        confidence = float(parsed.get("confidence"))
    except Exception:
        confidence = 0.0

    if confidence < CONFIDENCE_THRESHOLD:
        return fallback("Model confidence is below the safety threshold.")

    raw_skipped = parsed.get("skipped_questions")
    raw_required = parsed.get("required_questions")
    skipped = [
        _as_text(item) for item in raw_skipped
        if _as_text(item) in valid_question_ids
    ] if isinstance(raw_skipped, list) else []
    required = [
        _as_text(item) for item in raw_required
        if _as_text(item) in valid_question_ids
    ] if isinstance(raw_required, list) else []

    skipped_set = set(skipped)
    required_set = set(required)

    if skipped_set & required_set:
        return fallback("Model marked the same question as skipped and required.")

    risky_questions = {"backend", "database", "auth", "payments"}
    if profile == "full_app" and skipped_set & risky_questions:
        return fallback("Model tried to skip technical questions for a full app.")

    if not required:
        required = [
            question_id for question_id in valid_question_ids
            if question_id not in skipped_set
        ]

    return {
        "ok": True,
        "source": "model",
        "profile": profile,
        "confidence": max(0.0, min(confidence, 1.0)),
        "skipped_questions": skipped,
        "required_questions": required,
        "reason": _as_text(parsed.get("reason")) or "Model-assisted intake policy.",
    }


async def resolve_dynamic_intake_policy(
    *,
    user_message: str,
    questions: list[dict[str, Any]],
    fallback_profile: dict[str, Any],
    model: str = "qwen2.5-coder:14b",
    adapter_factory: Callable[[], OllamaAdapter] | None = None,
) -> dict[str, Any]:
    adapter = adapter_factory() if adapter_factory else OllamaAdapter(allow_network=True, supports_json_mode=True)

    if (adapter_factory is None or isinstance(adapter, OllamaAdapter)) and is_local_model(model):
        health = check_local_model_provider_health(
            model=model,
            base_url=getattr(adapter, "base_url", None),
            timeout_seconds=2.0,
        )
        if not health.get("ok"):
            fallback = normalize_dynamic_intake_policy(
                None,
                questions=questions,
                fallback_profile=fallback_profile,
            )
            fallback["reason"] = _as_text(health.get("reason")) or fallback["reason"]
            fallback["provider_health"] = health
            return fallback

    context = ProviderTurnContext(
        session_id="dynamic-intake-policy",
        agent_id="dynamic-intake-policy",
        model=model,
        system_prompt=(
            "You are OpenSwarm's App Builder intake policy resolver. "
            "Return only one JSON object. Do not execute tools. "
            "Decide which intake questions are necessary or can be safely skipped."
        ),
        messages=[
            {
                "role": "user",
                "content": build_dynamic_intake_policy_prompt(
                    user_message=user_message,
                    questions=questions,
                    fallback_profile=fallback_profile,
                ),
            }
        ],
        tools=[],
    )

    assistant_content = ""
    try:
        async for event in adapter.run_turn(context):
            if event.type == "message_final":
                message = event.payload.get("message") if isinstance(event.payload, dict) else {}
                assistant_content = _as_text((message or {}).get("content"))
            elif event.type == "error":
                return normalize_dynamic_intake_policy(
                    {"confidence": 0.0},
                    questions=questions,
                    fallback_profile=fallback_profile,
                )
    except Exception:
        return normalize_dynamic_intake_policy(
            {"confidence": 0.0},
            questions=questions,
            fallback_profile=fallback_profile,
        )

    return normalize_dynamic_intake_policy(
        assistant_content,
        questions=questions,
        fallback_profile=fallback_profile,
    )
