from backend.apps.skills.candidate_store import SkillCandidateStore
from backend.apps.skills.import_candidate import build_skill_candidate_from_import_preview
from backend.apps.skills.import_policy import evaluate_skill_import_policy
from backend.apps.skills.import_preview import build_skill_import_preview_report


def _allowed_preview_and_policy():
    preview = build_skill_import_preview_report({
        "source_format": "claude_skill",
        "source_author": "Known Author",
        "source_license": "MIT",
        "source_url": "file://prepared/SKILL.md",
        "name": "Imported Candidate",
        "content": "# Imported Candidate\nUse a safe workflow.",
    })
    policy = evaluate_skill_import_policy(preview)
    assert policy["can_create_candidate"] is True
    return preview, policy


def test_safe_preview_creates_in_memory_skill_candidate():
    preview, policy = _allowed_preview_and_policy()

    candidate = build_skill_candidate_from_import_preview(preview, policy)

    assert candidate.skill_spec.name == "Imported Candidate"
    assert candidate.status == "candidate"
    assert candidate.source == "skill_import"
    assert candidate.source_ref == "file://prepared/SKILL.md"
    assert candidate.install_approved is False
    assert candidate.research_approved is False
    assert candidate.research_evidence == []
    assert candidate.policy_refs == ["skill_import_policy:allow_candidate_preview"]


def test_candidate_is_not_installed_or_approved():
    preview, policy = _allowed_preview_and_policy()

    candidate = build_skill_candidate_from_import_preview(preview, policy)

    assert candidate.status != "installed"
    assert candidate.install_approved is False
    assert candidate.source == "skill_import"


def test_blocked_policy_raises_value_error():
    preview = build_skill_import_preview_report({
        "source_format": "claude_skill",
        "content": "API_KEY=sk-1234567890abcdef",
    })
    policy = evaluate_skill_import_policy(preview)

    try:
        build_skill_candidate_from_import_preview(preview, policy)
    except ValueError as exc:
        assert str(exc) == "skill_import_policy_blocks_candidate_creation"
    else:
        raise AssertionError("expected blocked policy to raise")


def test_build_candidate_does_not_write_store(tmp_path):
    store = SkillCandidateStore(root=tmp_path / "skill_candidates")
    preview, policy = _allowed_preview_and_policy()

    candidate = build_skill_candidate_from_import_preview(preview, policy)

    assert candidate.candidate_id
    assert store.list() == []
    assert not (tmp_path / "skill_candidates").exists()
