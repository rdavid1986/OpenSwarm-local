from pathlib import Path

from backend.apps.agents.orchestration.models import SwarmState, TaskNode
from backend.apps.agents.orchestration.store import SwarmStore
from backend.apps.agents.runtime import ToolCall, ToolExecutionContext, ToolRuntime


def test_tool_runtime_lists_builtin_tools_without_execution():
    runtime = ToolRuntime()
    tools = runtime.list_builtin_tools()

    names = {tool.name for tool in tools}

    assert "Read" in names
    assert "Write" in names
    assert "Bash" in names
    assert all(tool.kind == "builtin" for tool in tools)


def test_tool_runtime_resolves_builtin_tool():
    runtime = ToolRuntime()
    result = runtime.resolve_tool("Read")

    assert result.found is True
    assert result.tool is not None
    assert result.tool.name == "Read"
    assert result.tool.kind == "builtin"


def test_tool_runtime_builds_provider_schemas_without_running_tools():
    runtime = ToolRuntime()
    schemas = runtime.build_provider_tool_schemas()

    read_schema = next(schema for schema in schemas if schema["function"]["name"] == "Read")

    assert read_schema["type"] == "function"
    assert read_schema["function"]["parameters"]["additionalProperties"] is True
    assert read_schema["x-openswarm"]["kind"] == "builtin"


def test_tool_runtime_persists_evidence_for_completed_real_tools(tmp_path: Path, monkeypatch):
    import backend.apps.agents.orchestration.store as store_module

    store = SwarmStore(root=tmp_path / "swarms")
    monkeypatch.setattr(store_module, "swarm_store", store)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "existing.txt").write_text("old needle", encoding="utf-8")

    task = TaskNode(title="Evidence task", objective="Exercise real tools")
    swarm = store.save(SwarmState(title="Evidence swarm", user_prompt="test", tasks=[task]))
    context = ToolExecutionContext(
        workspace_path=str(workspace),
        swarm_id=swarm.id,
        task_id=task.id,
        agent_id="agent-1",
        session_id="session-1",
        allowed_tools=["Read", "Write", "Edit", "SearchFiles", "SearchText"],
    )
    runtime = ToolRuntime()

    runtime.execute_tool(ToolCall(name="Read", input={"path": "existing.txt"}, id="read-1"), context)
    runtime.execute_tool(ToolCall(name="Write", input={"path": "created.txt", "content": "hello"}, id="write-created"), context)
    runtime.execute_tool(ToolCall(name="Write", input={"path": "existing.txt", "content": "new needle"}, id="write-modified"), context)
    runtime.execute_tool(ToolCall(name="Edit", input={"path": "existing.txt", "old_text": "new", "new_text": "edited"}, id="edit-1"), context)
    runtime.execute_tool(ToolCall(name="SearchFiles", input={"path": ".", "pattern": "*.txt"}, id="search-files"), context)
    runtime.execute_tool(ToolCall(name="SearchText", input={"path": ".", "query": "edited"}, id="search-text"), context)

    saved = store.load(swarm.id)
    evidence_by_call = {item.tool_call_id: item for item in saved.evidence}

    assert evidence_by_call["read-1"].kind == "file_read"
    assert evidence_by_call["read-1"].action == "read"
    assert evidence_by_call["write-created"].kind == "file_created"
    assert evidence_by_call["write-created"].action == "created"
    assert evidence_by_call["write-modified"].kind == "file_modified"
    assert evidence_by_call["write-modified"].action == "modified"
    assert evidence_by_call["edit-1"].kind == "file_modified"
    assert evidence_by_call["search-files"].kind == "output"
    assert evidence_by_call["search-text"].action == "output"
    assert all(item.event_id for item in saved.evidence)

    task_evidence = saved.tasks[0].evidence
    assert len(task_evidence) == len(saved.evidence)
    assert all(isinstance(item, dict) for item in task_evidence)


def test_tool_runtime_does_not_persist_evidence_for_failed_or_denied_tools(tmp_path: Path, monkeypatch):
    import backend.apps.agents.orchestration.store as store_module

    store = SwarmStore(root=tmp_path / "swarms")
    monkeypatch.setattr(store_module, "swarm_store", store)
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    task = TaskNode(title="Evidence task", objective="No evidence for failures")
    swarm = store.save(SwarmState(title="Evidence swarm", user_prompt="test", tasks=[task]))
    runtime = ToolRuntime()

    runtime.execute_tool(
        ToolCall(name="Read", input={"path": "missing.txt"}, id="failed-read"),
        ToolExecutionContext(
            workspace_path=str(workspace),
            swarm_id=swarm.id,
            task_id=task.id,
            allowed_tools=["Read"],
        ),
    )
    runtime.execute_tool(
        ToolCall(name="Write", input={"path": "denied.txt", "content": "x"}, id="denied-write"),
        ToolExecutionContext(
            workspace_path=str(workspace),
            swarm_id=swarm.id,
            task_id=task.id,
            allowed_tools=["Read"],
        ),
    )

    saved = store.load(swarm.id)
    assert saved.evidence == []
    assert saved.tasks[0].evidence == []
