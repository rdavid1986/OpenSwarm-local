"""Provider-independent Tool Runtime facade.

Phase 6 goal:
- Describe and resolve OpenSwarm tools through one boundary.
- Reuse existing builtin/MCP registries.
- Do not execute tools yet and do not reroute AgentManager.

Execution is introduced incrementally. Builtin filesystem Read/Write are
available through this runtime for the Swarm MVP; Claude SDK hooks, MCP
subprocesses, browser tools, InvokeAgent, and the legacy Ollama inline loop keep
their current execution paths until they are migrated deliberately.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import fnmatch
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from backend.apps.tools_lib.models import BUILTIN_TOOLS
from backend.apps.tools_lib.tools_lib import (
    _load_all as load_all_tools,
    _sanitize_server_name,
    load_builtin_permissions,
)
from backend.apps.agents.runtime.events import EventTraceRuntime, event_trace_runtime
from backend.apps.agents.runtime.policies import PolicyRuntime, policy_runtime
from backend.apps.agents.runtime.approvals import ApprovalRuntime, approval_runtime


ToolKind = Literal["builtin", "mcp"]
ToolPolicy = Literal["always_allow", "ask", "deny"]
ToolStatus = Literal["completed", "failed", "denied", "approval_required", "unsupported"]


@dataclass(frozen=True)
class ToolSpec:
    """Normalized tool descriptor exposed to provider adapters."""

    name: str
    kind: ToolKind
    description: str = ""
    category: str = "general"
    policy: ToolPolicy = "always_allow"
    deferred: bool = False
    server_name: str | None = None
    raw_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolResolution:
    """Result of resolving a provider-proposed tool name."""

    found: bool
    tool: ToolSpec | None = None
    reason: str | None = None


@dataclass(frozen=True)
class ToolCall:
    """Normalized provider/runtime tool call."""

    name: str
    input: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid4().hex)
    provider_call_id: str | None = None
    raw_name: str | None = None


@dataclass(frozen=True)
class ToolExecutionContext:
    """Context needed to execute a tool safely and traceably."""

    workspace_path: str
    session_id: str | None = None
    swarm_id: str | None = None
    agent_id: str | None = None
    task_id: str | None = None
    active_mcps: list[str] | None = None
    allowed_tools: list[str] | None = None
    require_human_approval: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolResult:
    """Normalized result returned by ToolRuntime."""

    call_id: str
    tool_name: str
    status: ToolStatus
    ok: bool
    result: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    stdout: str | None = None
    stderr: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_history_entry(self) -> dict[str, Any]:
        return {
            "call_id": self.call_id,
            "tool": self.tool_name,
            "status": self.status,
            "ok": self.ok,
            "result": self.result,
            "error": self.error,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            **self.metadata,
        }


def _now_iso() -> str:
    from datetime import datetime

    return datetime.now().isoformat()


class ToolRuntime:
    """Facade over existing OpenSwarm tool definitions and minimal execution."""

    def __init__(
        self,
        *,
        events: EventTraceRuntime | None = None,
        policies: PolicyRuntime | None = None,
        approvals: ApprovalRuntime | None = None,
    ) -> None:
        self._builtin_by_name = {tool.name: tool for tool in BUILTIN_TOOLS}
        self.events = events or event_trace_runtime
        self.policies = policies or policy_runtime
        self.approvals = approvals or approval_runtime

    @staticmethod
    def _normalize_policy(value: Any, default: ToolPolicy = "always_allow") -> ToolPolicy:
        if value in ("always_allow", "ask", "deny"):
            return value
        return default

    def list_builtin_tools(self) -> list[ToolSpec]:
        perms = load_builtin_permissions()
        specs: list[ToolSpec] = []
        for tool in BUILTIN_TOOLS:
            specs.append(
                ToolSpec(
                    name=tool.name,
                    kind="builtin",
                    description=tool.description,
                    category=tool.category,
                    policy=self._normalize_policy(perms.get(tool.name, "always_allow")),
                    deferred=tool.deferred,
                    raw_name=tool.name,
                )
            )
        return specs

    def list_mcp_tools(self, *, active_mcps: list[str] | None = None) -> list[ToolSpec]:
        """Return MCP sub-tools known to OpenSwarm.

        If active_mcps is provided, only active MCP servers are returned. This
        mirrors the existing activation gate without changing it.
        """
        active_set = set(active_mcps) if active_mcps is not None else None
        specs: list[ToolSpec] = []
        for tool in load_all_tools():
            if not (tool.mcp_config and tool.enabled and tool.auth_status in ("configured", "connected")):
                continue
            server_name = _sanitize_server_name(tool.name)
            if active_set is not None and server_name not in active_set:
                continue

            descriptions = tool.tool_permissions.get("_tool_descriptions", {})
            if not isinstance(descriptions, dict):
                descriptions = {}

            for subtool_name, description in descriptions.items():
                if str(subtool_name).startswith("_"):
                    continue
                policy = self._normalize_policy(tool.tool_permissions.get(subtool_name, "ask"), default="ask")
                specs.append(
                    ToolSpec(
                        name=f"mcp__{server_name}__{subtool_name}",
                        kind="mcp",
                        description=str(description or ""),
                        category="mcp",
                        policy=policy,
                        deferred=False,
                        server_name=server_name,
                        raw_name=str(subtool_name),
                        metadata={
                            "tool_definition_id": tool.id,
                            "tool_definition_name": tool.name,
                            "auth_status": tool.auth_status,
                            "connected_account_email": tool.connected_account_email,
                        },
                    )
                )
        return specs

    def list_tools(self, *, active_mcps: list[str] | None = None) -> list[ToolSpec]:
        return [*self.list_builtin_tools(), *self.list_mcp_tools(active_mcps=active_mcps)]

    def resolve_tool(self, name: str, *, active_mcps: list[str] | None = None) -> ToolResolution:
        if not name:
            return ToolResolution(found=False, reason="tool name is required")
        synthetic_specs = {
            "SearchFiles": ToolSpec(
                name="SearchFiles",
                kind="builtin",
                description="Search files by name or glob pattern inside the workspace",
                category="search",
                raw_name="SearchFiles",
            ),
            "SearchText": ToolSpec(
                name="SearchText",
                kind="builtin",
                description="Search text inside workspace files",
                category="search",
                raw_name="SearchText",
            ),
        }
        if name in synthetic_specs:
            return ToolResolution(found=True, tool=synthetic_specs[name])

        for spec in self.list_tools(active_mcps=active_mcps):
            if spec.name == name or spec.raw_name == name:
                if spec.policy == "deny":
                    return ToolResolution(found=True, tool=spec, reason="tool policy is deny")
                return ToolResolution(found=True, tool=spec)

        return ToolResolution(found=False, reason=f"unknown tool: {name}")

    def build_provider_tool_schemas(self, *, active_mcps: list[str] | None = None) -> list[dict[str, Any]]:
        """Return simple provider-facing schemas.

        This intentionally avoids executing or validating arguments. It gives
        adapters a common vocabulary while real execution stays behind the
        existing runtime until later phases.
        """
        schemas: list[dict[str, Any]] = []
        for spec in self.list_tools(active_mcps=active_mcps):
            if spec.policy == "deny":
                continue
            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": spec.name,
                        "description": spec.description,
                        "parameters": {
                            "type": "object",
                            "properties": {},
                            "additionalProperties": True,
                        },
                    },
                    "x-openswarm": {
                        "kind": spec.kind,
                        "category": spec.category,
                        "policy": spec.policy,
                        "server_name": spec.server_name,
                        "deferred": spec.deferred,
                    },
                }
            )
        return schemas

    def execute_tool(
        self,
        call: ToolCall,
        context: ToolExecutionContext,
        *,
        history: list[dict[str, Any]] | None = None,
    ) -> ToolResult:
        """Execute a normalized tool call.

        Phase scope is intentionally narrow: core filesystem/search tools use the shared
        execution path; all other tool families return "unsupported" so their
        existing AgentManager/SDK/MCP execution remains untouched.
        """

        started_at = _now_iso()
        resolution = self.resolve_tool(call.name, active_mcps=context.active_mcps)
        decision = self.policies.evaluate_tool_call(
            resolution=resolution,
            context=context,
            requested_tool_name=call.name,
        )
        decision_metadata = self._policy_metadata(context, decision)
        if not decision.allowed:
            metadata = {**self._metadata(context), **decision_metadata}
            if decision.requires_approval:
                approval_request = self.approvals.create_request(
                    tool_name=decision.tool_name or call.name,
                    tool_input=call.input,
                    workspace_path=context.workspace_path,
                    session_id=context.session_id,
                    swarm_id=context.swarm_id,
                    agent_id=context.agent_id,
                    task_id=context.task_id,
                    reason=decision.reason,
                    metadata={
                        "tool_call_id": call.id,
                        "provider_call_id": call.provider_call_id,
                        "raw_name": call.raw_name,
                        "provider_tool_format": context.metadata.get("provider_tool_format"),
                        "task_type": context.metadata.get("task_type"),
                        "allowed_tools": list(context.allowed_tools or []),
                        "policy_decision": getattr(decision, "status", None),
                    },
                    emit_event=False,
                )
                metadata = {
                    **metadata,
                    "approval_request_id": approval_request.id,
                    "approval_request": approval_request.to_dict(),
                }

            return self._finalize_result(
                ToolResult(
                    call_id=call.id,
                    tool_name=decision.tool_name or call.name,
                    status="approval_required" if decision.requires_approval else "denied",
                    ok=False,
                    error=decision.reason or "tool policy denied execution",
                    started_at=started_at,
                    completed_at=_now_iso(),
                    metadata=metadata,
                ),
                history=history,
            )

        spec = resolution.tool
        if spec is None:
            return self._finalize_result(
                ToolResult(
                    call_id=call.id,
                    tool_name=call.name,
                    status="denied",
                    ok=False,
                    error="tool resolution missing after policy allow",
                    started_at=started_at,
                    completed_at=_now_iso(),
                    metadata={**self._metadata(context), **decision_metadata},
                ),
                history=history,
            )

        self._event("tool_approved", context, {"tool": spec.name, "input": call.input, **decision_metadata})
        self._event("tool_started", context, {"tool": spec.name, "input": call.input})
        try:
            if spec.kind != "builtin":
                result = ToolResult(
                    call_id=call.id,
                    tool_name=spec.name,
                    status="unsupported",
                    ok=False,
                    error="MCP execution remains on existing AgentManager/SDK path",
                    started_at=started_at,
                    completed_at=_now_iso(),
                    metadata=self._metadata(context),
                )
            elif spec.name == "Write":
                result = self._execute_write(call, context, spec.name, started_at)
            elif spec.name == "Read":
                result = self._execute_read(call, context, spec.name, started_at)
            elif spec.name == "Edit":
                result = self._execute_edit(call, context, spec.name, started_at)
            elif spec.name == "Glob":
                result = self._execute_search_files(call, context, spec.name, started_at)
            elif spec.name == "Grep":
                result = self._execute_search_text(call, context, spec.name, started_at)
            elif spec.name in ("SearchFiles", "SearchText"):
                result = (
                    self._execute_search_files(call, context, spec.name, started_at)
                    if spec.name == "SearchFiles"
                    else self._execute_search_text(call, context, spec.name, started_at)
                )
            else:
                result = ToolResult(
                    call_id=call.id,
                    tool_name=spec.name,
                    status="unsupported",
                    ok=False,
                    error=f"Builtin tool execution not migrated yet: {spec.name}",
                    started_at=started_at,
                    completed_at=_now_iso(),
                    metadata=self._metadata(context),
                )
        except Exception as exc:
            result = ToolResult(
                call_id=call.id,
                tool_name=spec.name,
                status="failed",
                ok=False,
                error=str(exc),
                started_at=started_at,
                completed_at=_now_iso(),
                metadata=self._metadata(context),
            )

        result = replace(result, metadata={**result.metadata, **decision_metadata})
        return self._finalize_result(result, history=history)

    def _execute_write(
        self,
        call: ToolCall,
        context: ToolExecutionContext,
        tool_name: str,
        started_at: str,
    ) -> ToolResult:
        relative_path = self._required_str(call.input, "path")
        content = call.input.get("content", "")
        if not isinstance(content, str):
            raise ValueError("content must be a string")

        target = self._safe_workspace_path(context.workspace_path, relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return ToolResult(
            call_id=call.id,
            tool_name=tool_name,
            status="completed",
            ok=True,
            result={
                "path": relative_path,
                "absolute_path": str(target),
                "bytes": len(content.encode("utf-8")),
            },
            started_at=started_at,
            completed_at=_now_iso(),
            metadata=self._metadata(context),
        )

    def _execute_edit(
        self,
        call: ToolCall,
        context: ToolExecutionContext,
        tool_name: str,
        started_at: str,
    ) -> ToolResult:
        relative_path = self._required_str(call.input, "path")
        old_text = call.input.get("old_text")
        new_text = call.input.get("new_text")
        replace_all = bool(call.input.get("replace_all", False))
        if not isinstance(old_text, str) or old_text == "":
            raise ValueError("old_text must be a non-empty string")
        if not isinstance(new_text, str):
            raise ValueError("new_text must be a string")

        target = self._safe_workspace_path(context.workspace_path, relative_path)
        if not target.exists():
            raise FileNotFoundError(f"file not found: {relative_path}")
        if not target.is_file():
            raise ValueError(f"not a file: {relative_path}")

        content = target.read_text(encoding="utf-8", errors="replace")
        occurrences = content.count(old_text)
        if occurrences == 0:
            raise ValueError("old_text not found")
        if occurrences > 1 and not replace_all:
            raise ValueError("old_text appears more than once; use replace_all=true or a more specific old_text")

        updated = content.replace(old_text, new_text) if replace_all else content.replace(old_text, new_text, 1)
        replaced = occurrences if replace_all else 1
        target.write_text(updated, encoding="utf-8")
        return ToolResult(
            call_id=call.id,
            tool_name=tool_name,
            status="completed",
            ok=True,
            result={
                "path": relative_path,
                "absolute_path": str(target),
                "replaced": replaced,
                "bytes": len(updated.encode("utf-8")),
            },
            started_at=started_at,
            completed_at=_now_iso(),
            metadata=self._metadata(context),
        )

    def _execute_search_files(
        self,
        call: ToolCall,
        context: ToolExecutionContext,
        tool_name: str,
        started_at: str,
    ) -> ToolResult:
        base_path = call.input.get("path", ".")
        if not isinstance(base_path, str):
            raise ValueError("path must be a string")
        pattern = call.input.get("pattern") or call.input.get("glob") or call.input.get("query")
        if not isinstance(pattern, str) or not pattern.strip():
            raise ValueError("pattern must be a non-empty string")
        max_results = int(call.input.get("max_results", 100) or 100)
        max_results = max(1, min(max_results, 1000))

        workspace = Path(context.workspace_path).expanduser().resolve()
        target = self._safe_workspace_path(str(workspace), base_path)
        if not target.exists():
            raise FileNotFoundError(f"path not found: {base_path}")

        lowered = pattern.lower()
        has_glob_meta = any(ch in pattern for ch in "*?[]")
        items = [target] if target.is_file() else sorted(target.rglob("*"))
        matches: list[dict[str, Any]] = []

        for item in items:
            if len(matches) >= max_results:
                break
            try:
                rel = item.relative_to(workspace)
            except ValueError:
                continue
            if self._is_ignored(rel):
                continue
            rel_text = str(rel).replace("\\", "/")
            matched = (
                fnmatch.fnmatch(rel_text, pattern)
                or fnmatch.fnmatch(item.name, pattern)
                if has_glob_meta
                else lowered in rel_text.lower() or lowered in item.name.lower()
            )
            if matched:
                matches.append({"path": rel_text + ("/" if item.is_dir() else ""), "type": "dir" if item.is_dir() else "file"})

        return ToolResult(
            call_id=call.id,
            tool_name=tool_name,
            status="completed",
            ok=True,
            result={
                "path": str(target.relative_to(workspace)).replace("\\", "/") if target != workspace else ".",
                "pattern": pattern,
                "matches": matches,
                "count": len(matches),
                "truncated": len(matches) >= max_results,
            },
            started_at=started_at,
            completed_at=_now_iso(),
            metadata=self._metadata(context),
        )

    def _execute_search_text(
        self,
        call: ToolCall,
        context: ToolExecutionContext,
        tool_name: str,
        started_at: str,
    ) -> ToolResult:
        base_path = call.input.get("path", ".")
        if not isinstance(base_path, str):
            raise ValueError("path must be a string")
        query = call.input.get("query") or call.input.get("pattern")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")
        max_results = int(call.input.get("max_results", 50) or 50)
        max_results = max(1, min(max_results, 1000))
        max_file_chars = int(call.input.get("max_file_chars", 300000) or 300000)
        max_file_chars = max(1000, min(max_file_chars, 2_000_000))

        workspace = Path(context.workspace_path).expanduser().resolve()
        target = self._safe_workspace_path(str(workspace), base_path)
        if not target.exists():
            raise FileNotFoundError(f"path not found: {base_path}")

        files = self._files_to_scan(target, workspace, max_files=1000)
        lowered_query = query.lower()
        matches: list[dict[str, Any]] = []

        for file_path in files:
            if len(matches) >= max_results:
                break
            try:
                if file_path.stat().st_size > max_file_chars:
                    continue
                content = file_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            for line_number, line in enumerate(content.splitlines(), start=1):
                if lowered_query in line.lower():
                    matches.append(
                        {
                            "path": str(file_path.relative_to(workspace)).replace("\\", "/"),
                            "line": line_number,
                            "text": line.strip()[:500],
                        }
                    )
                    if len(matches) >= max_results:
                        break

        return ToolResult(
            call_id=call.id,
            tool_name=tool_name,
            status="completed",
            ok=True,
            result={
                "path": str(target.relative_to(workspace)).replace("\\", "/") if target != workspace else ".",
                "query": query,
                "matches": matches,
                "count": len(matches),
                "truncated": len(matches) >= max_results,
            },
            started_at=started_at,
            completed_at=_now_iso(),
            metadata=self._metadata(context),
        )

    def _execute_read(
        self,
        call: ToolCall,
        context: ToolExecutionContext,
        tool_name: str,
        started_at: str,
    ) -> ToolResult:
        relative_path = self._required_str(call.input, "path")
        max_chars = int(call.input.get("max_chars", 120000) or 120000)
        target = self._safe_workspace_path(context.workspace_path, relative_path)
        if not target.exists():
            raise FileNotFoundError(f"file not found: {relative_path}")
        if not target.is_file():
            raise ValueError(f"not a file: {relative_path}")
        content = target.read_text(encoding="utf-8", errors="replace")
        return ToolResult(
            call_id=call.id,
            tool_name=tool_name,
            status="completed",
            ok=True,
            result={
                "path": relative_path,
                "absolute_path": str(target),
                "content": content[:max_chars],
                "truncated": len(content) > max_chars,
                "bytes": len(content.encode("utf-8")),
            },
            started_at=started_at,
            completed_at=_now_iso(),
            metadata=self._metadata(context),
        )

    def _finalize_result(self, result: ToolResult, *, history: list[dict[str, Any]] | None) -> ToolResult:
        if result.status == "completed":
            event_type = "tool_completed"
        elif result.status == "denied":
            event_type = "tool_denied"
        elif result.status == "approval_required":
            event_type = "approval_required"
        else:
            event_type = "tool_failed"

        self._event(event_type, self._context_from_metadata(result.metadata), result.to_history_entry())
        if history is not None:
            history.append(result.to_history_entry())
        return result

    @staticmethod
    def _required_str(data: dict[str, Any], key: str) -> str:
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} must be a non-empty string")
        return value

    @staticmethod
    def _safe_workspace_path(workspace_path: str, relative_path: str) -> Path:
        workspace = Path(workspace_path).expanduser().resolve()
        if Path(relative_path).is_absolute():
            raise ValueError("absolute paths are not allowed")
        target = (workspace / relative_path).resolve()
        target.relative_to(workspace)
        return target

    @staticmethod
    def _is_ignored(relative_path: Path) -> bool:
        ignored_dirs = {".git", "node_modules", "dist", "build", ".next", ".venv", "__pycache__"}
        return bool(set(relative_path.parts).intersection(ignored_dirs))

    def _files_to_scan(self, target: Path, workspace: Path, *, max_files: int) -> list[Path]:
        if target.is_file():
            return [target]
        files: list[Path] = []
        for item in sorted(target.rglob("*")):
            if len(files) >= max_files:
                break
            if not item.is_file():
                continue
            try:
                rel = item.relative_to(workspace)
            except ValueError:
                continue
            if self._is_ignored(rel):
                continue
            files.append(item)
        return files

    @staticmethod
    def _metadata(context: ToolExecutionContext) -> dict[str, Any]:
        return {
            "session_id": context.session_id,
            "swarm_id": context.swarm_id,
            "agent_id": context.agent_id,
            "task_id": context.task_id,
            "workspace_path": context.workspace_path,
            **context.metadata,
        }

    @staticmethod
    def _policy_metadata(context: ToolExecutionContext, decision: Any) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "policy_decision": getattr(decision, "status", None),
            "policy_reason": getattr(decision, "reason", None),
        }
        task_type = context.metadata.get("task_type")
        if task_type:
            metadata["task_type"] = task_type
        return metadata

    @staticmethod
    def _context_from_metadata(metadata: dict[str, Any]) -> ToolExecutionContext:
        return ToolExecutionContext(
            workspace_path=str(metadata.get("workspace_path") or "."),
            session_id=metadata.get("session_id"),
            swarm_id=metadata.get("swarm_id"),
            agent_id=metadata.get("agent_id"),
            task_id=metadata.get("task_id"),
        )

    def _event(self, event_type: str, context: ToolExecutionContext, payload: dict[str, Any]) -> None:
        self.events.create(
            event_type,
            session_id=context.session_id,
            swarm_id=context.swarm_id,
            agent_id=context.agent_id,
            task_id=context.task_id,
            payload=payload,
        )


tool_runtime = ToolRuntime()
