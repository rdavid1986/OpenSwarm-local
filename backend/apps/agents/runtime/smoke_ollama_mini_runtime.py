"""Isolated OllamaAdapter + MiniAgentRuntime smoke.

Default mode is mock and does not require Ollama to be running. Optional real
mode can be enabled with OPENSWARM_SMOKE_REAL_OLLAMA=1.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, AsyncIterator

from backend.apps.agents.orchestration.models import AgentContract, TaskNode
from backend.apps.agents.providers.ollama_adapter import OllamaAdapter
from backend.apps.agents.runtime.mini_agent_runtime import MiniAgentRuntime, MiniAgentRuntimeContext
from backend.apps.agents.runtime.provider import ProviderEvent, ProviderTurnContext


class MockOllamaAdapter(OllamaAdapter):
    """OllamaAdapter-compatible mock using Ollama-native tool call shape."""

    def __init__(self, script: list[dict[str, Any]], **kwargs: Any) -> None:
        super().__init__(allow_network=False, **kwargs)
        self.script = list(script)
        self.calls: list[ProviderTurnContext] = []

    async def run_turn(self, context: ProviderTurnContext) -> AsyncIterator[ProviderEvent]:
        self.calls.append(context)
        item = self.script.pop(0) if self.script else {"message": {"role": "assistant", "content": ""}}
        yield ProviderEvent(
            type="provider_request",
            session_id=context.session_id,
            agent_id=context.agent_id,
            task_id=context.task_id,
            payload={"provider": self.id, "api_mode": self.api_mode, "mock": True},
        )
        for event in self.parse_response_events(item, context):
            yield event


def tool_response(name: str, arguments: dict[str, Any], call_id: str) -> dict[str, Any]:
    return {"message": {"role": "assistant", "content": "", "tool_calls": [{"id": call_id, "function": {"name": name, "arguments": arguments}}]}}


def final_response(content: str) -> dict[str, Any]:
    return {"message": {"role": "assistant", "content": content}}


async def run_mock_smokes() -> None:
    with TemporaryDirectory() as td:
        workspace = Path(td)
        workspace.mkdir(parents=True, exist_ok=True)
        runtime = MiniAgentRuntime()
        worker = AgentContract(role="DocumentationAgent", objective="Work with docs", allowed_tools=["Read", "Write", "Edit", "Grep"])
        task = TaskNode(title="Mock Ollama task", objective="Use one local tool", assigned_contract_id=worker.id)

        write = await runtime.run_agent_task(MiniAgentRuntimeContext(
            contract=worker,
            task=task,
            provider=MockOllamaAdapter([
                tool_response("write_file", {"path": "README.md", "content": "# OpenSwarm MVP\nneedle old\n"}, "ow1"),
                final_response("written"),
            ]),
            workspace_path=str(workspace),
            model="ollama/mock",
        ))
        assert write.status == "completed", write
        assert (workspace / "README.md").exists()

        read = await runtime.run_agent_task(MiniAgentRuntimeContext(
            contract=worker,
            task=task,
            provider=MockOllamaAdapter([tool_response("read_file", {"path": "README.md"}, "or1"), final_response("read")]),
            workspace_path=str(workspace),
            model="ollama/mock",
        ))
        assert read.status == "completed" and any(h["tool"] == "Read" for h in read.tool_history), read

        edit = await runtime.run_agent_task(MiniAgentRuntimeContext(
            contract=worker,
            task=task,
            provider=MockOllamaAdapter([tool_response("edit_file", {"path": "README.md", "old_text": "needle old", "new_text": "needle new"}, "oe1"), final_response("edited")]),
            workspace_path=str(workspace),
            model="ollama/mock",
        ))
        assert edit.status == "completed" and "needle new" in (workspace / "README.md").read_text(encoding="utf-8"), edit

        search_text = await runtime.run_agent_task(MiniAgentRuntimeContext(
            contract=worker,
            task=task,
            provider=MockOllamaAdapter([tool_response("search_text", {"path": ".", "query": "needle new"}, "og1"), final_response("found")]),
            workspace_path=str(workspace),
            model="ollama/mock",
        ))
        assert search_text.status == "completed" and any(h["tool"] == "SearchText" for h in search_text.tool_history), search_text

        missing = await runtime.run_agent_task(MiniAgentRuntimeContext(
            contract=worker,
            task=task,
            provider=MockOllamaAdapter([tool_response("does_not_exist", {}, "om1"), final_response("done with error")]),
            workspace_path=str(workspace),
            model="ollama/mock",
        ))
        assert missing.status == "completed_with_errors", missing

        loop = await runtime.run_agent_task(MiniAgentRuntimeContext(
            contract=worker,
            task=task,
            provider=MockOllamaAdapter([tool_response("write_file", {"path": "loop.txt", "content": "x"}, "ol1")]),
            workspace_path=str(workspace),
            model="ollama/mock",
            max_turns=1,
        ))
        assert loop.status == "failed", loop

    print("mock ollama mini runtime smoke ok")


async def run_real_optional() -> None:
    if os.environ.get("OPENSWARM_SMOKE_REAL_OLLAMA") != "1":
        print("real ollama smoke skipped; set OPENSWARM_SMOKE_REAL_OLLAMA=1 to enable")
        return
    model = os.environ.get("OPENSWARM_SMOKE_OLLAMA_MODEL", "llama3.1")
    adapter = OllamaAdapter(allow_network=True)
    health = adapter.healthcheck(timeout_seconds=2.0)
    if not health.get("ok"):
        print(f"real ollama smoke skipped; healthcheck failed: {health.get('error')}")
        return
    with TemporaryDirectory() as td:
        workspace = Path(td)
        runtime = MiniAgentRuntime()
        contract = AgentContract(
            role="DocumentationAgent",
            objective="Use safe filesystem tools and report evidence.",
            allowed_tools=["Read", "Write", "Edit", "SearchFiles", "SearchText"],
            acceptance_criteria=["README.md exists.", "Final answer cites evidence."],
        )
        task = TaskNode(
            title="Real Ollama write README",
            objective=(
                "Create README.md in the workspace using the available write tool. "
                "Then return final evidence that the file was created."
            ),
            assigned_contract_id=contract.id,
        )
        result = await runtime.run_agent_task(MiniAgentRuntimeContext(
            contract=contract,
            task=task,
            provider=adapter,
            workspace_path=str(workspace),
            model=f"ollama/{model}",
            max_turns=4,
        ))
        readme = workspace / "README.md"
        print(f"real ollama smoke status={result.status} turns={result.turns} readme_exists={readme.exists()}")
        if result.tool_history:
            print("real ollama tool_history=", [(item.get("tool"), item.get("status"), item.get("ok")) for item in result.tool_history])
        if result.errors:
            print("real ollama errors=", result.errors)


async def main() -> None:
    await run_mock_smokes()
    await run_real_optional()


if __name__ == "__main__":
    asyncio.run(main())
