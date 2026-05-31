from backend.apps.skills.skill_metrics import (
    build_skill_effectiveness_gate,
    build_skill_effectiveness_metric_record,
    build_skill_effectiveness_summary,
)
from backend.apps.skills.skill_metrics_store import SkillMetricsStore


def test_empty_summary_is_unmeasured_and_safe():
    summary = build_skill_effectiveness_summary([], skill_ref="skill1")

    assert summary["status"] == "unmeasured"
    assert summary["record_count"] == 0
    assert summary["average_score"] is None
    assert summary["can_install_skill"] is False


def test_explicit_records_are_summarized_and_average_ignores_none():
    records = [
        build_skill_effectiveness_metric_record(skill_ref="skill1", outcome="success", score=0.8, evidence_refs=["ev1"], measured=True),
        build_skill_effectiveness_metric_record(skill_ref="skill1", outcome="partial", score=None, measured=False),
        build_skill_effectiveness_metric_record(skill_ref="skill1", outcome="unknown", score=None),
    ]

    summary = build_skill_effectiveness_summary(records, skill_ref="skill1")

    assert summary["record_count"] == 3
    assert summary["measured_count"] == 1
    assert summary["success_count"] == 1
    assert summary["partial_count"] == 1
    assert summary["unknown_count"] == 1
    assert summary["average_score"] == 0.8
    assert summary["evidence_refs"] == ["ev1"]


def test_failing_records_build_failing_gate():
    records = [
        build_skill_effectiveness_metric_record(skill_ref="skill1", outcome="failure", score=0.1, measured=True),
        build_skill_effectiveness_metric_record(skill_ref="skill1", outcome="failure", score=0.2, measured=True),
    ]
    summary = build_skill_effectiveness_summary(records, skill_ref="skill1")
    gate = build_skill_effectiveness_gate(summary)

    assert summary["status"] == "failing"
    assert gate["decision"] == "blocked"
    assert gate["can_promote_candidate"] is False


def test_metrics_store_persists_explicit_records(tmp_path):
    store = SkillMetricsStore(root=tmp_path / "metrics")
    record = build_skill_effectiveness_metric_record(skill_ref="skill1", outcome="success", score=1.0, evidence_refs=["ev1"])

    store.save(record)
    listed = store.list("skill1")

    assert [item["record_id"] for item in listed] == [record["record_id"]]
    assert listed[0]["evidence_refs"] == ["ev1"]
    assert listed[0]["can_execute_source"] is False
