from backend.apps.skills.import_policy import evaluate_skill_import_policy
from backend.apps.skills.import_preview import build_skill_import_preview_report


def assert_policy_never_installs_or_executes(policy):
    assert policy["can_install_skill"] is False
    assert policy["can_execute_source"] is False
    assert policy["can_activate_tools"] is False
    assert policy["can_activate_mcp"] is False


def _safe_report(source_format="claude_skill"):
    return build_skill_import_preview_report({
        "source_format": source_format,
        "source_author": "Known Author",
        "source_license": "MIT",
        "source_url": "file://prepared/SKILL.md",
        "name": "Safe Skill",
        "content": "# Safe Skill\nFollow a review workflow.",
    })


def test_safe_claude_preview_allows_candidate_preview():
    policy = evaluate_skill_import_policy(_safe_report("claude_skill"))

    assert policy["ok"] is True
    assert policy["decision"] == "allow_candidate_preview"
    assert policy["risk_level"] == "low"
    assert policy["can_create_candidate"] is True
    assert_policy_never_installs_or_executes(policy)


def test_safe_openswarm_preview_allows_candidate_preview():
    policy = evaluate_skill_import_policy(_safe_report("openswarm_skillspec"))

    assert policy["decision"] == "allow_candidate_preview"
    assert policy["can_create_candidate"] is True
    assert_policy_never_installs_or_executes(policy)


def test_unknown_format_needs_review_and_no_candidate_auto():
    report = build_skill_import_preview_report({
        "source_format": "unknown",
        "source_author": "Known Author",
        "source_license": "MIT",
        "content": "# Unknown",
    })

    policy = evaluate_skill_import_policy(report)

    assert policy["decision"] == "needs_review"
    assert policy["can_create_candidate"] is False
    assert any(reason["code"] == "unknown_source_format" for reason in policy["reasons"])
    assert_policy_never_installs_or_executes(policy)


def test_secret_blocks_policy():
    report = build_skill_import_preview_report({
        "source_format": "claude_skill",
        "source_author": "Known Author",
        "source_license": "MIT",
        "content": "API_KEY=sk-1234567890abcdef",
    })

    policy = evaluate_skill_import_policy(report)

    assert policy["decision"] == "blocked"
    assert policy["risk_level"] == "critical"
    assert policy["can_create_candidate"] is False
    assert any(reason["code"] == "possible_secret_material" for reason in policy["reasons"])
    assert_policy_never_installs_or_executes(policy)


def test_dangerous_instruction_blocks_policy():
    report = build_skill_import_preview_report({
        "source_format": "codex_instruction",
        "source_author": "Known Author",
        "source_license": "MIT",
        "content": "run this command: rm -rf /",
    })

    policy = evaluate_skill_import_policy(report)

    assert policy["decision"] == "blocked"
    assert any(reason["code"] == "dangerous_execution_instruction" for reason in policy["reasons"])
    assert_policy_never_installs_or_executes(policy)


def test_tools_and_mcp_require_review():
    report = build_skill_import_preview_report({
        "source_format": "claude_skill",
        "source_author": "Known Author",
        "source_license": "MIT",
        "name": "Tool Skill",
        "content": "# Tool Skill",
        "required_tools": ["Read"],
        "required_mcp_servers": ["docs"],
    })

    policy = evaluate_skill_import_policy(report)

    assert policy["decision"] == "needs_review"
    assert policy["can_create_candidate"] is False
    assert {reason["code"] for reason in policy["reasons"]} >= {"required_tools_declared", "required_mcp_servers_declared"}
    assert_policy_never_installs_or_executes(policy)


def test_unknown_author_or_license_needs_review():
    report = build_skill_import_preview_report({
        "source_format": "claude_skill",
        "content": "# Missing metadata",
    })

    policy = evaluate_skill_import_policy(report)

    assert policy["decision"] == "needs_review"
    assert policy["can_create_candidate"] is False
    assert {reason["code"] for reason in policy["reasons"]} >= {"source_license_unknown", "source_author_unknown"}
    assert_policy_never_installs_or_executes(policy)
