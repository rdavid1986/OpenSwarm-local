"""Model-assisted dynamic intake plan enrichment.

This module is side-effect free. It may ask a local model to enrich a generated
App Builder plan, but it never mutates swarm state, executes tools, or changes
DAG selection fields. Callers must merge enrichment conservatively.
"""

from __future__ import annotations

import json
from typing import Any, Callable

from backend.apps.agents.providers.ollama_adapter import OllamaAdapter
from backend.apps.agents.providers.provider_health import check_local_model_provider_health, is_local_model
from backend.apps.agents.runtime.provider import ProviderTurnContext
from backend.apps.swarms.model_response_contract import build_model_response_contract_prompt
from backend.apps.swarms.project_memory import build_project_memory_from_swarm_state
from backend.apps.swarms.state_context import build_state_context_payload, build_state_context_prompt
from backend.apps.swarms.system_prompt import build_openswarm_system_prompt


CONFIDENCE_THRESHOLD = 0.70
MAX_LIST_ITEMS = 8
MAX_TEXT = 600


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


def _text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        text = _as_text(item)[:MAX_TEXT]
        if text and text not in result:
            result.append(text)
        if len(result) >= MAX_LIST_ITEMS:
            break
    return result


def build_dynamic_plan_enrichment_prompt(
    *,
    generated_plan: dict[str, Any],
    intake_state: dict[str, Any],
    project_memory_manifest: dict[str, Any] | None = None,
) -> str:
    system_prompt = build_openswarm_system_prompt(mode="app_builder", task_kind="dynamic_intake")
    state_context = build_state_context_payload(
        mode="app_builder",
        route="dynamic_intake_plan_enrichment",
        user_message=_as_text(intake_state.get("user_message") or intake_state.get("initial_prompt")),
        creation_type=_as_text(generated_plan.get("app_type") or intake_state.get("intake_profile")) or None,
        project_intake_status=_as_text(intake_state.get("status") or intake_state.get("intake_status")) or None,
        project_memory_manifest=project_memory_manifest,
        available_context={
            "intake_mode": intake_state.get("intake_mode"),
            "intake_profile": intake_state.get("intake_profile"),
            "skipped_questions": intake_state.get("skipped_questions"),
            "question_policy": intake_state.get("question_policy"),
        },
    )
    payload = {
        "task": "Enrich an OpenSwarm App Builder generated_plan without changing core DAG selection fields.",
        "openswarm_system_prompt": system_prompt,
        "state_context": state_context,
        "state_context_prompt": build_state_context_prompt(state_context),
        "model_response_contract_prompt": build_model_response_contract_prompt("dynamic_intake"),
        "generated_plan": generated_plan,
        "intake_state": {
            "intake_mode": intake_state.get("intake_mode"),
            "intake_profile": intake_state.get("intake_profile"),
            "skipped_questions": intake_state.get("skipped_questions"),
            "question_policy": intake_state.get("question_policy"),
            "answers": intake_state.get("answers"),
        },
        "rules": [
            "Return only one JSON object.",
            "Follow openswarm_system_prompt.",
            "Use state_context as the real state snapshot.",
            "Use model_response_contract_prompt as safety guidance only; keep expected_json_shape as the required output schema.",
            "Do not execute tools.",
            "Do not modify or restate core fields as replacements.",
            "Do not change app_type, frontend, backend, database, auth, payments or deploy.",
            "Only add enrichment fields that help planning and implementation.",
            "Use short lists and concise strings.",
            "If unsure, return confidence below threshold.",
        ],
        "expected_json_shape": {
            "confidence": 0.0,
            "mvp_scope": ["short scope item"],
            "recommended_stack_reason": "short explanation",
            "implementation_notes": ["short implementation note"],
            "risks": ["short risk"],
            "out_of_scope_reason": "short explanation",
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def normalize_dynamic_plan_enrichment(model_output: Any) -> dict[str, Any]:
    parsed = model_output if isinstance(model_output, dict) else _extract_json_object(str(model_output or ""))
    if not parsed:
        return {
            "ok": False,
            "source": "fallback",
            "confidence": 0.0,
            "reason": "Model did not return a valid JSON object.",
            "plan_enrichment": {},
        }

    try:
        confidence = float(parsed.get("confidence"))
    except Exception:
        confidence = 0.0

    if confidence < CONFIDENCE_THRESHOLD:
        return {
            "ok": False,
            "source": "fallback",
            "confidence": max(0.0, min(confidence, 1.0)),
            "reason": "Model confidence is below the safety threshold.",
            "plan_enrichment": {},
        }

    enrichment = {
        "mvp_scope": _text_list(parsed.get("mvp_scope")),
        "recommended_stack_reason": _as_text(parsed.get("recommended_stack_reason"))[:MAX_TEXT],
        "implementation_notes": _text_list(parsed.get("implementation_notes")),
        "risks": _text_list(parsed.get("risks")),
        "out_of_scope_reason": _as_text(parsed.get("out_of_scope_reason"))[:MAX_TEXT],
    }
    enrichment = {key: value for key, value in enrichment.items() if value}

    return {
        "ok": True,
        "source": "model",
        "confidence": max(0.0, min(confidence, 1.0)),
        "reason": "Model-assisted plan enrichment.",
        "plan_enrichment": enrichment,
    }


async def enrich_dynamic_intake_plan(
    *,
    generated_plan: dict[str, Any],
    intake_state: dict[str, Any],
    model: str = "qwen2.5-coder:14b",
    adapter_factory: Callable[[], OllamaAdapter] | None = None,
    project_memory_source: Any = None,
    project_memory_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    adapter = adapter_factory() if adapter_factory else OllamaAdapter(allow_network=True, supports_json_mode=True)

    if (adapter_factory is None or isinstance(adapter, OllamaAdapter)) and is_local_model(model):
        health = check_local_model_provider_health(
            model=model,
            base_url=getattr(adapter, "base_url", None),
            timeout_seconds=2.0,
        )
        if not health.get("ok"):
            return {
                "ok": False,
                "source": "fallback",
                "confidence": 0.0,
                "reason": _as_text(health.get("reason")) or "Local model provider is unavailable.",
                "plan_enrichment": {},
                "provider_health": health,
            }

    context = ProviderTurnContext(
        session_id="dynamic-intake-plan-enrichment",
        agent_id="dynamic-intake-plan-enrichment",
        model=model,
        system_prompt=build_openswarm_system_prompt(mode="app_builder", task_kind="dynamic_intake"),
        messages=[
            {
                "role": "user",
                "content": build_dynamic_plan_enrichment_prompt(
                    generated_plan=generated_plan,
                    intake_state=intake_state,
                    project_memory_manifest=project_memory_manifest
                    if project_memory_manifest is not None
                    else build_project_memory_from_swarm_state(project_memory_source)
                    if project_memory_source is not None
                    else None,
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
                return normalize_dynamic_plan_enrichment({"confidence": 0.0})
    except Exception:
        return normalize_dynamic_plan_enrichment({"confidence": 0.0})

    return normalize_dynamic_plan_enrichment(assistant_content)
