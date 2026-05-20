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
        allowed_tools=["SafeShell"],
        metadata={"policy_scope": "test", "task_type": "safe_shell_execute"},
    )


def test_safe_shell_allows_python_py_compile_file():
    workspace = Path(tempfile.mkdtemp(prefix="openswarm-safe-shell-")).resolve()
    target = workspace / "ok.py"
    target.write_text("x = 1\n", encoding="utf-8")

    result = tool_runtime.execute_tool(
        ToolCall(name="SafeShell", input={"command": "python -m py_compile ok.py"}),
        _ctx(workspace),
        history=[],
    )

    assert result.ok is True
    assert result.status == "completed"
    assert result.result["command"] == "python -m py_compile ok.py"
    assert result.result["allowed"] is True
    assert result.result["execution_status"] == "executed"
    assert result.result["exit_code"] == 0
    assert result.metadata["executed"] is True
    assert result.metadata["timeout_seconds"] == 30
    assert result.metadata["stdout_truncated"] is False
    assert result.metadata["stderr_truncated"] is False


def test_safe_shell_blocks_rm_rf():
    workspace = Path(tempfile.mkdtemp(prefix="openswarm-safe-shell-")).resolve()

    result = tool_runtime.execute_tool(
        ToolCall(name="SafeShell", input={"command": "rm -rf ."}),
        _ctx(workspace),
        history=[],
    )

    assert result.ok is False
    assert result.status == "failed"
    assert "blocked command pattern" in str(result.error)


def test_safe_shell_blocks_unknown_commands():
    workspace = Path(tempfile.mkdtemp(prefix="openswarm-safe-shell-")).resolve()

    result = tool_runtime.execute_tool(
        ToolCall(name="SafeShell", input={"command": "python script.py"}),
        _ctx(workspace),
        history=[],
    )

    assert result.ok is False
    assert result.status == "failed"
    assert "command is not allowlisted" in str(result.error)


def test_safe_shell_blocks_py_compile_parent_traversal():
    workspace = Path(tempfile.mkdtemp(prefix="openswarm-safe-shell-")).resolve()

    result = tool_runtime.execute_tool(
        ToolCall(name="SafeShell", input={"command": "python -m py_compile ../outside.py"}),
        _ctx(workspace),
        history=[],
    )

    assert result.ok is False
    assert result.status == "failed"
    assert "path escapes workspace" in str(result.error)


def test_safe_shell_blocks_py_compile_ignored_workspace_path():
    workspace = Path(tempfile.mkdtemp(prefix="openswarm-safe-shell-")).resolve()
    ignored = workspace / ".venv"
    ignored.mkdir()
    (ignored / "bad.py").write_text("x = 1\n", encoding="utf-8")

    result = tool_runtime.execute_tool(
        ToolCall(name="SafeShell", input={"command": "python -m py_compile .venv/bad.py"}),
        _ctx(workspace),
        history=[],
    )

    assert result.ok is False
    assert result.status == "failed"
    assert "ignored workspace path" in str(result.error)
