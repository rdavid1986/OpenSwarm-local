# Experimental Mini Runtime HTTP Smoke

This validates the isolated experimental path:

`/api/swarms/{swarm_id}/experimental/run-task -> MiniAgentRuntime -> ProviderTurnHarness -> ProviderToolBridge -> ToolRuntime -> OllamaAdapter`

It does **not** use AgentManager, the current Ollama inline loop, Claude SDK flow, MCP, browser tools, InvokeAgent, run_command, destructive tools, or the UI/canvas.

## Required flags

The backend must be started with:

```text
OPENSWARM_EXPERIMENTAL_MINI_RUNTIME=1
```

The smoke defaults to:

```text
OPENSWARM_SMOKE_OLLAMA_MODEL=qwen2.5-coder:14b
OLLAMA_BASE_URL=http://localhost:11434
OPENSWARM_SMOKE_BACKEND_URL=http://127.0.0.1:8324
```

## Start backend with flag — PowerShell

```powershell
$env:OPENSWARM_EXPERIMENTAL_MINI_RUNTIME="1"
$env:OPENSWARM_PORT="8324"
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8324
```

## Start backend with flag — Git Bash

```bash
export OPENSWARM_EXPERIMENTAL_MINI_RUNTIME=1
export OPENSWARM_PORT=8324
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8324
```

## Check health

```powershell
Invoke-RestMethod http://127.0.0.1:8324/api/health/check
```

Expected:

```text
OK
```

## Run HTTP smoke

PowerShell:

```powershell
$env:OPENSWARM_EXPERIMENTAL_MINI_RUNTIME="1"
$env:OPENSWARM_SMOKE_BACKEND_URL="http://127.0.0.1:8324"
$env:OPENSWARM_SMOKE_OLLAMA_MODEL="qwen2.5-coder:14b"
$env:OLLAMA_BASE_URL="http://localhost:11434"
python -m backend.apps.agents.runtime.smoke_experimental_http_ollama
```

Git Bash:

```bash
export OPENSWARM_EXPERIMENTAL_MINI_RUNTIME=1
export OPENSWARM_SMOKE_BACKEND_URL=http://127.0.0.1:8324
export OPENSWARM_SMOKE_OLLAMA_MODEL=qwen2.5-coder:14b
export OLLAMA_BASE_URL=http://localhost:11434
python -m backend.apps.agents.runtime.smoke_experimental_http_ollama
```

## Endpoint payload

`POST /api/swarms/create`

```json
{
  "user_prompt": "HTTP smoke experimental Ollama MiniRuntime",
  "workspace_path": "C:/temp/openswarm-http-ollama"
}
```

`POST /api/swarms/{swarm_id}/experimental/run-task`

```json
{
  "model": "qwen2.5-coder:14b",
  "task": "Crea un README.md en el workspace usando la tool de escritura. Luego responde con evidencia del archivo creado.",
  "workspace_path": "C:/temp/openswarm-http-ollama",
  "allowed_tools": ["Read", "Write", "Edit", "SearchFiles", "SearchText"],
  "base_url": "http://localhost:11434",
  "max_turns": 8
}
```

## Common errors

- `404 Experimental mini runtime is disabled`: backend was not started with `OPENSWARM_EXPERIMENTAL_MINI_RUNTIME=1` or you are hitting an older backend process.
- `422 Unprocessable Entity`: payload does not match the endpoint schema. `/api/swarms/create` accepts `{}` now, but documented payload should include `user_prompt` and optionally `workspace_path`.
- `provider_unavailable`: Ollama is not running or `base_url` is wrong.
- model not found: pull/start the model in Ollama, e.g. `ollama pull qwen2.5-coder:14b`.
- `runtime_not_completed` or `write_not_completed`: model did not produce a usable tool call; inspect the JSON diagnostics printed by the smoke.

## Experimental single DAG task endpoint

This endpoint runs **one existing TaskNode** from a swarm DAG through MiniAgentRuntime + OllamaAdapter. It does not traverse dependencies, run reviewer, consolidate final output, or replace the existing MVP executor.

When a selected task writes or edits files, the runner also records structured
swarm state:

- `swarm.artifacts[]` with the touched file path, task id, agent id/role, status, bytes, and evidence reference.
- `task.artifacts[]` and `task.touched_files[]`.
- `submit_artifact` message from the executing agent.
- `request_review` message when a dependent review task can be inferred.

The downstream review/consolidation tasks remain `pending`; this endpoint only
prepares the state for the next step.

Required backend flags:

```text
OPENSWARM_EXPERIMENTAL_MINI_RUNTIME=1
OPENSWARM_EXPERIMENTAL_DAG_TASK_RUNTIME=1
```

Endpoint:

```http
POST /api/swarms/{swarm_id}/experimental/run-task/{task_id}
```

Payload:

```json
{
  "model": "qwen2.5-coder:14b",
  "base_url": "http://localhost:11434",
  "allowed_tools": ["Read", "Write", "Edit", "SearchFiles", "SearchText"],
  "max_turns": 8,
  "workspace_path": "C:/temp/openswarm-dag-task"
}
```

How to get `task_id`:

```powershell
Invoke-RestMethod http://127.0.0.1:8324/api/swarms/<swarm_id>/tasks
```

Pick the MVP task titled `Create README.md`.

Run in-process TestClient smoke without Ollama:

```powershell
python -m backend.apps.agents.runtime.smoke_experimental_dag_task_testclient
```

Run HTTP smoke for one DAG task:

PowerShell:

```powershell
$env:OPENSWARM_EXPERIMENTAL_MINI_RUNTIME="1"
$env:OPENSWARM_EXPERIMENTAL_DAG_TASK_RUNTIME="1"
$env:OPENSWARM_SMOKE_BACKEND_URL="http://127.0.0.1:8324"
$env:OPENSWARM_SMOKE_OLLAMA_MODEL="qwen2.5-coder:14b"
$env:OLLAMA_BASE_URL="http://localhost:11434"
python -m backend.apps.agents.runtime.smoke_experimental_dag_task_ollama
```

Git Bash:

```bash
export OPENSWARM_EXPERIMENTAL_MINI_RUNTIME=1
export OPENSWARM_EXPERIMENTAL_DAG_TASK_RUNTIME=1
export OPENSWARM_SMOKE_BACKEND_URL=http://127.0.0.1:8324
export OPENSWARM_SMOKE_OLLAMA_MODEL=qwen2.5-coder:14b
export OLLAMA_BASE_URL=http://localhost:11434
python -m backend.apps.agents.runtime.smoke_experimental_dag_task_ollama
```

Current limits:

- Runs exactly one selected task.
- Does not execute dependency ordering.
- Does not auto-run reviewer.
- Does not consolidate final result.
- Does not touch AgentManager or the existing Ollama inline loop.
- Safe tools only; no run_command/destructive tools.

## Experimental Worker -> Reviewer chain

This endpoint runs only:

1. `Create README.md`
2. `Review README.md`

It does not run `Consolidate final evidence` and does not traverse arbitrary DAG
dependencies.

Required backend flags:

```text
OPENSWARM_EXPERIMENTAL_MINI_RUNTIME=1
OPENSWARM_EXPERIMENTAL_DAG_TASK_RUNTIME=1
OPENSWARM_EXPERIMENTAL_DAG_CHAIN_RUNTIME=1
```

Endpoint:

```http
POST /api/swarms/{swarm_id}/experimental/run-worker-review
```

Payload:

```json
{
  "model": "qwen2.5-coder:14b",
  "base_url": "http://localhost:11434",
  "allowed_tools": ["Read", "Write", "Edit", "SearchFiles", "SearchText"],
  "max_turns": 8,
  "workspace_path": "C:/temp/openswarm-worker-review"
}
```

Behavior:

- Worker writes `README.md` via ToolRuntime.
- Worker registers artifact + `submit_artifact`.
- Coordinator/request path registers `request_review`.
- Reviewer receives the artifact as structured input.
- Reviewer is required to use `Read` on `README.md`.
- Reviewer persists `review_result` in task evidence/validations and sends it to Coordinator.
- Consolidation remains `pending`.

Run in-process smoke without Ollama:

```powershell
python -m backend.apps.agents.runtime.smoke_experimental_worker_review_testclient
```

Run real HTTP/Ollama smoke:

```powershell
$env:OPENSWARM_EXPERIMENTAL_MINI_RUNTIME="1"
$env:OPENSWARM_EXPERIMENTAL_DAG_TASK_RUNTIME="1"
$env:OPENSWARM_EXPERIMENTAL_DAG_CHAIN_RUNTIME="1"
$env:OPENSWARM_SMOKE_BACKEND_URL="http://127.0.0.1:8324"
$env:OPENSWARM_SMOKE_OLLAMA_MODEL="qwen2.5-coder:14b"
$env:OLLAMA_BASE_URL="http://localhost:11434"
python -m backend.apps.agents.runtime.smoke_experimental_worker_review_ollama
```

Current limits:

- Only the README Worker/Reviewer pair is detected.
- Reviewer approval is accepted only if the Reviewer completed and ToolRuntime history includes `Read` for `README.md`.
- No final consolidation yet.
- No AgentManager/Ollama inline/Claude SDK changes.

## Experimental final consolidation

This endpoint performs deterministic consolidation after Worker + Reviewer have
already completed. It does not call Ollama and does not execute new tools.

Required backend flags:

```text
OPENSWARM_EXPERIMENTAL_MINI_RUNTIME=1
OPENSWARM_EXPERIMENTAL_DAG_TASK_RUNTIME=1
OPENSWARM_EXPERIMENTAL_DAG_CHAIN_RUNTIME=1
OPENSWARM_EXPERIMENTAL_DAG_CONSOLIDATE_RUNTIME=1
```

Endpoint:

```http
POST /api/swarms/{swarm_id}/experimental/consolidate-final
```

Payload:

```json
{}
```

Behavior:

- Requires `Create README.md` completed.
- Requires `Review README.md` completed.
- Requires `README.md` artifact.
- Requires approved `review_result`.
- Builds `swarm.final_evidence` from artifact, review result, task statuses, and tool history.
- Persists `swarm.final_result`.
- Marks `Consolidate final evidence` as `completed`.
- Marks the experimental swarm state as `completed`.

Run in-process smoke without Ollama:

```powershell
python -m backend.apps.agents.runtime.smoke_experimental_consolidate_testclient
```

Run real HTTP/Ollama smoke:

```powershell
$env:OPENSWARM_EXPERIMENTAL_MINI_RUNTIME="1"
$env:OPENSWARM_EXPERIMENTAL_DAG_TASK_RUNTIME="1"
$env:OPENSWARM_EXPERIMENTAL_DAG_CHAIN_RUNTIME="1"
$env:OPENSWARM_EXPERIMENTAL_DAG_CONSOLIDATE_RUNTIME="1"
$env:OPENSWARM_SMOKE_BACKEND_URL="http://127.0.0.1:8324"
$env:OPENSWARM_SMOKE_OLLAMA_MODEL="qwen2.5-coder:14b"
$env:OLLAMA_BASE_URL="http://localhost:11434"
python -m backend.apps.agents.runtime.smoke_experimental_consolidate_ollama
```

Current limits:

- Consolidation is deterministic and specific to the README DAG slice.
- It does not run arbitrary DAG dependencies.
- It does not create a natural-language final answer through a provider yet.
- No AgentManager/Ollama inline/Claude SDK changes.

## Experimental automatic README mini-DAG

This endpoint runs the validated README slice in one call:

`Create README.md -> Review README.md -> Consolidate final evidence`

It is still not a generic DAG runner. It reuses the existing experimental
Worker/Reviewer chain and deterministic consolidator.

Required backend flags:

```text
OPENSWARM_EXPERIMENTAL_MINI_RUNTIME=1
OPENSWARM_EXPERIMENTAL_DAG_TASK_RUNTIME=1
OPENSWARM_EXPERIMENTAL_DAG_CHAIN_RUNTIME=1
OPENSWARM_EXPERIMENTAL_DAG_CONSOLIDATE_RUNTIME=1
OPENSWARM_EXPERIMENTAL_DAG_MINI_RUNNER=1
```

Endpoint:

```http
POST /api/swarms/{swarm_id}/experimental/run-mini-dag
```

Payload:

```json
{
  "model": "qwen2.5-coder:14b",
  "base_url": "http://localhost:11434",
  "allowed_tools": ["Read", "Write", "Edit", "SearchFiles", "SearchText"],
  "max_turns": 8,
  "workspace_path": "C:/temp/openswarm-mini-dag"
}
```

Behavior:

- Loads existing SwarmState.
- If Worker + Reviewer already completed with approved review, it skips rerunning them.
- Otherwise runs the existing Worker -> Reviewer chain.
- Runs deterministic final consolidation.
- Returns tasks, artifacts, messages, tool_history, final_result, and final_evidence.

Run in-process smoke without Ollama:

```powershell
python -m backend.apps.agents.runtime.smoke_experimental_mini_dag_testclient
```

Run real HTTP/Ollama smoke:

```powershell
$env:OPENSWARM_EXPERIMENTAL_MINI_RUNTIME="1"
$env:OPENSWARM_EXPERIMENTAL_DAG_TASK_RUNTIME="1"
$env:OPENSWARM_EXPERIMENTAL_DAG_CHAIN_RUNTIME="1"
$env:OPENSWARM_EXPERIMENTAL_DAG_CONSOLIDATE_RUNTIME="1"
$env:OPENSWARM_EXPERIMENTAL_DAG_MINI_RUNNER="1"
$env:OPENSWARM_SMOKE_BACKEND_URL="http://127.0.0.1:8324"
$env:OPENSWARM_SMOKE_OLLAMA_MODEL="qwen2.5-coder:14b"
$env:OLLAMA_BASE_URL="http://localhost:11434"
python -m backend.apps.agents.runtime.smoke_experimental_mini_dag_ollama
```

Current limits:

- README DAG only.
- No generic dependency scheduler yet.
- Plan task is not executed by a planner provider yet.
- No AgentManager/Ollama inline/Claude SDK changes.

## Experimental dependency-ordered README DAG

This endpoint walks `TaskNode.depends_on` and executes only known safe README
task types:

- `plan_reused`
- `create_readme`
- `review_readme`
- `consolidate_final`

Unknown task types fail closed. This is still not a generic open-ended DAG
orchestrator.

Required backend flags:

```text
OPENSWARM_EXPERIMENTAL_MINI_RUNTIME=1
OPENSWARM_EXPERIMENTAL_DAG_TASK_RUNTIME=1
OPENSWARM_EXPERIMENTAL_DAG_CHAIN_RUNTIME=1
OPENSWARM_EXPERIMENTAL_DAG_CONSOLIDATE_RUNTIME=1
OPENSWARM_EXPERIMENTAL_DAG_MINI_RUNNER=1
OPENSWARM_EXPERIMENTAL_DAG_DEPENDENCY_RUNNER=1
```

Optional PlannerAgent execution:

```text
OPENSWARM_EXPERIMENTAL_PLANNER_AGENT_RUNTIME=1
```

When enabled, `Plan task DAG` is executed through MiniAgentRuntime +
OllamaAdapter as a strict PlannerAgent. When disabled, the runner keeps the
previous deterministic `plan_reused` behavior.

Endpoint:

```http
POST /api/swarms/{swarm_id}/experimental/run-dag-dependencies
```

Payload:

```json
{
  "model": "qwen2.5-coder:14b",
  "base_url": "http://localhost:11434",
  "allowed_tools": ["Read", "Write", "Edit", "SearchFiles", "SearchText"],
  "max_turns": 8,
  "workspace_path": "C:/temp/openswarm-dag-dependencies"
}
```

Behavior:

- Sorts tasks topologically using `depends_on`.
- Marks the existing plan task as reused with evidence, or runs a strict PlannerAgent when `OPENSWARM_EXPERIMENTAL_PLANNER_AGENT_RUNTIME=1`.
- Executes `create_readme` through MiniAgentRuntime + OllamaAdapter.
- Executes `review_readme` through MiniAgentRuntime + OllamaAdapter and requires `Read`.
- Executes deterministic final consolidation.
- Skips already completed tasks only when their evidence is valid.
- Re-running should not duplicate artifacts or messages.

PlannerAgent contract:

- Receives the current DAG as structured input.
- May only return `plan_validated` or `plan_rejected`.
- May not create, delete, reorder, rename, or modify tasks.
- May not modify `depends_on`.
- If rejected or unparsable, the runner fails closed before Worker execution.

Run in-process smoke without Ollama:

```powershell
python -m backend.apps.agents.runtime.smoke_experimental_dag_dependency_testclient
```

Run real HTTP/Ollama smoke:

```powershell
$env:OPENSWARM_EXPERIMENTAL_MINI_RUNTIME="1"
$env:OPENSWARM_EXPERIMENTAL_DAG_TASK_RUNTIME="1"
$env:OPENSWARM_EXPERIMENTAL_DAG_CHAIN_RUNTIME="1"
$env:OPENSWARM_EXPERIMENTAL_DAG_CONSOLIDATE_RUNTIME="1"
$env:OPENSWARM_EXPERIMENTAL_DAG_MINI_RUNNER="1"
$env:OPENSWARM_EXPERIMENTAL_DAG_DEPENDENCY_RUNNER="1"
$env:OPENSWARM_EXPERIMENTAL_PLANNER_AGENT_RUNTIME="1"
$env:OPENSWARM_SMOKE_BACKEND_URL="http://127.0.0.1:8324"
$env:OPENSWARM_SMOKE_OLLAMA_MODEL="qwen2.5-coder:14b"
$env:OLLAMA_BASE_URL="http://localhost:11434"
python -m backend.apps.agents.runtime.smoke_experimental_dag_dependency_ollama
```

Current limits:

- Only the README DAG task types above are accepted.
- PlannerAgent is strict validation-only; it cannot mutate the DAG yet.
- No generic arbitrary task executor.
- No AgentManager/Ollama inline/Claude SDK changes.

## Experimental PolicyRuntime and ApprovalRuntime

F.3.3 status: OK.

Summary:
- PolicyRuntime decides whether a tool call is allowed, denied, or requires approval.
- ToolRuntime does not execute denied tools.
- ToolRuntime does not execute tools that are waiting for approval.
- ApprovalRuntime stores experimental approvals per swarm.
- `allow` records the decision but does not execute the tool.
- `deny` records the decision and blocks execution.
- `resume` executes an allowed approval once.
- `resume` does not re-enter the provider loop.
- `resume` does not automatically mark the task as completed.

Endpoints:
```text
GET  /api/swarms/{swarm_id}/experimental/approvals
GET  /api/swarms/{swarm_id}/experimental/approvals/{approval_id}
POST /api/swarms/{swarm_id}/experimental/approvals/{approval_id}/allow
POST /api/swarms/{swarm_id}/experimental/approvals/{approval_id}/deny
POST /api/swarms/{swarm_id}/experimental/approvals/{approval_id}/resume
```

Statuses:
- `pending`
- `allowed`
- `denied`
- `resumed`
- `resume_failed`

`updated_input` note:
- `updated_input` is stored in the decision.
- `resume` currently executes the original `tool_input`.
- Do not change this behavior without explicit smoke coverage.

Future UI checklist:
- show approval status
- show tool name and original input
- show stored `updated_input` when present
- allow approve/deny actions
- allow resume only after approval
- show events, tool history, and resume result


## Safe task type addition pattern

Every new experimental task type must be added one at a time and must fail closed.
Do not add it to the base README DAG unless that is explicitly required later.

Required steps for each safe task type:

1. Add a registry entry in `experimental_task_type_registry.py` with matcher, safe allowed tools, output contract, and evidence expectations.
2. Add one explicit runner branch in `experimental_dag_dependency_runner.py`; do not execute arbitrary task titles or free-form types.
3. Keep tool execution inside `ToolRuntime`; do not call provider tools directly.
4. Persist deterministic evidence on the `TaskNode` and normalized `tool_history` on `SwarmState`.
5. Make reruns idempotent or duplicate-safe.
6. Add a TestClient smoke.
7. Add an HTTP/Ollama smoke only when it can remain isolated and feature-flagged.

### `inspect_readme`

`inspect_readme` is a safe experimental task type that runs only when the current
`SwarmState` explicitly contains an `Inspect README.md` task. It is not part of
the default README review DAG.

Allowed tool:

```text
Read
```

Evidence contract:

```json
{
  "kind": "readme_inspection",
  "path": "README.md",
  "bytes": 123,
  "line_count": 3,
  "has_title": true
}
```

Run TestClient smoke:

```powershell
python -m backend.apps.agents.runtime.smoke_experimental_inspect_readme_testclient
```

Run HTTP smoke against a real backend:

```powershell
$env:OPENSWARM_EXPERIMENTAL_MINI_RUNTIME="1"
$env:OPENSWARM_EXPERIMENTAL_DAG_TASK_RUNTIME="1"
$env:OPENSWARM_EXPERIMENTAL_DAG_CHAIN_RUNTIME="1"
$env:OPENSWARM_EXPERIMENTAL_DAG_CONSOLIDATE_RUNTIME="1"
$env:OPENSWARM_EXPERIMENTAL_DAG_MINI_RUNNER="1"
$env:OPENSWARM_EXPERIMENTAL_DAG_DEPENDENCY_RUNNER="1"
$env:OPENSWARM_EXPERIMENTAL_PLANNER_AGENT_RUNTIME="0"
$env:OPENSWARM_SMOKE_BACKEND_URL="http://127.0.0.1:8324"
python -m backend.apps.agents.runtime.smoke_experimental_inspect_readme_ollama
```

PlannerAgent must stay disabled for this inspect-only smoke because the current
real PlannerAgent contract validates the full README review DAG, not a custom
`Plan task DAG -> Inspect README.md` DAG.

