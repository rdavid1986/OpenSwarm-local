from backend.apps.skills.candidate_store import SkillCandidateStore
from backend.apps.skills.models import SkillSpec, SkillSpecCandidate


def test_skill_candidate_store_saves_loads_and_lists_without_installing(tmp_path):
    store = SkillCandidateStore(root=tmp_path / "skill_candidates")
    candidate = SkillSpecCandidate(
        skill_spec=SkillSpec(name="CSS Validator", content="# CSS Validator\n"),
        source="skill_builder",
    )

    saved = store.save(candidate)
    loaded = store.load(saved.candidate_id)
    listed = store.list()

    assert loaded.candidate_id == candidate.candidate_id
    assert loaded.skill_spec.name == "CSS Validator"
    assert loaded.status == "candidate"
    assert loaded.install_approved is False
    assert [item.candidate_id for item in listed] == [candidate.candidate_id]


def test_skill_candidate_store_requires_candidate_id(tmp_path):
    store = SkillCandidateStore(root=tmp_path / "skill_candidates")
    try:
        store.load("")
    except ValueError as exc:
        assert str(exc) == "candidate_id is required"
    else:
        raise AssertionError("Expected ValueError")
