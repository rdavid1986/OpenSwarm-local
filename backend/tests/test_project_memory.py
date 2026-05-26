import json

from backend.apps.swarms.project_memory import (
    build_project_memory_manifest,
    build_project_memory_prompt,
    extract_project_memory_refs,
    normalize_project_memory_entry,
    summarize_project_memory_manifest,
)


def test_project_memory_manifest_stable_with_missing_data():
    manifest = build_project_memory_manifest()

    assert manifest == {
        "project_id": None,
        "swarm_id": None,
        "workspace_id": None,
        "current_goal": None,
        "decisions": [],
        "outputs": [],
        "accepted_iterations": [],
        "candidate_iterations": [],
        "artifacts": [],
        "evidence": [],
        "constraints": [],
        "open_questions": [],
        "last_updated_source": None,
    }


def test_project_memory_manifest_does_not_invent_outputs_evidence_or_artifacts():
    manifest = build_project_memory_manifest(
        project_id="project-1",
        swarm_id="swarm-1",
        current_goal="Crear una landing",
    )

    assert manifest["outputs"] == []
    assert manifest["candidate_iterations"] == []
    assert manifest["accepted_iterations"] == []
    assert manifest["artifacts"] == []
    assert manifest["evidence"] == []


def test_project_memory_manifest_normalizes_lists_and_entries():
    manifest = build_project_memory_manifest(
        decisions=[{"id": "decision-1", "status": "accepted"}, "legacy decision"],
        constraints="usar solo estado real",
        open_questions=["¿Cuál es el público?", ""],
        artifacts=[{"artifact_id": "artifact-1", "kind": "static_app"}],
    )

    assert manifest["decisions"] == [
        {"id": "decision-1", "status": "accepted"},
        {"value": "legacy decision"},
    ]
    assert manifest["constraints"] == ["usar solo estado real"]
    assert manifest["open_questions"] == ["¿Cuál es el público?"]
    assert manifest["artifacts"] == [{"artifact_id": "artifact-1", "kind": "static_app"}]


def test_project_memory_summary_is_short_and_safe():
    manifest = build_project_memory_manifest(
        project_id="project-1",
        swarm_id="swarm-1",
        outputs=[{"id": "output-1"}],
        evidence=[{"id": "evidence-1"}],
    )

    summary = summarize_project_memory_manifest(manifest)

    assert "Project Memory Manifest summary" in summary
    assert "project_id: project-1" in summary
    assert "swarm_id: swarm-1" in summary
    assert "workspace_id: missing" in summary
    assert "outputs=1" in summary
    assert "evidence=1" in summary


def test_project_memory_prompt_marks_missing_and_empty_semantics():
    prompt = build_project_memory_prompt(build_project_memory_manifest(swarm_id="swarm-1"))

    assert "do not invent missing memory" in prompt
    assert "Treat null as missing and [] as empty" in prompt
    assert '"swarm_id": "swarm-1"' in prompt
    assert '"outputs": []' in prompt
    assert '"evidence": []' in prompt


def test_extract_project_memory_refs_returns_only_listed_ids():
    manifest = build_project_memory_manifest(
        decisions=[{"id": "decision-1"}],
        outputs=[{"id": "output-1"}, {"output_id": "output-2"}],
        accepted_iterations=[{"iteration_id": "iter-accepted"}],
        candidate_iterations=[{"candidate_iteration_id": "iter-candidate"}],
        artifacts=[{"artifact_id": "artifact-1"}],
        evidence=[{"id": "evidence-1"}],
    )

    refs = extract_project_memory_refs(manifest)

    assert refs["decision_ids"] == ["decision-1"]
    assert refs["output_ids"] == ["output-1", "output-2"]
    assert refs["accepted_iteration_ids"] == ["iter-accepted"]
    assert refs["candidate_iteration_ids"] == ["iter-candidate"]
    assert refs["artifact_ids"] == ["artifact-1"]
    assert refs["evidence_ids"] == ["evidence-1"]


def test_normalize_project_memory_entry_is_json_safe_and_bounded():
    normalized = normalize_project_memory_entry(
        {
            "long": "x" * 1200,
            "items": list(range(40)),
            "nested": {"b": 2, "a": None},
        }
    )

    assert len(normalized["long"]) == 800
    assert len(normalized["items"]) == 24
    assert normalized["nested"] == {"a": None, "b": 2}
    json.dumps(normalized)
