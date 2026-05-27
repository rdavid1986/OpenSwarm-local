from backend.config.Apps import SubApp
from backend.apps.agents.agent_manager import agent_manager
from backend.apps.agents.ws_manager import ws_manager
from backend.apps.agents.models import AgentConfig, ApprovalResponse
from backend.apps.agents.plans import create_plan_from_text, get_plan, list_plans, update_execution_state, append_validation_log
from contextlib import asynccontextmanager
from fastapi import WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse
import asyncio
import os
import json
import logging

logger = logging.getLogger(__name__)

@asynccontextmanager
async def agents_lifespan():
    logger.info("Agents sub-app starting")
    await agent_manager.reconcile_on_startup()
    await agent_manager.restore_all_sessions()
    yield
    logger.info("Agents sub-app shutting down")
    for session_id in list(agent_manager.tasks.keys()):
        await agent_manager.stop_agent(session_id)
    await agent_manager.persist_all_sessions()

agents = SubApp("agents", agents_lifespan)


def _mode_label(mode: str | None) -> str:
    labels = {
        "agent": "Agent",
        "ask": "Ask",
        "plan": "Plan",
        "skill-builder": "Skill Builder",
        "view-builder": "View Builder",
        "app-builder": "App Builder",
    }
    normalized = str(mode or "").strip()
    return labels.get(normalized, normalized.replace("-", " ").title() or "Session")


def _session_payload(session):
    payload = session.model_dump(mode="json")
    mode_label = _mode_label(payload.get("mode"))
    name = str(payload.get("name") or payload.get("id") or "Untitled").strip()
    payload["mode_label"] = mode_label
    payload["display_label"] = f"{mode_label} · {name}"
    payload["technical_id"] = payload.get("id")
    return payload


# REST Endpoints

@agents.router.get("/sessions")
async def list_sessions(dashboard_id: str = ""):
    sessions = agent_manager.get_all_sessions(dashboard_id=dashboard_id or None)
    return {"sessions": [_session_payload(s) for s in sessions]}

@agents.router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    session = agent_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return _session_payload(session)

@agents.router.post("/launch")
async def launch_agent(config: AgentConfig):
    session = await agent_manager.launch_agent(config)
    return {"session_id": session.id, "session": _session_payload(session)}

@agents.router.get("/plans")
async def api_list_plans(dashboard_id: str | None = None):
    return list_plans(dashboard_id=dashboard_id)


@agents.router.get("/plans/{plan_id}")
async def api_get_plan(plan_id: str):
    result = get_plan(plan_id)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail=result.get("error", "Plan not found"))
    return result


@agents.router.post("/plans")
async def api_create_plan(body: dict):
    title = str(body.get("title") or "").strip()
    content = str(body.get("content") or "").strip()

    if not title:
        raise HTTPException(status_code=400, detail="title is required")
    if not content:
        raise HTTPException(status_code=400, detail="content is required")

    return create_plan_from_text(
        title,
        content,
        session_id=body.get("session_id"),
        created_by_session_id=body.get("created_by_session_id"),
        dashboard_id=body.get("dashboard_id"),
        source_mode=str(body.get("source_mode") or "plan"),
    )


@agents.router.patch("/plans/{plan_id}/execution-state")
async def api_update_execution_state(plan_id: str, body: dict):
    result = update_execution_state(plan_id, body)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail=result.get("error", "Execution state not found"))
    return result


async def _watch_plan_execution_completion(
    session_id: str,
    plan_id: str,
    minimum_message_count: int,
    timeout_seconds: int = 120,
):
    """Cierra el execution_state del plan cuando el Agent produce una respuesta final nueva."""
    for _ in range(timeout_seconds):
        await asyncio.sleep(1)

        session = agent_manager.get_session(session_id)
        if not session:
            continue

        new_messages = list(session.messages)[minimum_message_count:]

        for message in reversed(new_messages):
            if getattr(message, "role", None) == "assistant" and str(getattr(message, "content", "")).strip():
                update_execution_state(plan_id, {
                    "status": "completed",
                    "current_phase_index": 1,
                    "completed_phase_indexes": [0],
                    "last_error": None,
                    "last_execution_session_id": session_id,
                })
                append_validation_log(plan_id, "execute_plan_completed", {
                    "session_id": session_id,
                    "message_count": len(session.messages),
                })
                return

    update_execution_state(plan_id, {
        "status": "running",
        "last_error": "Timed out waiting for new final assistant message.",
    })
    append_validation_log(plan_id, "execute_plan_timeout", {
        "session_id": session_id,
        "timeout_seconds": timeout_seconds,
    })


@agents.router.post("/sessions/{session_id}/execute-plan")
async def execute_plan(session_id: str, body: dict):
    plan_id = str(body.get("plan_id") or "").strip()
    if not plan_id:
        raise HTTPException(status_code=400, detail="plan_id is required")

    result = get_plan(plan_id)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail=result.get("error", "Plan not found"))

    plan = result.get("plan") or {}
    title = plan.get("title") or plan_id
    content = plan.get("content") or ""

    prompt = f"""Ejecutá este plan persistente.

PLAN_ID: {plan_id}
TÍTULO: {title}

Reglas:
- Leé el plan antes de actuar.
- Ejecutá solo la primera fase pendiente.
- No avances fases sin validar.
- Si falta una decisión, preguntá antes de modificar.
- Después de ejecutar, resumí archivos modificados y validación realizada.

Contenido del plan:
{content}
"""

    session_before_execution = agent_manager.get_session(session_id)
    if not session_before_execution:
        raise HTTPException(status_code=404, detail="Session not found")

    minimum_message_count = len(session_before_execution.messages)

    update_execution_state(plan_id, {
        "status": "running",
        "current_phase_index": 0,
        "completed_phase_indexes": [],
        "failed_phase_indexes": [],
        "last_error": None,
        "last_execution_session_id": session_id,
    })
    append_validation_log(plan_id, "execute_plan_sent", {
        "session_id": session_id,
        "minimum_message_count": minimum_message_count,
    })

    await agent_manager.send_message(
        session_id,
        prompt,
        mode="agent",
        hidden=False,
    )

    asyncio.create_task(_watch_plan_execution_completion(
        session_id,
        plan_id,
        minimum_message_count,
    ))

    return {
        "ok": True,
        "session_id": session_id,
        "plan_id": plan_id,
        "status": "sent_to_agent",
    }


@agents.router.post("/sessions/{session_id}/message")
async def send_message(session_id: str, body: dict):
    prompt = body.get("prompt", "")
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt is required")

    # Pre-flight MCP suggestion (Phase 3, Layer N). Runs in parallel with
    # the agent launch path — if it produces suggestions, they're
    # surfaced inline in the chat via agent:mcp_suggestions WS event.
    # Fails open: any error from the classifier is swallowed and the
    # agent proceeds normally. The classifier is short-circuited for
    # obviously-local prompts (greetings, shell commands, file paths).
    try:
        from backend.apps.agents.mcp_preflight import run_preflight
        from backend.apps.agents.ws_manager import ws_manager as _ws

        async def _emit_preflight():
            try:
                result = await run_preflight(prompt)
                if result.get("suggestions") or result.get("is_vague"):
                    await _ws.send_to_session(session_id, "agent:mcp_suggestions", {
                        "session_id": session_id,
                        "suggestions": result.get("suggestions", []),
                        "is_vague": bool(result.get("is_vague")),
                    })
            except Exception:
                pass

        # Non-blocking — don't gate the agent on the classifier.
        import asyncio as _asyncio
        _asyncio.create_task(_emit_preflight())
    except Exception:
        pass

    await agent_manager.send_message(
        session_id,
        prompt,
        mode=body.get("mode"),
        model=body.get("model"),
        images=body.get("images"),
        context_paths=body.get("context_paths"),
        forced_tools=body.get("forced_tools"),
        attached_skills=body.get("attached_skills"),
        hidden=body.get("hidden", False),
        selected_browser_ids=body.get("selected_browser_ids"),
        client_message_id=body.get("client_message_id"),
    )
    return {"ok": True}

@agents.router.post("/sessions/{session_id}/stop")
async def stop_agent(session_id: str):
    await agent_manager.stop_agent(session_id)
    return {"ok": True}

@agents.router.post("/approval")
async def handle_approval(response: ApprovalResponse):
    agent_manager.handle_approval(response.request_id, {
        "behavior": response.behavior,
        "message": response.message,
        "updated_input": response.updated_input,
    })
    return {"ok": True}

@agents.router.post("/sessions/{session_id}/edit_message")
async def edit_message(session_id: str, body: dict):
    message_id = body.get("message_id")
    new_content = body.get("content", "")
    if not message_id or not new_content:
        raise HTTPException(status_code=400, detail="message_id and content are required")
    await agent_manager.edit_message(session_id, message_id, new_content)
    return {"ok": True}

@agents.router.post("/sessions/{session_id}/switch_branch")
async def switch_branch(session_id: str, body: dict):
    branch_id = body.get("branch_id", "")
    if not branch_id:
        raise HTTPException(status_code=400, detail="branch_id is required")
    await agent_manager.switch_branch(session_id, branch_id)
    return {"ok": True}

@agents.router.post("/sessions/{session_id}/generate-title")
async def generate_title(session_id: str, body: dict):
    prompt = body.get("prompt", "")
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt is required")
    title = await agent_manager.generate_title(session_id, prompt)
    return {"title": title}

@agents.router.post("/sessions/{session_id}/generate-group-meta")
async def generate_group_meta(session_id: str, body: dict):
    group_id = body.get("group_id", "")
    tool_calls = body.get("tool_calls", [])
    if not group_id or not tool_calls:
        raise HTTPException(status_code=400, detail="group_id and tool_calls are required")
    result = await agent_manager.generate_group_meta(
        session_id,
        group_id,
        tool_calls,
        results_summary=body.get("results_summary"),
        is_refinement=body.get("is_refinement", False),
    )
    return result

@agents.router.patch("/sessions/{session_id}")
async def update_session(session_id: str, body: dict):
    session = agent_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    await agent_manager.update_session(session_id, **body)
    return {"ok": True}

@agents.router.get("/sessions/{session_id}/branches")
async def get_branches(session_id: str):
    session = agent_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "branches": {k: v.model_dump(mode="json") for k, v in session.branches.items()},
        "active_branch_id": session.active_branch_id,
    }

@agents.router.post("/sessions/{session_id}/duplicate")
async def duplicate_session(session_id: str, body: dict = {}):
    try:
        session = await agent_manager.duplicate_session(
            session_id,
            dashboard_id=body.get("dashboard_id"),
            up_to_message_id=body.get("up_to_message_id"),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"session": session.model_dump(mode="json")}

@agents.router.post("/sessions/{session_id}/close")
async def close_session(session_id: str):
    try:
        await agent_manager.close_session(session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"ok": True}

@agents.router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    await agent_manager.delete_session(session_id)
    return {"ok": True}

@agents.router.get("/history")
async def get_history(q: str = "", limit: int = 20, offset: int = 0, dashboard_id: str = ""):
    return agent_manager.get_history(
        q=q, limit=limit, offset=offset,
        dashboard_id=dashboard_id or None,
    )

@agents.router.get("/sessions/{session_id}/browser-agents")
async def get_browser_agent_children(session_id: str):
    children = agent_manager.get_browser_agent_children(session_id)
    return {"sessions": children}

@agents.router.post("/sessions/{session_id}/resume")
async def resume_session(session_id: str):
    try:
        session = await agent_manager.resume_session(session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"session": session.model_dump(mode="json")}


@agents.router.post("/sessions/{session_id}/warm-cache")
async def warm_session_cache(session_id: str):
    """Fire a max_tokens=1 dummy request through the agent path so
    Anthropic processes the system+tools prefix and writes the prompt
    cache. The next real user turn lands a cache hit instead of paying
    cold-start TTFT. Non-blocking, fire-and-forget on the frontend.
    Returns 200 even on failure (best-effort).
    """
    try:
        await agent_manager.warm_prompt_cache(session_id)
    except Exception:
        pass
    return {"ok": True}


# ---------------------------------------------------------------------------
# 9Router / Subscription endpoints
# ---------------------------------------------------------------------------

@agents.router.get("/subscriptions/status")
async def subscriptions_status():
    """Check if 9Router is running and list connected providers."""
    from backend.apps.nine_router import is_running, get_providers, get_models
    if not is_running():
        return {"running": False, "providers": [], "models": []}
    connections = await get_providers()
    models = await get_models()
    # Frontend consumers (OnboardingModal, Settings) read
    # `data.providers.connections` — preserve that envelope here.
    return {"running": True, "providers": {"connections": connections}, "models": models}


@agents.router.post("/subscriptions/connect")
async def subscriptions_connect(body: dict):
    """Start OAuth flow for a subscription provider."""
    from backend.apps.nine_router import is_running, ensure_running, start_oauth
    provider = body.get("provider", "")
    if not provider:
        raise HTTPException(status_code=400, detail="provider required")

    if not is_running():
        await ensure_running()
        if not is_running():
            raise HTTPException(status_code=503, detail="9Router not available. Please install Node.js.")

    try:
        result = await start_oauth(provider)

        # For auth_code flows, store pending state so the callback can exchange
        if result.get("flow") == "authorization_code" and result.get("state"):
            from backend.main import _pending_oauth
            _pending_oauth[result["state"]] = {
                "provider": provider,
                "code_verifier": result.get("code_verifier", ""),
                "redirect_uri": result.get("redirect_uri", ""),
            }

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@agents.router.post("/subscriptions/poll")
async def subscriptions_poll(body: dict):
    """Poll for OAuth completion."""
    from backend.apps.nine_router import poll_oauth
    provider = body.get("provider", "")
    device_code = body.get("device_code", "")
    if not provider or not device_code:
        raise HTTPException(status_code=400, detail="provider and device_code required")

    try:
        result = await poll_oauth(
            provider, device_code,
            code_verifier=body.get("code_verifier"),
            extra_data=body.get("extra_data"),
        )
        if result.get("success"):
            from backend.apps.service.client import sync as _sync
            from backend.apps.settings.settings import load_settings
            _sync(load_settings().model_dump())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@agents.router.post("/subscriptions/exchange")
async def subscriptions_exchange(body: dict):
    """Exchange OAuth code for tokens via 9Router."""
    from backend.apps.nine_router import exchange_oauth
    provider = body.get("provider", "")
    code = body.get("code", "")
    redirect_uri = body.get("redirect_uri", "")
    code_verifier = body.get("code_verifier", "")
    state = body.get("state", "")

    if not provider or not code:
        raise HTTPException(status_code=400, detail="provider and code required")

    try:
        result = await exchange_oauth(provider, code, redirect_uri, code_verifier, state)
        if result.get("success"):
            from backend.apps.service.client import sync as _sync
            from backend.apps.settings.settings import load_settings
            _sync(load_settings().model_dump())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@agents.router.get("/subscriptions/models")
async def subscriptions_models():
    """List all models available through connected subscriptions."""
    from backend.apps.nine_router import is_running, get_models
    if not is_running():
        return {"models": []}
    models = await get_models()
    return {"models": models}


@agents.router.post("/probe-model")
async def probe_model(body: dict):
    """1-token health probe. Returns {ok, latency_ms} or {ok:false, error}
    or {ok:true, skipped:true} when the route's ambiguous (silent beats wrong)."""
    import time as _time
    short_name = (body or {}).get("model") or ""
    if not short_name:
        return {"ok": False, "error": "model required"}
    try:
        from backend.apps.agents.providers.registry import (
            resolve_model_id_for_sdk,
            get_api_type,
            _find_builtin_model,
        )
        from backend.apps.settings.settings import load_settings
        from backend.apps.nine_router import is_running as _9r_running
        settings = load_settings()
        api_type = get_api_type(short_name)
        resolved = resolve_model_id_for_sdk(short_name, settings)
        entry = _find_builtin_model(short_name) or {}
        route = entry.get("route")
        connection_mode = getattr(settings, "connection_mode", "own_key")

        import anthropic
        client = None

        # Routing mirrors agent_manager: prefix takes precedence over Pro.
        resolved_is_9router = (
            isinstance(resolved, str)
            and resolved.startswith(("cc/", "cx/", "gc/", "ag/", "openrouter/", "gemini/"))
        )

        if resolved_is_9router:
            if not _9r_running():
                return {"ok": True, "skipped": True}
            client = anthropic.AsyncAnthropic(api_key="9router", base_url="http://localhost:20128")
        elif route == "api" and api_type == "anthropic" and getattr(settings, "anthropic_api_key", None):
            client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        elif api_type == "anthropic" and connection_mode == "openswarm-pro":
            bearer = getattr(settings, "openswarm_bearer_token", "") or ""
            proxy_url = (getattr(settings, "openswarm_proxy_url", None) or "https://api.openswarm.com").rstrip("/")
            if not bearer:
                return {"ok": True, "skipped": True}
            client = anthropic.AsyncAnthropic(auth_token=bearer, base_url=proxy_url)
        elif api_type == "anthropic" and getattr(settings, "anthropic_api_key", None):
            client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        else:
            if not _9r_running():
                return {"ok": True, "skipped": True}
            client = anthropic.AsyncAnthropic(api_key="9router", base_url="http://localhost:20128")

        t0 = _time.monotonic()
        await client.messages.create(
            model=resolved,
            max_tokens=1,
            messages=[{"role": "user", "content": "ping"}],
            timeout=10.0,
        )
        return {"ok": True, "latency_ms": int((_time.monotonic() - t0) * 1000)}
    except Exception as e:
        msg = str(e).splitlines()[0] if str(e) else type(e).__name__
        low = msg.lower()
        # Suppress transients — chat will retry naturally and probe-time aliasing
        # 404s often differ from how the chat path resolves the same id.
        if any(s in low for s in (
            "timeout", "timed out",
            "connection reset", "connection aborted",
            "rate_limit", "rate limit", "429",
            "internal server error", "503", "502", "504",
            "reset after",
            "provider returned error",
            "404", "not_found", "not found",
        )):
            return {"ok": True, "skipped": True}
        return {"ok": False, "error": msg[:240]}


@agents.router.get("/models")
async def list_models():
    """Picker model list, grouped by provider, intersected with available creds."""
    from backend.apps.agents.providers.registry import BUILTIN_MODELS
    from backend.apps.nine_router import is_running as _9r_running, get_providers as _9r_providers
    from backend.apps.settings.settings import load_settings

    settings = load_settings()
    nine_router_up = _9r_running()

    connected: set[str] = set()
    if nine_router_up:
        try:
            conns = await _9r_providers()
            raw_providers = {c.get("provider", "") for c in conns if c.get("isActive") or c.get("testStatus") == "active"}
            # 9Router uses "claude"; our models use api="anthropic" — map across.
            _9R_TO_API = {
                "claude": "anthropic",
                "codex": "codex",
                "gemini-cli": "gemini-cli",
                "antigravity": "gemini-cli",  # AG = same Gemini models, separate OAuth.
            }
            connected = raw_providers | {_9R_TO_API.get(p, p) for p in raw_providers}
        except Exception as e:
            logger.debug(f"Failed to fetch 9Router providers: {e}")

    def _serialize(models: list[dict]) -> list[dict]:
        # Native models. Tiers describe the model itself; billing_kind
        # describes the user's wallet for it. Pricing is shown only for paid.
        from backend.apps.agents.providers.registry import (
            COST_PER_1M_TOKENS,
            compute_tiers,
            compute_billing_kind,
        )
        out = []
        for m in models:
            input_cost = output_cost = 0.0
            for (_p, _v), rates in COST_PER_1M_TOKENS.items():
                if _v == m["value"]:
                    input_cost, output_cost = rates
                    break
            api = m.get("api", "")
            route = m.get("route")
            billing_kind = compute_billing_kind(
                api=api, route=route, is_or_free=False, settings=settings,
            )
            tiers = compute_tiers(
                m.get("model_id", m["value"]),
                m["label"],
                output_cost,
                bool(m.get("reasoning", False)),
            )
            out.append({
                "value": m["value"],
                "label": m["label"],
                "context_window": m.get("context_window", 128_000),
                "reasoning": bool(m.get("reasoning", False)),
                "input_cost_per_1m": input_cost,
                "output_cost_per_1m": output_cost,
                # Strict — subscription doesn't count. Pickerside uses Subscription chip.
                "is_free": billing_kind == "free",
                "billing_kind": billing_kind,
                "tiers": list(tiers),
            })
        return out

    has_api_key = bool(getattr(settings, "anthropic_api_key", None))
    is_openswarm_pro = (
        getattr(settings, "connection_mode", "own_key") == "openswarm-pro"
        and bool(getattr(settings, "openswarm_bearer_token", None))
    )
    has_claude_sub = "claude" in connected

    result: dict[str, list[dict]] = {}

    def _ollama_label(model_name: str) -> str:
        clean = str(model_name or "").strip()
        display = clean.replace(":latest", "").replace("-", " ").replace("_", " ")
        return "Ollama " + " ".join(part.capitalize() for part in display.split())

    def _ollama_context_window(model_name: str) -> int:
        lower = str(model_name or "").lower()
        if "codellama" in lower:
            return 16_000
        if "qwen" in lower:
            return 128_000
        if "phi" in lower:
            return 16_000
        return 32_000

    def _ollama_reasoning(model_name: str) -> bool:
        lower = str(model_name or "").lower()
        return any(token in lower for token in ("qwen3", "qwen3.", "qwq", "deepseek-r1", "reason"))

    def _ollama_tiers(model_name: str) -> list[int]:
        lower = str(model_name or "").lower()
        if "qwen3" in lower or "qwen2.5-coder:32" in lower or "34b" in lower or "36" in lower:
            return [3, 3, 1]
        if "14b" in lower:
            return [2, 4, 1]
        return [2, 3, 1]

    def _ollama_metadata(item: dict) -> dict:
        details = item.get("details") if isinstance(item.get("details"), dict) else {}
        name = str(item.get("name") or item.get("model") or "").strip()
        return {
            "source": "ollama_api_tags",
            "name": name or None,
            "model": item.get("model") or name or None,
            "modified_at": item.get("modified_at"),
            "size": item.get("size"),
            "digest": item.get("digest"),
            "details": {
                "format": details.get("format"),
                "family": details.get("family"),
                "families": details.get("families"),
                "parameter_size": details.get("parameter_size"),
                "quantization_level": details.get("quantization_level"),
            },
        }

    async def _fetch_ollama_models() -> list[dict]:
        import httpx
        base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"{base_url}/api/tags")
                response.raise_for_status()
                data = response.json()
        except Exception as e:
            logger.debug(f"Ollama model fetch failed: {e}")
            return []
        models = []
        seen: set[str] = set()
        for item in data.get("models", []):
            name = str(item.get("name") or item.get("model") or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            metadata = _ollama_metadata(item)
            details = metadata["details"]
            models.append({
                "value": f"ollama/{name}",
                "label": _ollama_label(name),
                "provider": "Ollama Local",
                # Compatibility fields for existing UI filters. These are
                # heuristics until OpenSwarm measures/declares them elsewhere.
                "context_window": _ollama_context_window(name),
                "reasoning": _ollama_reasoning(name),
                "context_window_source": "estimated",
                "reasoning_source": "estimated",
                "tiers_source": "estimated",
                "input_cost_per_1m": 0.0,
                "output_cost_per_1m": 0.0,
                "is_free": True,
                "billing_kind": "free",
                "tiers": _ollama_tiers(name),
                # Real local metadata from Ollama /api/tags, flattened for
                # picker ergonomics and preserved as a structured object.
                "local_metadata": metadata,
                "model_metadata": metadata,
                "metadata_source": "Ollama /api/tags",
                "name": metadata.get("name"),
                "model": metadata.get("model"),
                "local_model_name": name,
                "modified_at": metadata.get("modified_at"),
                "size_bytes": metadata.get("size"),
                "digest": metadata.get("digest"),
                "format": details.get("format"),
                "family": details.get("family"),
                "families": details.get("families"),
                "parameter_size": details.get("parameter_size"),
                "quantization_level": details.get("quantization_level"),
                "availability": "available",
                "availability_source": "Ollama /api/tags",
                "runtime_metrics": None,
                "eval_results": None,
            })
        return models


    anthropic_models = BUILTIN_MODELS.get("Anthropic", [])
    adaptive = [m for m in anthropic_models if m.get("route") not in ("cc", "api")]
    cc_variants = [m for m in anthropic_models if m.get("route") == "cc"]
    api_variants = [m for m in anthropic_models if m.get("route") == "api"]

    # Pro mode shows two groups (Pro proxy + Anthropic alternates via cc/api);
    # own-key mode collapses to one Anthropic group using adaptive routing.
    notes: list[dict] = []
    if is_openswarm_pro:
        result["OpenSwarm Pro"] = _serialize(adaptive)
        anth_alternates: list[dict] = []
        if has_claude_sub:
            anth_alternates += cc_variants
        if has_api_key:
            anth_alternates += api_variants
        if anth_alternates:
            result["Anthropic"] = _serialize(anth_alternates)
    elif has_api_key or has_claude_sub:
        result["Anthropic"] = _serialize(adaptive)

    has_openai_key = bool(getattr(settings, "openai_api_key", None))
    has_google_key = bool(getattr(settings, "google_api_key", None))
    has_openrouter_key = bool(getattr(settings, "openrouter_api_key", None))
    from backend.apps.agents.providers.registry import (
        COST_PER_1M_TOKENS as _CPM,
        compute_tiers as _ct_native,
        compute_billing_kind as _cbk_native,
    )
    for provider_name, models in BUILTIN_MODELS.items():
        if provider_name == "Anthropic":
            continue
        visible = []
        for m in models:
            api = m.get("api", "")
            route = m.get("route")
            if route == "api":
                if api == "openai" and not has_openai_key:
                    continue
                if api == "gemini" and not has_google_key:
                    continue
            elif m.get("subscription_only"):
                if not nine_router_up or api not in connected:
                    continue
            in_cost = out_cost = 0.0
            for (_p, _v), rates in _CPM.items():
                if _v == m["value"]:
                    in_cost, out_cost = rates
                    break
            billing_kind = _cbk_native(
                api=api, route=route, is_or_free=False, settings=settings,
            )
            tiers = _ct_native(
                m.get("model_id", m["value"]),
                m["label"],
                out_cost,
                bool(m.get("reasoning", False)),
            )
            visible.append({
                "value": m["value"],
                "label": m["label"],
                "context_window": m.get("context_window", 128_000),
                "reasoning": bool(m.get("reasoning", False)),
                "input_cost_per_1m": in_cost,
                "output_cost_per_1m": out_cost,
                "is_free": billing_kind == "free",
                "billing_kind": billing_kind,
                "tiers": list(tiers),
            })
        if visible:
            result[provider_name] = visible

    ollama_models = await _fetch_ollama_models()
    if ollama_models:
        result["Ollama Local"] = ollama_models

    # OR catalog fetched straight from openrouter.ai (independent of 9Router
    # boot state) so picker populates the moment a key lands.
    if has_openrouter_key:
        try:
            from backend.apps.agents.providers.registry import fetch_openrouter_models
            or_models = await fetch_openrouter_models(settings.openrouter_api_key)
        except Exception as e:
            logger.debug(f"OpenRouter catalog fetch failed: {e}")
            or_models = []
        if or_models:
            by_vendor: dict[str, list[dict]] = {}
            from backend.apps.agents.providers.registry import (
                compute_tiers as _ct,
                compute_billing_kind as _cbk,
            )
            for m in or_models:
                v = m.get("vendor") or "Other"
                in_cost = float(m.get("input_cost_per_1m", 0.0))
                out_cost = float(m.get("output_cost_per_1m", 0.0))
                is_free = bool(m.get("is_free", False))
                billing_kind = _cbk(
                    api="openrouter", route="openrouter", is_or_free=is_free,
                    settings=settings,
                )
                tiers = _ct(
                    m.get("model_id", m["value"]),
                    m["label"],
                    out_cost,
                    bool(m.get("reasoning", False)),
                )
                by_vendor.setdefault(v, []).append({
                    "value": m["value"],
                    "label": m["label"],
                    "context_window": m.get("context_window", 128_000),
                    "reasoning": bool(m.get("reasoning", False)),
                    "input_cost_per_1m": in_cost,
                    "output_cost_per_1m": out_cost,
                    "is_free": is_free,
                    "billing_kind": billing_kind,
                    "tiers": list(tiers),
                    "max_completion_tokens": m.get("max_completion_tokens"),
                })
            for vendor in sorted(by_vendor.keys()):
                pretty = (
                    vendor.replace("-", " ").replace("_", " ").title().replace("Ai", "AI")
                )
                entries = sorted(by_vendor[vendor], key=lambda x: x["label"].lower())
                result[f"OpenRouter · {pretty}"] = entries

    return {"models": result, "notes": notes}


@agents.router.post("/subscriptions/disconnect")
async def subscriptions_disconnect(body: dict):
    """Disconnect a subscription provider via 9Router."""
    import httpx
    provider = body.get("provider", "")
    if not provider:
        raise HTTPException(status_code=400, detail="provider required")

    try:
        from backend.apps.nine_router import NINE_ROUTER_API, get_providers
        connections = await get_providers()
        conn = next((c for c in connections if c.get("provider") == provider), None)
        if conn and conn.get("id"):
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.delete(f"{NINE_ROUTER_API}/providers/{conn['id']}")
            from backend.apps.service.client import sync as _sync
            from backend.apps.settings.settings import load_settings
            _sync(load_settings().model_dump())
            return {"ok": True}
        return {"ok": False, "error": "Connection not found"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

