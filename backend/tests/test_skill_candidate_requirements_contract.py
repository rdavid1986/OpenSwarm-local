from copy import deepcopy

from backend.apps.modes.models import Mode
from backend.apps.skills.models import SkillSpec, SkillSpecCandidate
from backend.apps.skills.requirements_contract import build_skill_candidate_requirements_contract
from backend.apps.tools_lib.models import BUILTIN_TOOLS, ToolDefinition


def _candidate(**spec_updates) -> SkillSpecCandidate:
    spec = SkillSpec(name="Contract Test", content="# Contract Test", **spec_updates)
    return SkillSpecCandidate(skill_spec=spec, status="validated", install_approved=False)


def test_candidate_without_requirements_returns_zero_summary_and_does_not_fail():
    candidate = _candidate()

    contract = build_skill_candidate_requirements_contract(candidate, builtin_tools=BUILTIN_TOOLS)

    assert contract["contract_kind"] == "skill_candidate_requirements_contract"
    assert contract["summary"]["declared_tool_count"] == 0
    assert contract["summary"]["declared_mcp_count"] == 0
    assert contract["summary"]["missing_tool_count"] == 0
    assert contract["summary"]["missing_mcp_count"] == 0
    assert contract["tools"] == []
    assert contract["mcp_servers"] == []


def test_required_tools_not_known_are_reported_not_found_without_inventing_availability():
    candidate = _candidate(required_tools=["NotARealTool"])

    contract = build_skill_candidate_requirements_contract(candidate, tools=[], builtin_tools=[])

    assert contract["summary"]["declared_tool_count"] == 1
    assert contract["summary"]["known_tool_count"] == 0
    assert contract["summary"]["missing_tool_count"] == 1
    assert contract["tools"][0]["name"] == "NotARealTool"
    assert contract["tools"][0]["known"] is False
    assert contract["tools"][0]["permission"] == "not_found"
    assert contract["tools"][0]["source"] == "unknown"


def test_helper_does_not_modify_candidate_or_install_approval():
    candidate = _candidate(required_tools=["Read"])
    before = deepcopy(candidate.model_dump(mode="json"))

    contract = build_skill_candidate_requirements_contract(
        candidate,
        builtin_tools=BUILTIN_TOOLS,
        builtin_permissions={"Read": "ask"},
    )

    assert candidate.model_dump(mode="json") == before
    assert candidate.install_approved is False
    assert candidate.status == "validated"
    assert contract["install_approved"] is False


def test_required_mcp_servers_are_declarative_and_read_only():
    candidate = _candidate(required_mcp_servers=["Google Workspace"])
    tool = ToolDefinition(
        name="Google Workspace",
        description="Persisted MCP config",
        mcp_config={"type": "stdio", "command": "server"},
        enabled=True,
        auth_status="expired",
    )

    contract = build_skill_candidate_requirements_contract(candidate, tools=[tool])

    assert contract["summary"]["declared_mcp_count"] == 1
    assert contract["summary"]["known_mcp_count"] == 1
    assert contract["summary"]["blocked_count"] == 1
    assert contract["mcp_servers"][0]["known"] is True
    assert contract["mcp_servers"][0]["activation_state"] == "blocked"
    assert "does not activate MCP" in contract["mcp_servers"][0]["notes"][0]


def test_unknown_mode_and_permission_data_are_marked_unknown():
    candidate = _candidate(required_tools=["CustomTool"])
    tool = ToolDefinition(name="CustomTool", description="Custom action")
    mode = Mode(id="agent", name="Agent", tools=None)

    contract = build_skill_candidate_requirements_contract(candidate, tools=[tool], modes=[mode])

    assert contract["tools"][0]["known"] is True
    assert contract["tools"][0]["permission"] == "unknown"
    assert contract["modes"][0]["mentions_required_tools"] == "unknown"
    assert contract["modes"][0]["allowed_tools_policy"] == "all_actions"
    assert contract["summary"]["unknown_count"] >= 2
