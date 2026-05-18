from backend.apps.agents.runtime import ToolRuntime


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
