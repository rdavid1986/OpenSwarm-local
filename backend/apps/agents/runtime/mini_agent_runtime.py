"""Mini Agent Runtime.

A minimal, isolated task runtime that connects AgentContract + TaskNode to a
ProviderAdapter through ProviderTurnHarness. It deliberately does not touch
AgentManager, Claude SDK routing, or the current Ollama inline loop.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from backend.apps.agents.orchestration.models import AgentContract, TaskNode, _now_iso
from backend.apps.agents.orchestration.store import SwarmStore, swarm_store
from backend.apps.agents.runtime.provider import ProviderAdapter, ProviderTurnContext
from backend.apps.agents.runtime.provider_turn_harness import ProviderTurnHarness, ProviderTurnHarnessResult
from backend.apps.agents.runtime.tools import ToolRuntime, tool_runtime
from backend.apps.agents.runtime.mini_agent_prompt_context import build_mini_agent_system_prompt

MiniAgentStatus = Literal["completed", "failed"]


@dataclass(frozen=True)
class MiniAgentRuntimeContext:
    contract: AgentContract
    task: TaskNode
    provider: ProviderAdapter
    workspace_path: str
    model: str = "fake"
    provider_tool_format: Literal["ollama", "openai_compatible"] = "ollama"
    session_id: str | None = None
    swarm_id: str | None = None
    inputs: dict[str, Any] = field(default_factory=dict)
    store: SwarmStore | None = None
    max_turns: int = 8


@dataclass(frozen=True)
class MiniAgentRuntimeResult:
    status: MiniAgentStatus
    task_id: str
    agent_contract_id: str
    final_message: dict[str, Any] | None
    tool_history: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    provider_events: list[dict[str, Any]] = field(default_factory=list)
    turns: int = 0
    persisted: bool = False


class MiniAgentRuntime:
    def __init__(self, *, tools: ToolRuntime | None = None, store: SwarmStore | None = None) -> None:
        self.tools = tools or tool_runtime
        self.store = store or swarm_store

    def build_initial_messages_from_contract(
        self,
        *,
        contract: AgentContract,
        task: TaskNode,
        inputs: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        safe_inputs = inputs or {}
        content = "\n".join(
            [
                f"Role: {contract.role}",
                f"Agent objective: {contract.objective}",
                f"Task: {task.title}",
                f"Task objective: {task.objective}",
                f"Allowed tools: {', '.join(contract.allowed_tools) if contract.allowed_tools else 'none'}",
                "Acceptance criteria:",
                *[f"- {item}" for item in contract.acceptance_criteria],
                "Output contract:",
                str(contract.output_contract or {}),
                "Inputs:",
                str(safe_inputs),
                "\nUse tools only when needed and return a concise final answer with evidence.",
            ]
        )
        return [{"role": "user", "content": content}]

    async def run_agent_task(self, context: MiniAgentRuntimeContext) -> MiniAgentRuntimeResult:
        messages = self.build_initial_messages_from_contract(
            contract=context.contract,
            task=context.task,
            inputs=context.inputs,
        )
        system_prompt = build_mini_agent_system_prompt(
            contract=context.contract,
            task=context.task,
            inputs=context.inputs,
        )
        harness = ProviderTurnHarness(
            provider=context.provider,
            provider_tool_format=context.provider_tool_format,
        )
        turn_result = await harness.run_until_final(
            context=ProviderTurnContext(
                session_id=context.session_id or f"mini-{context.task.id}",
                model=context.model,
                messages=messages,
                system_prompt=system_prompt,
                agent_id=context.contract.id,
                runtime_state=self._provider_runtime_state(context),
                task_id=context.task.id,
                tools=self._provider_tool_schemas(context.contract.allowed_tools),
                metadata=self._provider_metadata(context),
            ),
            workspace_path=context.workspace_path,
            max_turns=context.max_turns,
        )
        result = self._to_result(context, turn_result)
        if context.swarm_id and context.store:
            result = self.persist_runtime_result(context, result)
        return result

    def _provider_tool_schemas(self, allowed_tools: list[str]) -> list[dict[str, Any]]:
        schemas = self.tools.build_provider_tool_schemas(active_mcps=[])
        if not allowed_tools:
            return []
        allowed = set(allowed_tools)
        return [
            schema for schema in schemas
            if ((schema.get("function") or {}).get("name") in allowed)
        ]

    def persist_runtime_result(
        self,
        context: MiniAgentRuntimeContext,
        result: MiniAgentRuntimeResult,
    ) -> MiniAgentRuntimeResult:
        store = context.store or self.store
        swarm = store.load(context.swarm_id or "")
        for task in swarm.tasks:
            if task.id != context.task.id:
                continue
            task.status = "completed" if result.status == "completed" else "failed"
            task.evidence.extend(result.evidence)
            task.errors.extend(result.errors)
            task.updated_at = _now_iso()
            for entry in result.tool_history:
                path = (entry.get("result") or {}).get("path")
                if path and path not in task.touched_files:
                    task.touched_files.append(path)
            break
        swarm.tool_history.extend(result.tool_history)
        if result.final_message:
            swarm.messages.append(
                self._message(
                    "send_message_to_agent",
                    context.contract.id,
                    task_id=context.task.id,
                    payload={"final_message": result.final_message, "status": result.status},
                )
            )
        store.save(swarm)
        return MiniAgentRuntimeResult(
            status=result.status,
            task_id=result.task_id,
            agent_contract_id=result.agent_contract_id,
            final_message=result.final_message,
            tool_history=result.tool_history,
            evidence=result.evidence,
            errors=result.errors,
            provider_events=result.provider_events,
            turns=result.turns,
            persisted=True,
        )

    @staticmethod
    def _to_result(
        context: MiniAgentRuntimeContext,
        turn_result: ProviderTurnHarnessResult,
    ) -> MiniAgentRuntimeResult:
        tool_errors = [entry for entry in turn_result.tool_history if not entry.get("ok")]
        errors = [*turn_result.errors]
        for entry in tool_errors:
            errors.append({"type": "tool_error", "tool": entry.get("tool"), "status": entry.get("status"), "error": entry.get("error")})

        if turn_result.status == "max_turns_exceeded":
            status: MiniAgentStatus = "failed"
        elif turn_result.status == "failed":
            status = "failed"
        elif errors:
            status = "failed"
        else:
            status = "completed"

        successful_tools = [entry for entry in turn_result.tool_history if entry.get("ok")]
        failed_tools = [entry for entry in turn_result.tool_history if not entry.get("ok")]
        attempted_tools = [
            {
                "tool": entry.get("tool"),
                "status": entry.get("status"),
                "ok": bool(entry.get("ok")),
                "path": (entry.get("result") or {}).get("path"),
            }
            for entry in turn_result.tool_history
        ]
        evidence = [
            {
                "kind": "mini_agent_runtime",
                "evidence_contract_version": "mini_agent_runtime.v1",
                "status": status,
                "turns": turn_result.turns,
                "has_final_message": turn_result.final_message is not None,
                "final_message": turn_result.final_message,
                "tool_count": len(turn_result.tool_history),
                "successful_tool_count": len(successful_tools),
                "failed_tool_count": len(failed_tools),
                "error_count": len(errors),
                "planned_work": {
                    "task_id": context.task.id,
                    "task_title": context.task.title,
                    "task_objective": context.task.objective,
                    "agent_contract_id": context.contract.id,
                    "agent_role": context.contract.role,
                    "acceptance_criteria": list(context.contract.acceptance_criteria or []),
                },
                "attempted_work": {
                    "tools": attempted_tools,
                    "turns": turn_result.turns,
                    "provider_event_count": len(turn_result.provider_events),
                },
                "completed_work": {
                    "final_message_available": turn_result.final_message is not None,
                    "successful_tools": [entry.get("tool") for entry in successful_tools],
                },
                "failed_work": {
                    "errors": errors,
                    "failed_tools": [entry.get("tool") for entry in failed_tools],
                },
            }
        ]
        for entry in turn_result.tool_history:
            evidence.append({"kind": "tool_result", "tool": entry.get("tool"), "history_entry": entry})

        return MiniAgentRuntimeResult(
            status=status,
            task_id=context.task.id,
            agent_contract_id=context.contract.id,
            final_message=turn_result.final_message,
            tool_history=turn_result.tool_history,
            evidence=evidence,
            errors=errors,
            provider_events=turn_result.provider_events,
            turns=turn_result.turns,
            persisted=False,
        )

    @staticmethod
    def _message(message_type: str, from_agent_id: str, **kwargs):
        from backend.apps.agents.orchestration.models import AgentToAgentMessage

        return AgentToAgentMessage(type=message_type, from_agent_id=from_agent_id, **kwargs)

    @staticmethod
    def _provider_runtime_state(context: MiniAgentRuntimeContext) -> dict[str, Any]:
        return {
            "runtime": "mini_agent_runtime",
            "task_id": context.task.id,
            "task_type": getattr(context.task, "task_type", None),
            "task_title": context.task.title,
            "task_status": getattr(context.task, "status", None),
            "agent_contract_id": context.contract.id,
            "agent_role": context.contract.role,
            "assigned_contract_id": getattr(context.task, "assigned_contract_id", None),
            "allowed_tools": list(context.contract.allowed_tools or []),
            "workspace_path": context.workspace_path,
            "swarm_id": context.swarm_id,
            "acceptance_criteria": list(context.contract.acceptance_criteria or []),
            "output_contract": dict(context.contract.output_contract or {}),
            "inputs_keys": sorted(str(key) for key in (context.inputs or {}).keys()),
            "provider_tool_format": context.provider_tool_format,
        }

    @staticmethod
    def _provider_metadata(context: MiniAgentRuntimeContext) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "allowed_tools": list(context.contract.allowed_tools or []),
            "agent_contract_allowed_tools": list(context.contract.allowed_tools or []),
            "provider_tool_format": context.provider_tool_format,
        }
        if context.swarm_id:
            metadata["swarm_id"] = context.swarm_id
        try:
            from backend.apps.agents.runtime.experimental_task_type_registry import experimental_tool_policy_metadata

            metadata.update(experimental_tool_policy_metadata(task=context.task, contract=context.contract))
        except Exception:
            pass
        return metadata


mini_agent_runtime = MiniAgentRuntime()
