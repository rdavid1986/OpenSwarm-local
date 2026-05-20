import tempfile
from pathlib import Path

from backend.apps.agents.runtime.tools import ToolCall, ToolExecutionContext, tool_runtime


def _ctx(workspace: Path) -> ToolExecutionContext:
    return ToolExecutionContext(
        workspace_path=str(workspace),
        session_id="test-session",
        swarm_id="test-swarm",
        agent_id="test-agent",
        task_id="test-task",
        allowed_tools=["Read", "Write", "Edit", "SearchFiles", "SearchText"],
        metadata={"policy_scope": "test"},
    )


def test_tool_runtime_blocks_absolute_paths():
    workspace = Path(tempfile.mkdtemp(prefix="openswarm-tool-safety-")).resolve()

    result = tool_runtime.execute_tool(
        ToolCall(name="Read", input={"path": str(workspace / "README.md")}),
        _ctx(workspace),
        history=[],
    )

    assert result.ok is False
    assert result.status == "failed"
    assert "absolute paths are not allowed" in str(result.error)


def test_tool_runtime_blocks_parent_traversal_outside_workspace():
    workspace = Path(tempfile.mkdtemp(prefix="openswarm-tool-safety-")).resolve()

    result = tool_runtime.execute_tool(
        ToolCall(name="Write", input={"path": "../outside.txt", "content": "bad"}),
        _ctx(workspace),
        history=[],
    )

    assert result.ok is False
    assert result.status == "failed"


def test_tool_runtime_blocks_ignored_direct_paths():
    workspace = Path(tempfile.mkdtemp(prefix="openswarm-tool-safety-")).resolve()

    result = tool_runtime.execute_tool(
        ToolCall(name="Write", input={"path": ".venv/secret.txt", "content": "bad"}),
        _ctx(workspace),
        history=[],
    )

    assert result.ok is False
    assert result.status == "failed"
    assert "ignored workspace path" in str(result.error)


def test_tool_runtime_allows_normal_workspace_write_and_read():
    workspace = Path(tempfile.mkdtemp(prefix="openswarm-tool-safety-")).resolve()
    history = []

    write_result = tool_runtime.execute_tool(
        ToolCall(name="Write", input={"path": "README.md", "content": "# OK\n"}),
        _ctx(workspace),
        history=history,
    )

    assert write_result.ok is True
    assert (workspace / "README.md").exists()

    read_result = tool_runtime.execute_tool(
        ToolCall(name="Read", input={"path": "README.md"}),
        _ctx(workspace),
        history=history,
    )

    assert read_result.ok is True
    assert read_result.result["content"] == "# OK\n"
