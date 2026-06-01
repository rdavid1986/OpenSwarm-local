from backend.apps.skills.import_detection import detect_skill_import_source_format
from backend.apps.skills.import_preview import build_skill_import_preview_report
from backend.apps.skills.import_policy import evaluate_skill_import_policy
from backend.apps.skills.models import SkillSetCandidate


def test_detects_skill_set_from_multiple_skill_md_files():
    result = detect_skill_import_source_format({
        "files": [
            {"path": "skills/frontend/SKILL.md", "content": "---\nname: Frontend\ndescription: UI work\n---\nUse React."},
            {"path": "skills/backend/SKILL.md", "content": "---\nname: Backend\ndescription: API work\n---\nUse FastAPI."},
        ]
    })

    assert result["detected_format"] == "skill_set"
    assert result["can_create_candidate"] is False
    assert result["can_execute_source"] is False


def test_skill_set_preview_preserves_shared_assets_without_installing():
    preview = build_skill_import_preview_report({
        "source_format": "skill_set",
        "source_author": "Example Author",
        "source_license": "MIT",
        "files": [
            {"path": "skills/frontend/SKILL.md", "content": "---\nname: Frontend\ndescription: UI work\n---\nUse React."},
            {"path": "skills/backend/SKILL.md", "content": "---\nname: Backend\ndescription: API work\n---\nUse FastAPI."},
            {"path": "skills/shared/style-guide.md", "content": "Shared design rules."},
        ],
    })

    assert preview["skill_set_summary"]["skill_count"] == 2
    assert preview["skill_set_summary"]["shared_asset_count"] == 1
    assert preview["shared_assets"][0]["preview_only"] is True
    assert preview["can_install_skill"] is False
    assert preview["can_execute_source"] is False
    assert preview["can_activate_tools"] is False
    assert preview["can_activate_mcp"] is False

    policy = evaluate_skill_import_policy(preview)
    assert policy["decision"] == "needs_review"
    assert policy["can_create_candidate"] is False
    assert any(reason["code"] == "skill_set_candidate_requires_review" for reason in policy["reasons"])


def test_adk_agent_framework_is_not_direct_skill_candidate():
    detection = detect_skill_import_source_format({
        "raw_text": "from google.adk.agents import Agent\nroot_agent = Agent(name='coding_agent', tools=[tool])",
    })
    assert detection["detected_format"] == "adk_agent_framework"

    preview = build_skill_import_preview_report({
        "source_format": "adk_agent_framework",
        "source_author": "Example Author",
        "source_license": "Apache-2.0",
        "content": "from google.adk.agents import Agent\nroot_agent = Agent(name='coding_agent', tools=[tool])",
    })
    policy = evaluate_skill_import_policy(preview)

    assert policy["decision"] == "needs_review"
    assert policy["can_create_candidate"] is False
    assert any(reason["code"] == "agent_framework_not_skill_candidate" for reason in policy["reasons"])
    assert preview["can_execute_source"] is False
    assert preview["can_activate_tools"] is False
    assert preview["can_activate_mcp"] is False


def test_skill_set_candidate_model_is_inert_by_default():
    candidate = SkillSetCandidate()

    assert candidate.candidate_kind == "SkillSetCandidate"
    assert candidate.install_approved is False
    assert candidate.skills == []
    assert candidate.shared_assets == []
