# OpenSwarm Swarm Runtime Audit

Fecha: 2026-05-17

Este documento congela la Fase 1 y Fase 2 del plan incremental para llevar OpenSwarm a un runtime multiagente local-first y provider-agnostic sin reemplazar lo que ya existe.

## Fase 1 — Auditoría de lo existente

### Backend y runtime actual

- `backend/apps/agents/agent_manager.py` concentra el runtime principal: sesiones, prompt composition, Claude SDK, permisos, approvals, MCP, streaming, compaction, stop/cancel, provider routing y el loop local de Ollama.
- `backend/apps/agents/agents.py` expone REST endpoints de sesiones, mensajes, approvals, modelos, planes persistentes y ejecución básica de planes.
- `backend/apps/agents/models.py` define `AgentConfig`, `AgentSession`, `Message`, approvals, branches y metadata de tools.
- `backend/apps/agents/ws_manager.py` y `backend/apps/agents/seq_log.py` ya proveen eventos WebSocket por sesión, broadcast global, approvals y replay con secuencias.
- `backend/apps/agents/providers/registry.py` ya registra modelos Anthropic, OpenAI, Gemini, OpenRouter y Ollama; también resuelve rutas de provider/modelo y pricing.

### Tools, approvals y policy actual

- `backend/apps/tools_lib/*` ya provee builtin tools, MCP tool definitions, permisos por tool/subtool, discovery y OAuth/token refresh.
- El flujo Claude SDK usa `can_use_tool`, `PreToolUse` y `PostToolUse` en `agent_manager.py` para allow/deny/ask y registro de resultados.
- Las reglas automáticas existen, pero están mezcladas en `agent_manager.py`: denied tools, MCP gates, command/path handling de Ollama, context guards y limits.

### Planes, dashboard y UI

- `backend/apps/agents/plans.py` existe como persistencia file-backed para planes, `execution_state`, decisions y validation log.
- `frontend/src/shared/state/plansSlice.ts` y `frontend/src/app/pages/Dashboard/PersistentPlansCard.tsx` exponen planes persistentes en UI.
- Dashboard/canvas ya tiene cards de agentes, browser cards, plans card, estado y selección.

### Multiagente actual

- Claude path puede crear subagentes con el tool `Agent`.
- `InvokeAgent` existe como MCP server (`invoke_agent_mcp_server.py`) y endpoint backend (`/api/invoke-agent/run`) para invocar/forkear otra sesión.
- Browser agents existen con runtime propio en `browser_agent.py` y cards visibles.
- Falta un Swarm Orchestrator formal con Plan Runtime + Task DAG + Agent Contracts + A2A messaging estructurado.

### Ollama actual

- Ollama está registrado como provider/modelos `ollama/*` en `providers/registry.py`.
- La ejecución real de Ollama hoy entra por un bloque inline en `agent_manager.py` llamado “OLLAMA LOCAL TOOL LOOP”.
- Ese bloque implementa tools locales propias (`read_file`, `write_file`, `run_command`, etc.) y reglas propias.
- Conclusión: Ollama hoy funciona como bypass parcial; no usa plenamente Tool Runtime, Approval Runtime, Policy Runtime, Event/Trace Runtime, MCP, Agent/InvokeAgent ni browser agents.

## Fase 2 — Mapeo de capas

| Capa objetivo | Estado real | Módulos actuales | Acción |
|---|---|---|---|
| Swarm API + WebSocket Events | parcial | `agents.py`, `main.py`, `ws_manager.py`, `seq_log.py` | Adaptar; agregar API/events de swarm sin reemplazar WS actual |
| Swarm Orchestrator | parcial | `Agent` tool, `InvokeAgent`, browser agents | Crear orquestador mínimo encima de sesiones existentes |
| Plan Runtime | parcial | `plans.py` | Adaptar a tasks, evidence y artifacts |
| Task DAG Runtime | no formal | `plans.py` execution_state básico | Crear pieza nueva file-backed |
| Agent Contract Runtime | no existe | modes/prompts dispersos | Crear contratos por task/role |
| Agent Registry | parcial | `modes/models.py`, session mode/name | Completar con roles formales |
| Shared Memory / State Store | parcial | `data/sessions`, `data/plans`, messages | Adaptar store común de swarm/task/artifact |
| Agent-to-Agent Messaging | parcial | `InvokeAgent` prompt-based | Crear mensajes estructurados |
| Agent Runtime | existe acoplado | `agent_manager.py` | Adelgazar incrementalmente |
| Session Runtime | parcial | `AgentSession`, `_save_session`, `_load_session_data` | Formalizar `agent_id`, `task_id`, provider/runtime/stop/resume state |
| Provider Adapter Interface | no existe | registry + conditionals | Crear interfaz mínima primero |
| ClaudeSDKAdapter | implícito | Claude SDK path en `agent_manager.py` | Envolver sin eliminar |
| OllamaAdapter | parcial/bypass | inline Ollama loop en `agent_manager.py` | Extraer y conectar al flujo nativo |
| Tool Runtime | parcial | `tools_lib`, hooks SDK, MCP servers | Unificar como runtime provider-independent |
| Approval Runtime | parcial | `ApprovalRequest`, `ws_manager`, hooks | Extraer/adaptar |
| Policy Runtime | parcial | reglas mezcladas | Extraer reglas automáticas |
| Event/Trace Runtime | parcial | WS messages, seq log | Agregar trace schema estructurado |

## Riesgos detectados

- `agent_manager.py` es monolítico y cualquier refactor invasivo puede romper Claude SDK, sesiones, WS, tools o stop/cancel.
- El bloque Ollama duplica capacidades y reglas; extraerlo requiere tests de seguridad antes de cambiar comportamiento.
- Los planes persistentes existen, pero la ejecución actual delega a una sesión Agent con prompt; todavía no hay Task DAG durable real.
- Hay muchos cambios no commiteados preexistentes en el working tree. Las siguientes fases deben tocar archivos nuevos o puntos pequeños y verificables.

## Decisión de seguridad

Fase 3 solo agrega una Provider Adapter Interface mínima y no cambia el flujo runtime. Claude y Ollama siguen entrando por el flujo actual hasta que sus adapters se conecten explícitamente en fases posteriores.

## Tool execution audit update — Phase 10b

Verified before extracting the shared execution layer:

- `backend/apps/agents/agent_manager.py` owns the current production Claude SDK flow. Claude tools are still executed by the SDK/CLI hooks configured from `ClaudeAgentOptions`, MCP server config, and approval callbacks; this was not rerouted.
- `backend/apps/agents/agent_manager.py` also contains the current Ollama inline local loop. Its local filesystem tools (`read_file`, `write_file`, `edit_file`, `search_files`, `run_command`, etc.) are nested functions inside the Ollama branch, so Ollama is still not using the shared runtime yet.
- `backend/apps/tools_lib/models.py` defines builtin tool declarations (`Read`, `Write`, `Edit`, `Bash`, `Glob`, `Grep`, browser tools, `InvokeAgent`, etc.). These are definitions/registry entries, not one shared execution engine.
- MCP tools are currently exposed through installed tool definitions and SDK/MCP server configuration. Direct MCP execution remains on the existing AgentManager/SDK path.
- Browser agent and `InvokeAgent` execution remain inside existing AgentManager/browser MCP paths.
- `backend/apps/agents/orchestration/executor.py` previously executed MVP `Read`/`Write` itself. It now delegates those real filesystem operations to `backend/apps/agents/runtime/tools.py` via `ToolCall` + `ToolExecutionContext`.

Current shared ToolRuntime execution scope:

- Migrated now: builtin `Read` and `Write` for the Swarm MVP.
- Explicitly not migrated yet: `Edit`, `Bash`, `Glob`, `Grep`, MCP, browser tools, `InvokeAgent`, Claude SDK hook execution, Ollama inline tool loop.
- ToolRuntime now records normalized `ToolResult`, appends optional `tool_history`, and emits `tool_started` / `tool_completed` / `tool_failed` through EventTraceRuntime.
