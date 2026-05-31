from backend.apps.skills.skill_versioning import build_skill_rollback_plan, build_skill_version_history_summary, build_skill_version_snapshot
from backend.apps.skills.skill_version_store import SkillVersionStore


def _candidate(content="# Skill\nUse safely."):
    return {"candidate_id": "cand1", "skill_spec": {"name": "Skill", "command": "skill", "content": content, "provenance": {"source": "test"}}}


def test_snapshot_candidate_creates_stable_hashes():
    snap1 = build_skill_version_snapshot(_candidate(), reason="baseline")
    snap2 = build_skill_version_snapshot(_candidate(), reason="baseline")

    assert snap1["snapshot_kind"] == "skill_version_snapshot"
    assert snap1["content_hash"] == snap2["content_hash"]
    assert snap1["spec_hash"] == snap2["spec_hash"]
    assert snap1["can_install_skill"] is False
    assert snap1["can_execute_source"] is False
    assert snap1["can_activate_tools"] is False
    assert snap1["can_activate_mcp"] is False


def test_snapshot_store_persists_and_lists(tmp_path):
    store = SkillVersionStore(root=tmp_path / "versions")
    snapshot = build_skill_version_snapshot(_candidate())

    saved = store.save(snapshot)
    listed = store.list("cand1")
    loaded = store.load("cand1", snapshot["snapshot_id"])

    assert saved["snapshot_id"] == snapshot["snapshot_id"]
    assert [item["snapshot_id"] for item in listed] == [snapshot["snapshot_id"]]
    assert loaded["content_hash"] == snapshot["content_hash"]


def test_rollback_plan_detects_changed_fields_and_does_not_restore():
    current = build_skill_version_snapshot(_candidate("# Skill\nNew."))
    target = build_skill_version_snapshot(_candidate("# Skill\nOld."))

    plan = build_skill_rollback_plan(current, target)

    assert plan["plan_kind"] == "skill_rollback_plan"
    assert plan["decision"] == "restore_ready"
    assert "content" in plan["changed_fields"]
    assert plan["restore_performed"] is False
    assert plan["can_install_skill"] is False


def test_rollback_plan_blocks_mismatched_snapshots():
    current = build_skill_version_snapshot(_candidate())
    target = build_skill_version_snapshot({"candidate_id": "other", "skill_spec": {"name": "Other", "content": "# Other"}})

    plan = build_skill_rollback_plan(current, target)

    assert plan["decision"] == "blocked"
    assert plan["can_restore"] is False


def test_history_summary_empty_is_safe():
    summary = build_skill_version_history_summary([])

    assert summary["snapshot_count"] == 0
    assert summary["latest_snapshot_id"] == "not_available"
    assert summary["can_install_skill"] is False
