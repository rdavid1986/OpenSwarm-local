"""Swarm API endpoints.

Thin REST surface over the non-executing SwarmOrchestrator state. This is
intentionally state-only for now: it exposes plans/contracts/messages/artifacts
without launching AgentManager sessions yet.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel

from backend.config.Apps import SubApp
from backend.apps.agents.orchestration.executor import swarm_mvp_executor
from backend.apps.agents.orchestration.orchestrator import swarm_orchestrator
from backend.apps.agents.runtime.experimental_mini_runtime import (
    ExperimentalMiniRuntimeRequest,
    experimental_mini_runtime_enabled,
    experimental_mini_runtime_service,
)
from backend.apps.agents.runtime.experimental_dag_task_runner import (
    ExperimentalDAGTaskRunRequest,
    experimental_dag_task_runner,
    experimental_dag_task_runtime_enabled,
)
from backend.apps.agents.runtime.experimental_dag_chain_runner import (
    ExperimentalWorkerReviewRunRequest,
    experimental_dag_chain_runner,
    experimental_dag_chain_runtime_enabled,
)
from backend.apps.agents.runtime.experimental_dag_consolidator import (
    ExperimentalConsolidateFinalRequest,
    experimental_dag_consolidator,
    experimental_dag_consolidate_runtime_enabled,
)
from backend.apps.agents.runtime.experimental_dag_mini_runner import (
    ExperimentalMiniDAGRunRequest,
    experimental_dag_mini_runner,
    experimental_dag_mini_runner_enabled,
)
from backend.apps.agents.runtime.experimental_dag_dependency_runner import (
    ExperimentalDAGDependencyRunRequest,
    experimental_dag_dependency_runner,
    experimental_dag_dependency_runner_enabled,
)
from backend.apps.agents.runtime.approvals import approval_runtime
from backend.apps.agents.runtime.events import event_trace_runtime
from backend.apps.agents.orchestration.models import AgentToAgentMessage
from backend.apps.agents.providers.ollama_adapter import OllamaAdapter
from backend.apps.agents.runtime.provider import ProviderTurnContext


@asynccontextmanager
async def swarms_lifespan():
    swarm_orchestrator.store.root.mkdir(parents=True, exist_ok=True)
    yield


swarms = SubApp("swarms", swarms_lifespan)


class CreateSwarmRequest(BaseModel):
    user_prompt: str = "Experimental swarm"
    dashboard_id: str | None = None
    workspace_path: str | None = None


class RunMVPRequest(BaseModel):
    workspace_path: str | None = None


class SubmitArtifactRequest(BaseModel):
    from_agent_id: str
    task_id: str
    artifact: dict[str, Any]


class RequestReviewRequest(BaseModel):
    from_agent_id: str
    to_agent_id: str
    task_id: str
    artifact_refs: list[str] = []


class ExperimentalApprovalDecisionRequest(BaseModel):
    message: str | None = None
    updated_input: dict[str, Any] | None = None


class ExperimentalChatRequest(BaseModel):
    message: str
    model: str = "qwen2.5-coder:14b"


class OrchestrationNodePositionRequest(BaseModel):
    node_id: str
    x: float | None = None
    y: float | None = None
    expanded: bool | None = None


def _dump(swarm):
    return swarm.model_dump(mode="json")


def _load_or_404(swarm_id: str):
    try:
        return swarm_orchestrator.store.load(swarm_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Swarm not found")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid swarm_id")


def _openswarm_short_identity() -> str:
    return (
        "Soy el chat principal de OpenSwarm: un orquestador local-first para coordinar agentes de IA, "
        "tareas, tools, approvals y artifacts dentro del dashboard."
    )


def _openswarm_app_explanation() -> str:
    return (
        "OpenSwarm es una aplicación local-first para coordinar agentes de IA en tu propia máquina usando modelos locales como Ollama. "
        "Funciona como un espacio de trabajo visual: cada dashboard puede tener su SwarmCard, que actúa como el chat principal del orquestador. "
        "Desde ahí podés hacer preguntas normales o pedir tareas grandes. Cuando la tarea lo requiere, el swarm puede dividir el trabajo en pasos, "
        "asignarlo a agentes, usar herramientas controladas, pedir approvals y mostrar artifacts o resultados dentro del canvas.\n\n"
        "La idea no es solo chatear: es ver qué está haciendo el sistema, qué tareas existen, qué herramientas se usaron, qué approvals faltan "
        "y cuál fue el resultado final. El panel derecho de la SwarmCard muestra esa información de forma opcional: Tasks, Approvals, Artifacts, "
        "Recent activity y Final result.\n\n"
        "En resumen: OpenSwarm busca funcionar como un Copilot Chat local-first con agentes, herramientas y control humano, manteniendo el trabajo "
        "en tu computadora siempre que sea posible."
    )


def _is_app_question(user_message: str) -> bool:
    normalized = (user_message or "").strip().lower()
    return (
        "como funciona esta app" in normalized
        or "cómo funciona esta app" in normalized
        or "que es esta app" in normalized
        or "qué es esta app" in normalized
        or "que hace esta app" in normalized
        or "qué hace esta app" in normalized
        or "para que sirve esta app" in normalized
        or "para qué sirve esta app" in normalized
        or "que hace openswarm" in normalized
        or "qué hace openswarm" in normalized
        or "que es openswarm" in normalized
        or "qué es openswarm" in normalized
        or "como funciona openswarm" in normalized
        or "cómo funciona openswarm" in normalized
        or "para que sirve openswarm" in normalized
        or "para qué sirve openswarm" in normalized
    )


def _normalize_question_text(user_message: str) -> str:
    return (user_message or "").strip().lower()


def _classify_chat_question(user_message: str) -> str:
    normalized = _normalize_question_text(user_message)

    if _is_app_question(user_message):
        return "app_identity"

    asks_short_identity = (
        "que sos" in normalized
        or "qué sos" in normalized
        or "quien sos" in normalized
        or "quién sos" in normalized
        or "que eres" in normalized
        or "qué eres" in normalized
    )

    if asks_short_identity:
        return "app_short_identity"

    app_terms = (
        "openswarm",
        "esta app",
        "la app",
        "swarm",
        "swarmcard",
        "dashboard",
        "agente",
        "agentes",
        "tool",
        "tools",
        "artifact",
        "artifacts",
        "task",
        "tarea",
        "tareas",
    )

    asks_capability = (
        "puede" in normalized
        or "podria" in normalized
        or "podría" in normalized
        or "sirve para" in normalized
        or "es capaz" in normalized
        or "hacer una app" in normalized
        or "crear una app" in normalized
        or "hacerme una app" in normalized
        or "crear proyecto" in normalized
        or "programar" in normalized
    )

    asks_state = (
        "que estamos haciendo" in normalized
        or "qué estamos haciendo" in normalized
        or "en que estamos" in normalized
        or "en qué estamos" in normalized
        or "donde estamos" in normalized
        or "dónde estamos" in normalized
        or "estado actual" in normalized
        or "que hicimos" in normalized
        or "qué hicimos" in normalized
        or "que falta" in normalized
        or "qué falta" in normalized
    )

    if asks_capability and any(term in normalized for term in app_terms):
        return "app_capability"

    if asks_state and any(term in normalized for term in app_terms):
        return "dashboard_state"

    if asks_state:
        return "dashboard_state"

    asks_memory = (
        "que hablamos" in normalized
        or "qué hablamos" in normalized
        or "memoria" in normalized
        or "recordas" in normalized
        or "recordás" in normalized
        or "historial" in normalized
        or "mensajes" in normalized
        or "mensaje" in normalized
        or "primer mensaje" in normalized
        or "primero que dije" in normalized
        or "primero que te dije" in normalized
        or "que te dije primero" in normalized
        or "qué te dije primero" in normalized
        or "ultimo mensaje" in normalized
        or "último mensaje" in normalized
        or "ultimo que dije" in normalized
        or "último que dije" in normalized
        or "eso no paso asi" in normalized
        or "eso no pasó así" in normalized
        or "no paso asi" in normalized
        or "no pasó así" in normalized
        or "eso no fue asi" in normalized
        or "eso no fue así" in normalized
        or "inventaste" in normalized
        or "lo inventaste" in normalized
        or "no inventes" in normalized
        or "conversacion" in normalized
        or "conversación" in normalized
    )

    asks_artifacts = (
        "artifact" in normalized
        or "artifacts" in normalized
        or "artefacto" in normalized
        or "artefactos" in normalized
        or "resultado generado" in normalized
        or "archivos generados" in normalized
    )

    asks_tasks = (
        "tasks" in normalized
        or "tareas" in normalized
        or "task" in normalized
        or "estado de tareas" in normalized
        or "tareas pendientes" in normalized
        or "tareas completadas" in normalized
        or "que tareas" in normalized
        or "qué tareas" in normalized
    )

    asks_implementation = (
        "haceme una app" in normalized
        or "hacer una app" in normalized
        or "hagamos una app" in normalized
        or "armemos una app" in normalized
        or "haceme una web" in normalized
        or "hacer una web" in normalized
        or "hagamos una web" in normalized
        or "armemos una web" in normalized
        or "implementa" in normalized
        or "implementá" in normalized
        or "empeza a construir" in normalized
        or "empezá a construir" in normalized
    )

    asks_planning = (
        "plan" in normalized
        or "roadmap" in normalized
        or "pasos" in normalized
        or "fases" in normalized
        or "arquitectura" in normalized
        or "diseñemos" in normalized
        or "diseñar" in normalized
    )

    asks_debug = (
        "error" in normalized
        or "bug" in normalized
        or "fallo" in normalized
        or "rompio" in normalized
        or "rompió" in normalized
        or "no funciona" in normalized
        or "corregi" in normalized
        or "corregí" in normalized
        or "arregla" in normalized
        or "arreglá" in normalized
    )

    asks_tool = (
        "usa la tool" in normalized
        or "usá la tool" in normalized
        or "usar tool" in normalized
        or "ejecuta la tool" in normalized
        or "ejecutá la tool" in normalized
        or "run_command" in normalized
        or "read_file" in normalized
        or "write_file" in normalized
        or "search_files" in normalized
        or "search_text" in normalized
        or "inspect_project" in normalized
    )

    asks_project_status = (
        "estado del proyecto" in normalized
        or "como va el proyecto" in normalized
        or "cómo va el proyecto" in normalized
        or "que falta del proyecto" in normalized
        or "qué falta del proyecto" in normalized
        or "avance del proyecto" in normalized
    )

    asks_dashboard_help = (
        "dashboard" in normalized
        and (
            "ayuda" in normalized
            or "como uso" in normalized
            or "cómo uso" in normalized
            or "para que sirve" in normalized
            or "para qué sirve" in normalized
        )
    )

    asks_agent_help = (
        ("agente" in normalized or "agentes" in normalized)
        and (
            "ayuda" in normalized
            or "como funcionan" in normalized
            or "cómo funcionan" in normalized
            or "que hacen" in normalized
            or "qué hacen" in normalized
            or "para que sirven" in normalized
            or "para qué sirven" in normalized
        )
    )

    asks_web_research = (
        "busca en internet" in normalized
        or "buscá en internet" in normalized
        or "buscar en internet" in normalized
        or "navega por internet" in normalized
        or "navegá por internet" in normalized
        or "investiga online" in normalized
        or "investigá online" in normalized
        or "web research" in normalized
    )

    if asks_memory:
        return "swarm_memory"

    if asks_artifacts:
        return "artifact_query"

    if asks_tasks:
        return "task_status"

    if asks_project_status:
        return "project_status"

    if asks_dashboard_help:
        return "dashboard_help"

    if asks_agent_help:
        return "agent_help"

    if asks_web_research:
        return "web_research_request"

    if asks_tool:
        return "tool_request"

    if asks_debug:
        return "debug_request"

    if asks_implementation:
        return "implementation_request"

    if asks_planning:
        return "planning_request"

    if asks_capability:
        return "app_capability"

    return "normal_chat"


def _implementation_request_explanation() -> str:
    return (
        "Puedo ayudarte a convertir ese pedido en un flujo de implementación, pero no voy a ejecutar cambios desde el chat simple. "
        "La forma correcta es iniciar un flujo task/DAG: primero se aclara el objetivo, después se arma un plan, se muestran tareas/agentes "
        "y recién con confirmación se ejecutan tools reales con evidencia."
    )


def _planning_request_explanation() -> str:
    return (
        "Puedo ayudarte a planificarlo. Para mantener control y evidencia, el plan debe quedar separado de la ejecución: alcance, fases, archivos probables, "
        "riesgos, validaciones y criterios de cierre. La ejecución real debe pasar por task/DAG si requiere modificar archivos o correr tools."
    )


def _debug_request_explanation() -> str:
    return (
        "Puedo ayudarte a depurar, pero no debo afirmar correcciones sin inspección ni evidencia. El flujo correcto es: leer el error, identificar archivos relevantes, "
        "inspeccionar la zona exacta, aplicar un patch mínimo y validar con comandos o tests."
    )


def _tool_request_explanation() -> str:
    return (
        "Las tools reales no deben ejecutarse desde una respuesta conversacional simple. Si el usuario pide usar read_file, write_file, search_files, run_command "
        "u otra tool, el pedido debe entrar por un flujo task/DAG con eventos, permisos y evidencia."
    )


def _project_status_explanation() -> str:
    return (
        "El estado del proyecto debe calcularse desde datos reales del dashboard, tareas, artifacts, eventos y memoria del swarm. "
        "Si falta evidencia local, OpenSwarm debe decirlo en lugar de inventar progreso."
    )


def _dashboard_help_explanation() -> str:
    return (
        "Un dashboard es el espacio visual donde vive el trabajo de un proyecto o flujo. Puede contener SwarmCard, PlansCard, BrowserCard y otros paneles. "
        "La SwarmCard actúa como chat principal del orquestador; los paneles laterales muestran tareas, approvals, artifacts, eventos y resultado final."
    )


def _agent_help_explanation() -> str:
    return (
        "Los agentes son roles especializados coordinados por el swarm. No deben inventar acciones: cada tarea importante debe producir eventos, artifacts "
        "o evidencia verificable. El orquestador decide cuándo planificar, cuándo delegar y cuándo pedir aprobación."
    )


def _web_research_request_explanation() -> str:
    return (
        "La investigación web debe ejecutarse mediante una tool controlada y registrar fuentes, fechas y evidencia. "
        "Desde el chat simple solo puedo clasificar el pedido; no debo fingir navegación ni citar fuentes que no fueron consultadas."
    )


def _openswarm_capability_explanation() -> str:
    return (
        "Sí, OpenSwarm está pensado para ayudarte a construir una app, pero no debe prometer trabajo que no ejecutó.\n\n"
        "La forma correcta no es tratarlo como un chat común, sino como un orquestador: primero entiende el pedido, después lo divide en tareas, "
        "asigna agentes, usa herramientas controladas, registra eventos, genera artifacts y muestra el resultado dentro del dashboard.\n\n"
        "Estado actual: el chat simple ya funciona separado del DAG, la SwarmCard está aislada por dashboard y el fast-path evita varias alucinaciones. "
        "Lo que todavía falta fortalecer es el router de contexto, la revisión de calidad, las tools reales del swarm, los agentes especializados y la capa "
        "de evidencia para que nunca diga que hizo algo sin haberlo ejecutado realmente."
    )


def _current_swarm_state_explanation(swarm) -> str:
    messages = getattr(swarm, "messages", []) or []
    artifacts = getattr(swarm, "artifacts", []) or []
    intent = getattr(swarm, "intent", "unknown")

    user_message_count = 0
    assistant_message_count = 0
    for message in messages:
        payload = getattr(message, "payload", {}) or {}
        role = payload.get("role") if isinstance(payload, dict) else None
        if role == "user":
            user_message_count += 1
        elif role == "assistant":
            assistant_message_count += 1

    lines = [
        "Estamos trabajando dentro del swarm activo de este dashboard.",
        "",
        f"Estado visible del swarm:",
        f"- Intent actual: {intent}.",
        f"- Mensajes del usuario registrados: {user_message_count}.",
        f"- Respuestas previas del asistente registradas: {assistant_message_count}.",
        f"- Artifacts registrados: {len(artifacts)}.",
    ]

    lines.extend(
        [
            "",
            "A nivel de implementación, el objetivo inmediato es mejorar el router de preguntas para que OpenSwarm distinga entre identidad de la app, "
            "capacidades, estado del dashboard, memoria del swarm, artifacts, estado de tareas, chat normal y tareas ejecutables. Esto evita que el modelo "
            "invente funciones o responda como si fuera otra aplicación.",
        ]
    )

    return "\n".join(lines)




def _shorten_memory_content(content: str, max_chars: int = 280) -> str:
    compact = " ".join((content or "").split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3].rstrip() + "..."


def _swarm_memory_explanation(swarm, user_message: str = "") -> str:
    normalized = _normalize_question_text(user_message)
    messages = getattr(swarm, "messages", []) or []
    previous_messages = messages[:-1] if messages else []

    user_messages: list[str] = []
    assistant_count = 0

    for message in previous_messages:
        payload = getattr(message, "payload", {}) or {}
        if not isinstance(payload, dict):
            continue

        role = str(payload.get("role") or "").strip()
        content = str(payload.get("content") or "").strip()
        if not role or not content:
            continue

        if role == "user":
            user_messages.append(content)
        elif role == "assistant":
            assistant_count += 1

    if not user_messages and assistant_count == 0:
        return "Este swarm todavía no tiene mensajes previos registrados."

    asks_first = (
        "primer mensaje" in normalized
        or "primero que dije" in normalized
        or "primero que te dije" in normalized
        or "que te dije primero" in normalized
        or "qué te dije primero" in normalized
    )

    asks_last = (
        "ultimo mensaje" in normalized
        or "último mensaje" in normalized
        or "ultimo que dije" in normalized
        or "último que dije" in normalized
    )

    if asks_first:
        if not user_messages:
            return "No hay mensajes previos del usuario registrados en este swarm."
        return f"El primer mensaje registrado del usuario en este swarm fue:\n\n{user_messages[0]}"

    is_correction = (
        "eso no paso asi" in normalized
        or "eso no pasó así" in normalized
        or "no paso asi" in normalized
        or "no pasó así" in normalized
        or "eso no fue asi" in normalized
        or "eso no fue así" in normalized
        or "inventaste" in normalized
        or "lo inventaste" in normalized
        or "no inventes" in normalized
    )

    if asks_last:
        if not user_messages:
            return "No hay mensajes previos del usuario registrados en este swarm."
        return f"El último mensaje previo registrado del usuario en este swarm fue:\n\n{user_messages[-1]}"

    if is_correction:
        lines = [
            "Tenés razón: no debo inventar mensajes ni asumir historial.",
            "",
            "Lo que puedo verificar en este swarm es:",
            f"- Mensajes previos del usuario: {len(user_messages)}.",
            f"- Respuestas previas del swarm: {assistant_count}.",
        ]
        if user_messages:
            lines.append("")
            lines.append("Primer mensaje registrado del usuario:")
            lines.append(user_messages[0])
        return "\n".join(lines)

    lines = [
        "Memoria reciente previa del swarm activo:",
        "",
        f"- Mensajes previos del usuario: {len(user_messages)}.",
        f"- Respuestas previas del swarm: {assistant_count}.",
    ]

    if user_messages:
        lines.append("")
        lines.append("Últimos pedidos del usuario:")
        for content in user_messages[-6:]:
            lines.append(f"- {_shorten_memory_content(content, 160)}")

    return "\n".join(lines)


def _artifact_query_explanation(swarm) -> str:
    artifacts = getattr(swarm, "artifacts", []) or []

    if not artifacts:
        return "Este swarm no tiene artifacts registrados todavía."

    lines = ["Artifacts registrados en el swarm activo:"]
    for index, artifact in enumerate(artifacts, start=1):
        if isinstance(artifact, dict):
            artifact_type = artifact.get("type") or artifact.get("kind") or "artifact"
            artifact_title = artifact.get("title") or artifact.get("name") or artifact.get("id") or f"artifact {index}"
            lines.append(f"- {artifact_title} ({artifact_type})")
        else:
            lines.append(f"- artifact {index}")

    return "\n".join(lines)


def _task_status_explanation(swarm) -> str:
    tasks = getattr(swarm, "tasks", []) or []

    if not tasks:
        return (
            "Este swarm no tiene tareas registradas todavía.\n\n"
            "Si el pedido es una tarea ejecutable, debe entrar por el flujo de task/DAG, no por chat simple."
        )

    status_counts: dict[str, int] = {}
    lines = ["Tareas registradas en el swarm activo:"]

    for task in tasks:
        status = str(getattr(task, "status", "unknown") or "unknown")
        title = str(getattr(task, "title", "") or getattr(task, "name", "") or getattr(task, "id", "task"))
        status_counts[status] = status_counts.get(status, 0) + 1
        lines.append(f"- {title}: {status}")

    lines.insert(1, "Resumen: " + ", ".join(f"{status}={count}" for status, count in sorted(status_counts.items())))

    return "\n".join(lines)




def _has_swarm_user_messages(swarm) -> bool:
    messages = getattr(swarm, "messages", []) or []
    for message in messages:
        payload = getattr(message, "payload", {}) or {}
        if isinstance(payload, dict) and payload.get("role") == "user" and str(payload.get("content") or "").strip():
            return True
    return False


def _looks_like_json_only_response(content: str) -> bool:
    text = (content or "").strip()
    if not text:
        return False

    fenced = text
    if fenced.startswith("```") and fenced.endswith("```"):
        lines = fenced.splitlines()
        if len(lines) >= 3:
            fenced = "\n".join(lines[1:-1]).strip()

    return (
        (text.startswith("{") and text.endswith("}"))
        or (text.startswith("[") and text.endswith("]"))
        or (fenced.startswith("{") and fenced.endswith("}"))
        or (fenced.startswith("[") and fenced.endswith("]"))
    )


def _answer_quality_guard_result(content: str, user_message: str, swarm) -> tuple[str, str | None]:
    text = (content or "").strip()
    normalized = text.lower()
    normalized_user = _normalize_question_text(user_message)

    if not text:
        return "No se generó una respuesta útil.", "empty_response"

    if _looks_like_json_only_response(text):
        return "El modelo devolvió una respuesta estructurada no útil. Necesito responder en texto claro.", "json_only_response"

    has_messages = _has_swarm_user_messages(swarm)

    denies_memory_access = (
        "no tengo acceso a los mensajes" in normalized
        or "no tengo acceso al historial" in normalized
        or "no puedo acceder al historial" in normalized
        or "no puedo recordar" in normalized
        or "no puedo recuperar información" in normalized
        or "no tengo memoria" in normalized
    )

    memory_related_user_message = (
        "mensaje" in normalized_user
        or "mensajes" in normalized_user
        or "historial" in normalized_user
        or "memoria" in normalized_user
        or "record" in normalized_user
        or "que dije" in normalized_user
        or "qué dije" in normalized_user
        or "que hablamos" in normalized_user
        or "qué hablamos" in normalized_user
    )

    if has_messages and denies_memory_access and memory_related_user_message:
        return _swarm_memory_explanation(swarm, user_message), "denied_available_memory"

    forbidden_app_descriptions = (
        "red mesh",
        "peer-to-peer",
        "p2p",
        "mensajería descentralizada",
        "mensajeria descentralizada",
        "red social",
        "chat offline entre usuarios",
    )

    if any(term in normalized for term in forbidden_app_descriptions):
        return _openswarm_app_explanation(), "false_app_description"

    evasive_patterns = (
        "no puedo ayudarte con eso",
        "no puedo proporcionar esa información",
        "necesito más contexto",
        "podrías proporcionar más contexto",
        "podrias proporcionar mas contexto",
        "no tengo suficiente información",
        "no tengo suficiente informacion",
    )

    local_context_should_answer = (
        "openswarm" in normalized_user
        or "esta app" in normalized_user
        or "que sos" in normalized_user
        or "qué sos" in normalized_user
        or "que puede hacer" in normalized_user
        or "qué puede hacer" in normalized_user
        or memory_related_user_message
    )

    if local_context_should_answer and any(pattern in normalized for pattern in evasive_patterns):
        route = _classify_chat_question(user_message)
        controlled = _controlled_chat_response(route, user_message, swarm)
        if controlled:
            return controlled, "evasive_despite_local_context"

    action_terms = (
        "crear",
        "creaste",
        "creado",
        "cree",
        "creé",
        "archivo",
        "modificar",
        "modificaste",
        "modificado",
        "ejecutar",
        "ejecutaste",
        "ejecutado",
        "comando",
        "tool",
        "tools",
        "tarea",
        "task",
    )

    user_requests_unverified_action_claim = (
        ("decime que" in normalized_user or "di que" in normalized_user or "dime que" in normalized_user)
        and any(term in normalized_user for term in action_terms)
    )

    action_claims = (
        "he creado",
        "creé",
        "cree el archivo",
        "creé el archivo",
        "he modificado",
        "modifiqué",
        "ejecuté",
        "he ejecutado",
        "corrí el comando",
        "he corrido",
        "ya creé",
        "ya cree",
        "ya ejecuté",
        "ya modifiqué",
    )

    if user_requests_unverified_action_claim or any(claim in normalized for claim in action_claims):
        return (
            "No puedo afirmar que ejecuté acciones reales desde este chat si no hay eventos o evidencia de tools. "
            "Para ejecutar una tarea real, el pedido debe entrar por el flujo task/DAG con tools registradas."
        ), "unverified_action_claim"

    return text, None


def _answer_quality_guard(content: str, user_message: str, swarm) -> str:
    guarded_content, _reason = _answer_quality_guard_result(content, user_message, swarm)
    return guarded_content

def _build_working_memory(swarm, route: str) -> list[str]:
    messages = getattr(swarm, "messages", []) or []
    artifacts = getattr(swarm, "artifacts", []) or []
    tasks = getattr(swarm, "tasks", []) or []
    events = getattr(swarm, "events", []) or []
    intent = getattr(swarm, "intent", "unknown")
    dashboard_id = getattr(swarm, "dashboard_id", None) or "unknown"

    return [
        "[working_memory]",
        "Estado operativo real del swarm activo:",
        f"- dashboard_id: {dashboard_id}",
        f"- swarm_intent: {intent}",
        f"- route: {route}",
        f"- messages_count: {len(messages)}",
        f"- tasks_count: {len(tasks)}",
        f"- artifacts_count: {len(artifacts)}",
        f"- persisted_events_count: {len(events)}",
        "",
    ]


def _build_semantic_memory() -> list[str]:
    return [
        "[semantic_memory]",
        "Hechos estables sobre OpenSwarm:",
        "- OpenSwarm es una aplicación local-first para coordinar agentes de IA en la máquina del usuario.",
        "- Usa dashboards visuales, SwarmCard, tareas, tools controladas, approvals, artifacts y resultados visibles.",
        "- El objetivo es funcionar como un Copilot Chat local-first con orquestación de agentes y control humano.",
        "- El chat simple está separado del flujo DAG/task.",
        "- Algunas preguntas se responden desde backend con contexto local controlado.",
        "- Preguntas sobre identidad, capacidad, estado, memoria, artifacts y tareas no deben depender de memoria inventada del modelo.",
        "- Si una tarea requiere ejecutar acciones, debe entrar por el flujo task/DAG, no por chat simple.",
        "",
    ]


def _build_procedural_memory() -> list[str]:
    return [
        "[procedural_memory]",
        "Reglas obligatorias de respuesta:",
        "- Respondé en el mismo idioma del usuario.",
        "- Respondé claro y breve.",
        "- Usá el contexto local como fuente de verdad.",
        "- No afirmes que ejecutaste tools, comandos, archivos o tareas si no hay evidencia real.",
        "- No inventes historial de conversación.",
        "- No inventes artifacts, tareas, approvals ni estado del dashboard.",
        "- Si falta evidencia local, decí que no hay suficiente información verificable.",
        "- No describas OpenSwarm como app de mensajería, red social, red mesh o peer-to-peer si el usuario no lo pidió.",
        "- Si el usuario pide una tarea ejecutable, explicá que debe iniciarse como task swarm.",
        "- No devuelvas JSON salvo que el usuario lo pida explícitamente.",
        "",
    ]


def _collect_recent_chat_memory(swarm) -> tuple[list[str], list[str]]:
    messages = getattr(swarm, "messages", []) or []
    recent_user_messages: list[str] = []
    recent_assistant_messages: list[str] = []

    # Se excluye el último mensaje porque normalmente es la pregunta actual recién guardada.
    previous_messages = messages[:-1] if messages else []

    for message in previous_messages[-12:]:
        payload = getattr(message, "payload", {}) or {}
        if not isinstance(payload, dict):
            continue

        role = str(payload.get("role") or "").strip()
        content = str(payload.get("content") or "").strip()
        if not role or not content:
            continue

        if role == "user":
            recent_user_messages.append(_shorten_memory_content(content, 220))
        elif role == "assistant":
            recent_assistant_messages.append(_shorten_memory_content(content, 220))

    return recent_user_messages, recent_assistant_messages


def _build_episodic_memory(swarm) -> list[str]:
    recent_user_messages, recent_assistant_messages = _collect_recent_chat_memory(swarm)
    context_lines = [
        "[episodic_memory]",
        "Memoria conversacional reciente del swarm activo:",
    ]

    if recent_user_messages:
        context_lines.append("- últimos mensajes previos del usuario:")
        for item in recent_user_messages[-6:]:
            context_lines.append(f"  - {item}")
    else:
        context_lines.append("- últimos mensajes previos del usuario: ninguno registrado.")

    if recent_assistant_messages:
        context_lines.append("- Últimas respuestas previas del swarm resumidas:")
        for item in recent_assistant_messages[-4:]:
            context_lines.append(f"  - {item}")
    else:
        context_lines.append("- Últimas respuestas previas del swarm: ninguna registrada.")

    return context_lines


def _build_current_input(user_message: str) -> list[str]:
    return [
        "",
        "[current_input]",
        "Mensaje actual del usuario:",
        user_message,
    ]


def _build_local_chat_context(swarm, user_message: str, route: str) -> str:
    context_lines = [
        "CONTEXTO LOCAL DE OPENSWARM",
        "Formato: memoria tipada estilo mini-Engram.",
        "",
    ]
    context_lines.extend(_build_working_memory(swarm, route))
    context_lines.extend(_build_semantic_memory())
    context_lines.extend(_build_procedural_memory())
    context_lines.extend(_build_episodic_memory(swarm))
    context_lines.extend(_build_current_input(user_message))

    return "\n".join(context_lines)


def _project_intake_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _project_intake_questions() -> list[dict[str, Any]]:
    custom = {"label": "Otra opción / escribir respuesta personalizada", "value": "__custom__"}

    def q(question_id: str, title: str, prompt: str, options: list[str]) -> dict[str, Any]:
        return {
            "id": question_id,
            "title": title,
            "prompt": prompt,
            "options": [{"label": option, "value": option} for option in options] + [custom],
        }

    return [
        q("app_type", "Tipo de app/web", "¿Qué tipo de app querés construir?", ["Web app", "Landing + formulario", "Dashboard interno", "E-commerce", "SaaS"]),
        q("main_goal", "Objetivo principal", "¿Cuál es el objetivo principal del producto?", ["Gestionar operaciones", "Vender online", "Capturar leads", "Automatizar un proceso", "Mostrar información"]),
        q("target_users", "Usuarios objetivo", "¿Quiénes van a usarla principalmente?", ["Clientes finales", "Equipo interno", "Administradores", "Vendedores", "Usuarios públicos"]),
        q("frontend", "Frontend deseado", "¿Qué frontend preferís para el MVP?", ["React", "Next.js", "Vite + React", "HTML/CSS simple", "No tengo preferencia"]),
        q("backend", "Backend deseado", "¿Qué backend preferís?", ["FastAPI", "Node/Express", "Next.js API routes", "Sin backend por ahora", "No tengo preferencia"]),
        q("database", "Persistencia/base de datos", "¿Qué persistencia necesitás?", ["PostgreSQL", "SQLite", "Supabase", "Archivos JSON", "No necesita base por ahora"]),
        q("auth", "Autenticación", "¿Necesita login o roles?", ["Sin login", "Login simple", "Admin + usuarios", "OAuth/Google", "No sé todavía"]),
        q("payments", "Pagos", "¿Necesita pagos en el MVP?", ["No", "Stripe", "Mercado Pago", "Solo registrar pagos manuales", "Más adelante"]),
        q("deploy", "Deploy", "¿Dónde imaginás deployarlo?", ["Local primero", "Vercel", "Docker/VPS", "Render/Fly.io", "No definido"]),
        q("visual_style", "Estilo visual", "¿Qué estilo visual buscás?", ["Minimalista", "Corporativo", "Moderno/SaaS", "Colorido", "Inspirado en una marca existente"]),
        q("mvp_priority", "Prioridad MVP", "¿Qué debe estar sí o sí en el primer MVP?", ["Formulario principal", "Dashboard", "CRUD básico", "Reportes", "Flujo completo end-to-end"]),
        q("technical_constraints", "Restricciones técnicas", "¿Hay restricciones técnicas importantes?", ["Usar stack existente", "Sin servicios pagos", "Funcionar offline/local", "Código simple de mantener", "No hay restricciones"]),
        q("out_of_scope", "Fuera del MVP", "¿Qué debería quedar fuera del MVP inicial?", ["Pagos", "Autenticación avanzada", "Diseño final pulido", "Integraciones externas", "Mobile app nativa"]),
    ]


def _get_project_intake_state(swarm) -> dict[str, Any]:
    state = getattr(swarm, "project_intake_state", {}) or {}
    return state if isinstance(state, dict) else {}


def _project_intake_question_by_id(question_id: str | None) -> dict[str, Any] | None:
    for question in _project_intake_questions():
        if question["id"] == question_id:
            return question
    return None


def _next_project_intake_question_id(answers: dict[str, Any]) -> str | None:
    for question in _project_intake_questions():
        if question["id"] not in answers:
            return str(question["id"])
    return None


def _project_intake_question_payload(state: dict[str, Any]) -> dict[str, Any]:
    question = _project_intake_question_by_id(str(state.get("current_question_id") or ""))
    if not question:
        return {}
    return {
        "project_intake_question": {
            "id": question["id"],
            "title": question["title"],
            "prompt": question["prompt"],
        },
        "project_intake_options": question["options"],
    }


def _start_project_intake(swarm, user_message: str) -> tuple[str, dict[str, Any]]:
    now = _project_intake_now()
    first_question_id = _project_intake_questions()[0]["id"]
    state = {
        "status": "collecting",
        "current_question_id": first_question_id,
        "answers": {},
        "generated_plan": None,
        "created_at": now,
        "updated_at": now,
        "original_request": user_message,
    }
    swarm.project_intake_state = state
    return _build_project_intake_message(state), {
        "route": "implementation_request",
        "project_intake_state": state,
        **_project_intake_question_payload(state),
    }


def _advance_project_intake(swarm, user_message: str) -> tuple[str, dict[str, Any]]:
    state = dict(_get_project_intake_state(swarm))
    answers = dict(state.get("answers") or {})
    current_question_id = str(state.get("current_question_id") or "")
    if current_question_id:
        answers[current_question_id] = user_message

    next_question_id = _next_project_intake_question_id(answers)
    state["answers"] = answers
    state["updated_at"] = _project_intake_now()

    if next_question_id:
        state["status"] = "collecting"
        state["current_question_id"] = next_question_id
        swarm.project_intake_state = state
        return _build_project_intake_message(state), {
            "route": "project_intake",
            "project_intake_state": state,
            **_project_intake_question_payload(state),
        }

    generated_plan = _build_project_intake_plan(state)
    state["status"] = "ready_to_implement"
    state["current_question_id"] = None
    state["generated_plan"] = generated_plan
    swarm.project_intake_state = state
    _ensure_orchestration_canvas_preview(swarm)
    return _build_project_intake_message(state), {
        "route": "project_plan_ready",
        "project_intake_state": state,
        "orchestration_canvas_state": getattr(swarm, "orchestration_canvas_state", {}),
        "project_intake_action": {
            "type": "start_implementation",
            "label": "Start Swarm Implementation",
            "enabled": experimental_dag_dependency_runner_enabled(),
            "reason": None if experimental_dag_dependency_runner_enabled() else "Implementation runner is not enabled. Start backend with OPENSWARM_EXPERIMENTAL_DAG_MINI_RUNNER=1 and OPENSWARM_EXPERIMENTAL_DAG_DEPENDENCY_RUNNER=1.",
        },
    }


def _build_project_intake_message(state: dict[str, Any]) -> str:
    status = str(state.get("status") or "collecting")
    if status == "ready_to_implement":
        plan = state.get("generated_plan") or {}
        lines = [
            "Listo: ya tengo información suficiente para un plan preliminar.",
            "",
            "Plan preliminar:",
            f"- Tipo: {plan.get('app_type', 'no definido')}",
            f"- Objetivo: {plan.get('main_goal', 'no definido')}",
            f"- Usuarios: {plan.get('target_users', 'no definido')}",
            f"- Stack sugerido: {plan.get('frontend', 'no definido')} + {plan.get('backend', 'no definido')} + {plan.get('database', 'no definido')}",
            f"- Autenticación: {plan.get('auth', 'no definido')}",
            f"- Pagos: {plan.get('payments', 'no definido')}",
            f"- Deploy: {plan.get('deploy', 'no definido')}",
            f"- Prioridad MVP: {plan.get('mvp_priority', 'no definido')}",
            f"- Fuera del MVP: {plan.get('out_of_scope', 'no definido')}",
            "",
            "El botón de implementación queda preparado y se habilita cuando el runner experimental está activo.",
        ]
        return "\n".join(lines)

    question = _project_intake_question_by_id(str(state.get("current_question_id") or ""))
    if not question:
        return "Necesito una respuesta más para continuar el intake del proyecto."

    answered_count = len(state.get("answers") or {})
    total = len(_project_intake_questions())
    return "\n".join([
        "Perfecto. Antes de implementar, voy a aclarar requisitos paso a paso.",
        "No voy a ejecutar tools ni crear archivos todavía.",
        "",
        f"Pregunta {answered_count + 1}/{total}: {question['prompt']}",
    ])


def _build_project_intake_plan(state: dict[str, Any]) -> dict[str, Any]:
    answers = dict(state.get("answers") or {})
    return {
        "summary": "Plan preliminar local generado desde el intake conversacional. No se ejecutaron tools ni se crearon artifacts.",
        "app_type": answers.get("app_type"),
        "main_goal": answers.get("main_goal"),
        "target_users": answers.get("target_users"),
        "frontend": answers.get("frontend"),
        "backend": answers.get("backend"),
        "database": answers.get("database"),
        "auth": answers.get("auth"),
        "payments": answers.get("payments"),
        "deploy": answers.get("deploy"),
        "visual_style": answers.get("visual_style"),
        "mvp_priority": answers.get("mvp_priority"),
        "technical_constraints": answers.get("technical_constraints"),
        "out_of_scope": answers.get("out_of_scope"),
    }


def _build_orchestration_canvas_nodes(plan: dict[str, Any]) -> list[dict[str, Any]]:
    plan_summary = str(plan.get("summary") or "Preview generated from project intake.")
    node_specs = [
        ("orchestrator", "Orchestrator", "Coordinator", "Coordinates the implementation flow and keeps scope aligned.", 40, 120),
        ("planner", "Planner", "Planning", "Turns the intake answers into an implementation breakdown.", 280, 120),
        ("frontend_planner", "Frontend Planner", "Frontend Planning", f"Plans UI for {plan.get('frontend') or 'the selected frontend'}.", 520, 20),
        ("backend_planner", "Backend Planner", "Backend Planning", f"Plans services and persistence for {plan.get('backend') or 'the selected backend'}.", 520, 220),
        ("frontend_agent", "Frontend Agent", "Implementation", "Implements the frontend tasks when execution is enabled.", 760, 20),
        ("backend_agent", "Backend Agent", "Implementation", "Implements the backend tasks when execution is enabled.", 760, 220),
        ("reviewer", "Reviewer", "Review", "Reviews implementation quality and scope fit.", 1000, 120),
        ("test_runner", "Test Runner", "Validation", "Runs validation checks when execution is enabled.", 1240, 120),
        ("consolidator", "Consolidator", "Consolidation", "Summarizes results and links real artifacts/evidence.", 1480, 120),
    ]
    return [
        {
            "id": node_id,
            "label": label,
            "role": role,
            "status": "pending",
            "description": description if node_id != "planner" else plan_summary,
            "model": None,
            "artifact_ref": None,
            "evidence_ref": None,
            "x": x,
            "y": y,
            "width": 180,
            "height": 96,
        }
        for node_id, label, role, description, x, y in node_specs
    ]


def _build_orchestration_canvas_edges() -> list[dict[str, Any]]:
    pairs = [
        ("orchestrator", "planner"),
        ("planner", "frontend_planner"),
        ("planner", "backend_planner"),
        ("frontend_planner", "frontend_agent"),
        ("backend_planner", "backend_agent"),
        ("frontend_agent", "reviewer"),
        ("backend_agent", "reviewer"),
        ("reviewer", "test_runner"),
        ("test_runner", "consolidator"),
    ]
    return [
        {"id": f"{source}-{target}", "from": source, "to": target}
        for source, target in pairs
    ]


def _build_orchestration_canvas_state(swarm) -> dict[str, Any]:
    now = _project_intake_now()
    intake_state = _get_project_intake_state(swarm)
    plan = dict(intake_state.get("generated_plan") or {})
    existing = getattr(swarm, "orchestration_canvas_state", {}) or {}
    created_at = existing.get("created_at") if isinstance(existing, dict) else None
    return {
        "status": "preview",
        "source": "project_intake",
        "linked_swarm_id": getattr(swarm, "id", None),
        "linked_project_intake_status": intake_state.get("status"),
        "linked_project_intake_state": {
            "status": intake_state.get("status"),
            "answers": dict(intake_state.get("answers") or {}),
            "generated_plan": plan,
        },
        "created_at": created_at or now,
        "updated_at": now,
        "nodes": _build_orchestration_canvas_nodes(plan),
        "edges": _build_orchestration_canvas_edges(),
    }


def _sync_specialized_contract_nodes(swarm) -> None:
    state = getattr(swarm, "orchestration_canvas_state", {}) or {}
    if not isinstance(state, dict):
        return

    nodes = state.get("nodes")
    if not isinstance(nodes, list):
        return

    contracts = [
        contract for contract in getattr(swarm, "contracts", []) or []
        if getattr(contract, "role", None) in {
            "ArchitectAgent",
            "FrontendAgent",
            "BackendAgent",
            "TesterAgent",
            "SecurityAgent",
        }
    ]
    if not contracts:
        return

    node_specs = {
        "ArchitectAgent": {
            "id": "architect_agent_contract",
            "label": "Architect Agent",
            "role": "Dormant Architecture Contract",
            "description": "Contrato especializado disponible. Todavía no ejecuta tareas ni tools.",
            "x": 520,
            "y": 420,
        },
        "FrontendAgent": {
            "id": "frontend_agent_contract",
            "label": "Frontend Agent Contract",
            "role": "Dormant Frontend Contract",
            "description": "Contrato frontend disponible. Se activará cuando existan task types frontend seguros.",
            "x": 760,
            "y": 420,
        },
        "BackendAgent": {
            "id": "backend_agent_contract",
            "label": "Backend Agent Contract",
            "role": "Dormant Backend Contract",
            "description": "Contrato backend disponible. Se activará cuando existan task types backend seguros.",
            "x": 760,
            "y": 560,
        },
        "TesterAgent": {
            "id": "tester_agent_contract",
            "label": "Tester Agent",
            "role": "Dormant Validation Contract",
            "description": "Contrato de validación disponible. No ejecuta shell hasta que exista una shell tool segura.",
            "x": 1000,
            "y": 420,
        },
        "SecurityAgent": {
            "id": "security_agent_contract",
            "label": "Security Agent",
            "role": "Dormant Security Contract",
            "description": "Contrato de seguridad disponible para revisar riesgos antes de habilitar operaciones sensibles.",
            "x": 1000,
            "y": 560,
        },
    }

    existing_nodes_by_id = {
        str(node.get("id")): node
        for node in nodes
        if isinstance(node, dict)
    }
    next_nodes = list(nodes)
    changed = False

    for contract in contracts:
        spec = node_specs.get(getattr(contract, "role", ""))
        if not spec:
            continue

        node_id = spec["id"]
        existing = existing_nodes_by_id.get(node_id)
        node_payload = {
            **spec,
            "status": "draft",
            "model": getattr(contract, "model", None),
            "artifact_ref": None,
            "evidence_ref": "contract:dormant",
            "contract_ref": getattr(contract, "id", None),
            "width": 200,
            "height": 96,
        }

        if existing:
            updated = {**existing, **node_payload}
            if updated != existing:
                existing.update(updated)
                changed = True
            continue

        next_nodes.append(node_payload)
        existing_nodes_by_id[node_id] = node_payload
        changed = True

    if not changed:
        return

    next_state = dict(state)
    next_state["nodes"] = next_nodes
    next_state["specialized_contracts_linked"] = True
    next_state["updated_at"] = datetime.now(timezone.utc).isoformat()
    swarm.orchestration_canvas_state = next_state


def _enrich_orchestration_canvas_with_evidence(swarm) -> None:
    state = getattr(swarm, "orchestration_canvas_state", {}) or {}
    if not isinstance(state, dict):
        return
    nodes = state.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        return

    artifacts = [artifact for artifact in getattr(swarm, "artifacts", []) or [] if isinstance(artifact, dict)]
    final_evidence = [item for item in getattr(swarm, "final_evidence", []) or [] if isinstance(item, dict)]
    final_result = getattr(swarm, "final_result", {}) or {}
    claim_guard = final_result.get("claim_guard") if isinstance(final_result, dict) else None

    first_artifact = artifacts[0] if artifacts else None
    artifact_ref = str(first_artifact.get("id") or first_artifact.get("path") or "") if first_artifact else None
    evidence_ref = None
    if first_artifact:
        evidence_ref = str(first_artifact.get("evidence_id") or first_artifact.get("evidence_ref") or "") or None
    if not evidence_ref:
        artifact_evidence = next((item for item in final_evidence if item.get("kind") == "artifact"), None)
        artifact_payload = artifact_evidence.get("artifact") if isinstance(artifact_evidence, dict) else None
        if isinstance(artifact_payload, dict):
            evidence_ref = str(artifact_payload.get("evidence_id") or artifact_payload.get("evidence_ref") or "") or None

    review_evidence = next((item for item in final_evidence if item.get("kind") == "review_result"), None)
    review_payload = review_evidence.get("review_result") if isinstance(review_evidence, dict) else None
    review_ref = None
    if isinstance(review_payload, dict):
        review_ref = str(review_payload.get("artifact_id") or review_payload.get("artifact_path") or "") or None

    tool_evidence = next((item for item in final_evidence if item.get("kind") == "tool_history_summary"), None)
    tool_ref = None
    if isinstance(tool_evidence, dict):
        tools = tool_evidence.get("tools") or []
        if isinstance(tools, list) and tools:
            tool_ref = f"{sum(1 for tool in tools if isinstance(tool, dict) and tool.get('ok') is True)}/{len(tools)} tools ok"

    final_status = str(final_result.get("status") or getattr(swarm, "status", "") or "") if isinstance(final_result, dict) else str(getattr(swarm, "status", "") or "")
    claim_status = str(claim_guard.get("status") or "") if isinstance(claim_guard, dict) else ""

    next_nodes: list[dict[str, Any]] = []
    changed = False
    for node in nodes:
        if not isinstance(node, dict):
            next_nodes.append(node)
            continue
        next_node = dict(node)
        node_id = str(next_node.get("id") or "")

        if node_id in {"frontend_agent", "backend_agent"} and artifact_ref:
            next_node["artifact_ref"] = artifact_ref
            next_node["evidence_ref"] = evidence_ref
            next_node["status"] = "completed" if first_artifact else next_node.get("status", "pending")
        elif node_id == "reviewer" and review_ref:
            next_node["artifact_ref"] = review_ref
            next_node["evidence_ref"] = review_ref
            next_node["status"] = "completed"
        elif node_id == "test_runner" and tool_ref:
            next_node["evidence_ref"] = tool_ref
            next_node["status"] = "completed"
        elif node_id == "consolidator" and final_status:
            next_node["evidence_ref"] = f"claim_guard:{claim_status or 'unknown'}"
            next_node["status"] = "completed" if final_status == "completed" and claim_status in {"", "verified"} else final_status

        if next_node != node:
            changed = True
        next_nodes.append(next_node)

    if not changed:
        return
    next_state = dict(state)
    next_state["nodes"] = next_nodes
    next_state["updated_at"] = datetime.now(timezone.utc).isoformat()
    next_state["evidence_linked"] = True
    swarm.orchestration_canvas_state = next_state


def _ensure_orchestration_canvas_preview(swarm) -> None:
    intake_state = _get_project_intake_state(swarm)
    if intake_state.get("status") != "ready_to_implement":
        return
    swarm.orchestration_canvas_state = _build_orchestration_canvas_state(swarm)


def _is_project_intake_collecting(swarm) -> bool:
    return _get_project_intake_state(swarm).get("status") == "collecting"


def _save_local_chat_message(swarm, coordinator_id: str, assistant_content: str, payload: dict[str, Any]):
    route = str(payload.get("route") or "project_intake")
    swarm.messages.append(
        AgentToAgentMessage(
            type="chat_message",
            from_agent_id=coordinator_id,
            to_agent_id="user",
            payload={
                "role": "assistant",
                "content": assistant_content,
                "route": route,
                "source": "local",
                "answer_guard_applied": False,
                "answer_guard_reason": None,
                **payload,
            },
            requires_response=False,
        )
    )
    swarm.final_result = {
        "status": "completed",
        "summary": assistant_content,
        "intent": "chat",
        "route": route,
        "source": "local",
        "answer_guard_applied": False,
        "answer_guard_reason": None,
    }
    if "project_intake_state" in payload:
        swarm.final_result["project_intake_state"] = payload["project_intake_state"]
    if "project_intake_action" in payload:
        swarm.final_result["project_intake_action"] = payload["project_intake_action"]
    if "orchestration_canvas_state" in payload:
        swarm.final_result["orchestration_canvas_state"] = payload["orchestration_canvas_state"]



def _controlled_chat_response(route: str, user_message: str, swarm) -> str | None:
    if route == "app_short_identity":
        return _openswarm_short_identity()

    if route == "app_identity":
        return _openswarm_app_explanation()

    if route == "app_capability":
        return _openswarm_capability_explanation()

    if route == "dashboard_state":
        return _current_swarm_state_explanation(swarm)

    if route == "swarm_memory":
        return _swarm_memory_explanation(swarm, user_message)

    if route == "artifact_query":
        return _artifact_query_explanation(swarm)

    if route == "task_status":
        return _task_status_explanation(swarm)

    if route == "implementation_request":
        return _implementation_request_explanation()

    if route == "planning_request":
        return _planning_request_explanation()

    if route == "debug_request":
        return _debug_request_explanation()

    if route == "tool_request":
        return _tool_request_explanation()

    if route == "project_status":
        return _project_status_explanation()

    if route == "dashboard_help":
        return _dashboard_help_explanation()

    if route == "agent_help":
        return _agent_help_explanation()

    if route == "web_research_request":
        return _web_research_request_explanation()

    return None


def _normalize_chat_response(content: str, user_message: str) -> str:
    text = (content or "").strip()
    route = _classify_chat_question(user_message)

    if route == "app_identity":
        return _openswarm_app_explanation()

    if route == "app_capability":
        return _openswarm_capability_explanation()

    if not text:
        return "No se generó una respuesta."

    try:
        parsed = json.loads(text)
    except Exception:
        return text

    if isinstance(parsed, dict):
        for key in ("answer", "response", "content", "message", "summary", "text"):
            value = parsed.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        function_name = str(parsed.get("function_name") or "").strip().lower()
        query = ""
        params = parsed.get("parameters")
        if isinstance(params, dict):
            query = str(params.get("query") or "").strip().lower()

        normalized_user = user_message.strip().lower()
        if "app" in normalized_user or "aplic" in normalized_user or "openswarm" in normalized_user or "app" in query:
            return _openswarm_app_explanation()

        if function_name:
            return "El modelo devolvió una intención estructurada, pero no una respuesta conversacional útil."

    return text


@swarms.router.get("/list")
async def list_swarms(dashboard_id: str | None = None):
    return {"swarms": swarm_orchestrator.store.list(dashboard_id=dashboard_id)}


@swarms.router.post("/create")
async def create_swarm(body: CreateSwarmRequest):
    try:
        swarm = swarm_orchestrator.create_swarm(
            user_prompt=body.user_prompt,
            dashboard_id=body.dashboard_id,
            workspace_path=body.workspace_path,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    event_trace_runtime.create(
        swarm_id=swarm.id,
        event_type="agent_message",
        payload={"message": "swarm_created", "title": swarm.title},
    )
    return _dump(swarm)


@swarms.router.get("/{swarm_id}")
async def get_swarm(swarm_id: str):
    return _dump(_load_or_404(swarm_id))


@swarms.router.get("/{swarm_id}/tasks")
async def get_swarm_tasks(swarm_id: str):
    swarm = _load_or_404(swarm_id)
    return {"tasks": [task.model_dump(mode="json") for task in swarm.tasks]}


@swarms.router.get("/{swarm_id}/agents")
async def get_swarm_agents(swarm_id: str):
    swarm = _load_or_404(swarm_id)
    return {"agents": [contract.model_dump(mode="json") for contract in swarm.contracts]}


@swarms.router.get("/{swarm_id}/messages")
async def get_swarm_messages(swarm_id: str):
    swarm = _load_or_404(swarm_id)
    return {"messages": [message.model_dump(mode="json") for message in swarm.messages]}


@swarms.router.get("/{swarm_id}/artifacts")
async def get_swarm_artifacts(swarm_id: str):
    swarm = _load_or_404(swarm_id)
    return {"artifacts": swarm.artifacts}


@swarms.router.get("/{swarm_id}/evidence")
async def get_swarm_evidence(swarm_id: str):
    swarm = _load_or_404(swarm_id)
    return {"evidence": [item.model_dump(mode="json") for item in swarm.evidence]}


@swarms.router.post("/{swarm_id}/experimental/chat")
async def experimental_swarm_chat(swarm_id: str, body: ExperimentalChatRequest):
    swarm = _load_or_404(swarm_id)
    user_message = (body.message or "").strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="message is required")
    if getattr(swarm, "intent", "task") != "chat":
        raise HTTPException(status_code=400, detail="Swarm is not a chat-intent swarm")

    coordinator_id = swarm.coordinator_contract_id or (swarm.contracts[0].id if swarm.contracts else "swarm")
    swarm.messages.append(
        AgentToAgentMessage(
            type="chat_message",
            from_agent_id="user",
            to_agent_id=coordinator_id,
            payload={"role": "user", "content": user_message},
            requires_response=True,
        )
    )

    route = _classify_chat_question(user_message)
    project_intake_payload: dict[str, Any] | None = None
    if _is_project_intake_collecting(swarm):
        assistant_content, project_intake_payload = _advance_project_intake(swarm, user_message)
    elif route == "implementation_request":
        assistant_content, project_intake_payload = _start_project_intake(swarm, user_message)

    if project_intake_payload:
        _save_local_chat_message(swarm, coordinator_id, assistant_content, project_intake_payload)
        swarm = swarm_orchestrator.store.save(swarm)
        event_trace_runtime.create(
            swarm_id=swarm.id,
            event_type="chat_completed",
            payload={
                "message": "project_intake_updated",
                "source": "local_project_intake",
                "route": project_intake_payload.get("route"),
                "project_intake_status": (project_intake_payload.get("project_intake_state") or {}).get("status"),
            },
        )
        return {**_dump(swarm), "provider_events": []}

    controlled_content = _controlled_chat_response(route, user_message, swarm)
    if controlled_content:
        assistant_content = controlled_content
        swarm.messages.append(
            AgentToAgentMessage(
                type="chat_message",
                from_agent_id=coordinator_id,
                to_agent_id="user",
                payload={
                    "role": "assistant",
                    "content": assistant_content,
                    "route": route,
                    "source": "local",
                    "answer_guard_applied": False,
                    "answer_guard_reason": None,
                },
                requires_response=False,
            )
        )
        swarm.final_result = {
            "status": "completed",
            "summary": assistant_content,
            "intent": "chat",
            "route": route,
            "answer_guard_applied": False,
        }
        swarm = swarm_orchestrator.store.save(swarm)
        event_trace_runtime.create(
            swarm_id=swarm.id,
            event_type="chat_completed",
            payload={"message": "chat_response_generated", "source": "local_project_context", "route": route},
        )
        return {**_dump(swarm), "provider_events": []}

    adapter = OllamaAdapter(allow_network=True, supports_json_mode=False)
    local_chat_context = _build_local_chat_context(swarm, user_message, route)

    context = ProviderTurnContext(
        session_id=swarm.id,
        agent_id=coordinator_id,
        model=body.model,
        system_prompt=(
            "You are OpenSwarm's local-first swarm chat coordinator. "
            "Answer in plain text, not JSON. "
            "Answer in the same language as the user. "
            "Use the provided local OpenSwarm context as the source of truth. "
            "Do not claim that you executed tools, created files, or ran tasks unless the runtime did so. "
            "Do not invent conversation history, tasks, artifacts, approvals, app capabilities, or dashboard state. "
            "If the user asks for an executable project task, explain that it should be run as a task swarm. "
            "If local evidence is insufficient, say that clearly."
        ),
        messages=[{"role": "user", "content": local_chat_context}],
        tools=[],
    )

    assistant_content = ""
    provider_events: list[dict[str, Any]] = []
    async for event in adapter.run_turn(context):
        provider_events.append({"type": event.type, "payload": event.payload})
        if event.type == "message_final":
            message = event.payload.get("message") or {}
            assistant_content = str(message.get("content") or "").strip()
        elif event.type == "error":
            raise HTTPException(status_code=500, detail=str(event.payload.get("error") or "Ollama chat failed"))

    assistant_content = _normalize_chat_response(assistant_content, user_message)
    guarded_content, answer_guard_reason = _answer_quality_guard_result(assistant_content, user_message, swarm)
    answer_guard_applied = answer_guard_reason is not None or guarded_content != assistant_content
    assistant_content = guarded_content

    swarm.messages.append(
        AgentToAgentMessage(
            type="chat_message",
            from_agent_id=coordinator_id,
            to_agent_id="user",
            payload={
                "role": "assistant",
                "content": assistant_content,
                "route": route,
                "source": "model",
                "answer_guard_applied": answer_guard_applied,
                "answer_guard_reason": answer_guard_reason,
            },
            requires_response=False,
        )
    )
    swarm.final_result = {
        "status": "completed",
        "summary": assistant_content,
        "intent": "chat",
        "route": route,
        "answer_guard_applied": answer_guard_applied,
        "answer_guard_reason": answer_guard_reason,
    }
    swarm = swarm_orchestrator.store.save(swarm)

    event_trace_runtime.create(
        swarm_id=swarm.id,
        event_type="chat_completed",
        payload={
            "message": "chat_response_generated",
            "route": route,
            "answer_guard_applied": answer_guard_applied,
            "answer_guard_reason": answer_guard_reason,
        },
    )

    return {**_dump(swarm), "provider_events": provider_events}


@swarms.router.patch("/{swarm_id}/orchestration-canvas/nodes/position")
async def update_orchestration_node_position(swarm_id: str, body: OrchestrationNodePositionRequest):
    swarm = _load_or_404(swarm_id)
    state = getattr(swarm, "orchestration_canvas_state", {}) or {}
    if not isinstance(state, dict):
        raise HTTPException(status_code=400, detail="orchestration_canvas_state is not available")

    nodes = state.get("nodes")
    if not isinstance(nodes, list):
        raise HTTPException(status_code=400, detail="orchestration nodes are not available")

    found = False
    updated_nodes: list[dict[str, Any]] = []
    for node in nodes:
        if not isinstance(node, dict):
            updated_nodes.append(node)
            continue
        next_node = dict(node)
        if str(next_node.get("id") or "") == body.node_id:
            if body.x is not None:
                next_node["x"] = body.x
            if body.y is not None:
                next_node["y"] = body.y
            if body.expanded is not None:
                next_node["expanded"] = body.expanded
            found = True
        updated_nodes.append(next_node)

    if not found:
        raise HTTPException(status_code=404, detail="orchestration node not found")

    state = dict(state)
    state["nodes"] = updated_nodes
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    swarm.orchestration_canvas_state = state
    swarm = swarm_orchestrator.store.save(swarm)

    event_trace_runtime.create(
        swarm_id=swarm.id,
        event_type="orchestration_canvas_updated",
        payload={
            "message": "orchestration_node_position_updated",
            "node_id": body.node_id,
            "x": body.x,
            "y": body.y,
            "expanded": body.expanded,
        },
    )

    return _dump(swarm)


@swarms.router.get("/{swarm_id}/events")
async def get_swarm_events(swarm_id: str):
    swarm = _load_or_404(swarm_id)
    persisted_events = [event for event in swarm.events if isinstance(event, dict)]
    memory_events = [event.to_dict() for event in event_trace_runtime.list_swarm_events(swarm_id)]

    merged: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for event in [*persisted_events, *memory_events]:
        event_id = str(event.get("id") or "")
        if event_id and event_id in seen_ids:
            continue
        if event_id:
            seen_ids.add(event_id)
        merged.append(event)

    return {"events": merged}


@swarms.router.get("/{swarm_id}/experimental/approvals")
async def experimental_list_approvals(swarm_id: str, status: str | None = None):
    _load_or_404(swarm_id)
    valid_statuses = {"pending", "allowed", "denied", "resumed", "resume_failed"}
    if status is not None and status not in valid_statuses:
        raise HTTPException(status_code=400, detail="status must be pending, allowed, denied, resumed, or resume_failed")
    approvals = approval_runtime.list_approvals(swarm_id=swarm_id, status=status)  # type: ignore[arg-type]
    pending_count = len(approval_runtime.list_approvals(swarm_id=swarm_id, status="pending"))
    return {"approvals": approvals, "pending_count": pending_count}


@swarms.router.get("/{swarm_id}/experimental/approvals/{approval_id}")
async def experimental_get_approval(swarm_id: str, approval_id: str):
    _load_or_404(swarm_id)
    approval = approval_runtime.get_approval(approval_id, swarm_id=swarm_id)
    if not approval:
        raise HTTPException(status_code=404, detail=f"approval not found: {approval_id}")
    return {"approval": approval}


@swarms.router.post("/{swarm_id}/experimental/approvals/{approval_id}/allow")
async def experimental_allow_approval(swarm_id: str, approval_id: str, body: ExperimentalApprovalDecisionRequest | None = None):
    _load_or_404(swarm_id)
    payload = body or ExperimentalApprovalDecisionRequest()
    try:
        decision = approval_runtime.resolve_request(
            approval_id,
            behavior="allow",
            swarm_id=swarm_id,
            message=payload.message,
            updated_input=payload.updated_input,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    approval = approval_runtime.get_approval(approval_id, swarm_id=swarm_id)
    return {"ok": True, "approval": approval, "decision": decision.to_dict(), "resume_supported": True}


@swarms.router.post("/{swarm_id}/experimental/approvals/{approval_id}/deny")
async def experimental_deny_approval(swarm_id: str, approval_id: str, body: ExperimentalApprovalDecisionRequest | None = None):
    _load_or_404(swarm_id)
    payload = body or ExperimentalApprovalDecisionRequest()
    try:
        decision = approval_runtime.resolve_request(
            approval_id,
            behavior="deny",
            swarm_id=swarm_id,
            message=payload.message,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    approval = approval_runtime.get_approval(approval_id, swarm_id=swarm_id)
    return {"ok": True, "approval": approval, "decision": decision.to_dict()}


@swarms.router.post("/{swarm_id}/experimental/approvals/{approval_id}/resume")
async def experimental_resume_approval(swarm_id: str, approval_id: str):
    _load_or_404(swarm_id)
    try:
        result = approval_runtime.resume_approval_tool(approval_id, swarm_id=swarm_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    approval = approval_runtime.get_approval(approval_id, swarm_id=swarm_id)
    return {"ok": result.ok, "approval": approval, "result": result.to_history_entry()}


@swarms.router.post("/{swarm_id}/run-mvp")
async def run_swarm_mvp(swarm_id: str, body: RunMVPRequest | None = None):
    try:
        swarm = swarm_mvp_executor.run_readme_review_mvp(
            swarm_id,
            workspace_path=body.workspace_path if body else None,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Swarm not found")
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _dump(swarm)


@swarms.router.post("/{swarm_id}/experimental/run-task")
async def experimental_run_task(swarm_id: str, body: ExperimentalMiniRuntimeRequest):
    if not experimental_mini_runtime_enabled():
        raise HTTPException(status_code=404, detail="Experimental mini runtime is disabled")
    _load_or_404(swarm_id)
    try:
        result = await experimental_mini_runtime_service.run_ollama_task(body=body, swarm_id=swarm_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result.model_dump(mode="json")


@swarms.router.post("/{swarm_id}/experimental/run-task/{task_id}")
async def experimental_run_existing_task(swarm_id: str, task_id: str, body: ExperimentalDAGTaskRunRequest):
    if not experimental_dag_task_runtime_enabled():
        raise HTTPException(status_code=404, detail="Experimental DAG task runtime is disabled")
    _load_or_404(swarm_id)
    try:
        result = await experimental_dag_task_runner.run_task(swarm_id=swarm_id, task_id=task_id, body=body)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result.model_dump(mode="json")


@swarms.router.post("/{swarm_id}/experimental/run-worker-review")
async def experimental_run_worker_review(swarm_id: str, body: ExperimentalWorkerReviewRunRequest):
    if not experimental_dag_chain_runtime_enabled():
        raise HTTPException(status_code=404, detail="Experimental DAG chain runtime is disabled")
    _load_or_404(swarm_id)
    try:
        result = await experimental_dag_chain_runner.run_worker_review(swarm_id=swarm_id, body=body)
        swarm = swarm_orchestrator.store.load(swarm_id)
        _enrich_orchestration_canvas_with_evidence(swarm)
        swarm_orchestrator.store.save(swarm)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result.model_dump(mode="json")


@swarms.router.post("/{swarm_id}/experimental/consolidate-final")
async def experimental_consolidate_final(swarm_id: str, body: ExperimentalConsolidateFinalRequest | None = None):
    if not experimental_dag_consolidate_runtime_enabled():
        raise HTTPException(status_code=404, detail="Experimental DAG consolidate runtime is disabled")
    _load_or_404(swarm_id)
    try:
        result = experimental_dag_consolidator.consolidate_final(swarm_id=swarm_id, body=body)
        swarm = swarm_orchestrator.store.load(swarm_id)
        _sync_specialized_contract_nodes(swarm)
        _enrich_orchestration_canvas_with_evidence(swarm)
        swarm = swarm_orchestrator.store.save(swarm)
        result = result.model_copy(update={
            "final_result": swarm.final_result,
            "final_evidence": swarm.final_evidence,
            "tasks": [task.model_dump(mode="json") for task in swarm.tasks],
            "artifacts": swarm.artifacts,
            "messages": [message.model_dump(mode="json") for message in swarm.messages],
        })
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result.model_dump(mode="json")


@swarms.router.post("/{swarm_id}/experimental/run-mini-dag")
async def experimental_run_mini_dag(swarm_id: str, body: ExperimentalMiniDAGRunRequest):
    if not experimental_dag_mini_runner_enabled():
        raise HTTPException(status_code=404, detail="Experimental DAG mini runner is disabled")
    _load_or_404(swarm_id)
    try:
        result = await experimental_dag_mini_runner.run_mini_dag(swarm_id=swarm_id, body=body)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result.model_dump(mode="json")


@swarms.router.post("/{swarm_id}/experimental/run-dag-dependencies")
async def experimental_run_dag_dependencies(swarm_id: str, body: ExperimentalDAGDependencyRunRequest):
    if not experimental_dag_dependency_runner_enabled():
        raise HTTPException(status_code=404, detail="Experimental DAG dependency runner is disabled")
    _load_or_404(swarm_id)
    try:
        result = await experimental_dag_dependency_runner.run_dag_dependencies(swarm_id=swarm_id, body=body)
        swarm = swarm_orchestrator.store.load(swarm_id)
        _enrich_orchestration_canvas_with_evidence(swarm)
        swarm_orchestrator.store.save(swarm)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result.model_dump(mode="json")


@swarms.router.post("/{swarm_id}/experimental/start-implementation")
async def experimental_start_implementation(swarm_id: str, body: ExperimentalDAGDependencyRunRequest):
    if not experimental_dag_dependency_runner_enabled():
        raise HTTPException(status_code=404, detail="Experimental DAG dependency runner is disabled")
    swarm = _load_or_404(swarm_id)
    intake_state = _get_project_intake_state(swarm)
    if intake_state.get("status") != "ready_to_implement":
        raise HTTPException(status_code=400, detail="Project intake is not ready to implement")

    try:
        _ensure_orchestration_canvas_preview(swarm)
        swarm = swarm_orchestrator.store.save(swarm)
        generated_plan = intake_state.get("generated_plan") if isinstance(intake_state, dict) else None
        swarm_orchestrator.ensure_readme_dag(swarm_id=swarm_id, generated_plan=generated_plan)
        swarm_orchestrator.ensure_specialized_agent_contracts(swarm_id=swarm_id, generated_plan=generated_plan)

        result = await experimental_dag_dependency_runner.run_dag_dependencies(swarm_id=swarm_id, body=body)

        swarm = swarm_orchestrator.store.load(swarm_id)
        _sync_specialized_contract_nodes(swarm)
        _enrich_orchestration_canvas_with_evidence(swarm)
        swarm = swarm_orchestrator.store.save(swarm)

        return {
            "ok": result.ok,
            "status": result.status,
            "enabled": True,
            "swarm_id": swarm_id,
            "implementation": result.model_dump(mode="json"),
            **_dump(swarm),
        }
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@swarms.router.post("/{swarm_id}/pause")
async def pause_swarm(swarm_id: str):
    try:
        swarm = swarm_orchestrator.update_status(swarm_id=swarm_id, status="paused")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Swarm not found")
    return _dump(swarm)


@swarms.router.post("/{swarm_id}/resume")
async def resume_swarm(swarm_id: str):
    try:
        swarm = swarm_orchestrator.update_status(swarm_id=swarm_id, status="running")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Swarm not found")
    return _dump(swarm)


@swarms.router.post("/{swarm_id}/cancel")
async def cancel_swarm(swarm_id: str):
    try:
        swarm = swarm_orchestrator.update_status(swarm_id=swarm_id, status="cancelled")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Swarm not found")
    event_trace_runtime.create(
        swarm_id=swarm.id,
        event_type="stop_requested",
        payload={"reason": "api_cancel"},
    )
    return _dump(swarm)


@swarms.router.post("/{swarm_id}/artifacts")
async def submit_artifact(swarm_id: str, body: SubmitArtifactRequest):
    try:
        swarm = swarm_orchestrator.submit_artifact(
            swarm_id=swarm_id,
            from_agent_id=body.from_agent_id,
            task_id=body.task_id,
            artifact=body.artifact,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Swarm not found")
    event_trace_runtime.create(
        swarm_id=swarm.id,
        task_id=body.task_id,
        agent_id=body.from_agent_id,
        event_type="agent_message",
        payload={"message_type": "submit_artifact", "artifact": body.artifact},
    )
    return _dump(swarm)


@swarms.router.post("/{swarm_id}/request-review")
async def request_review(swarm_id: str, body: RequestReviewRequest):
    try:
        swarm = swarm_orchestrator.request_review(
            swarm_id=swarm_id,
            from_agent_id=body.from_agent_id,
            to_agent_id=body.to_agent_id,
            task_id=body.task_id,
            artifact_refs=body.artifact_refs,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Swarm not found")
    event_trace_runtime.create(
        swarm_id=swarm.id,
        task_id=body.task_id,
        agent_id=body.from_agent_id,
        event_type="review_requested",
        payload={"to_agent_id": body.to_agent_id, "artifact_refs": body.artifact_refs},
    )
    return _dump(swarm)
