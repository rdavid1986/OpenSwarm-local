import json
from types import SimpleNamespace

from backend.apps.swarms.project_memory import (
    build_project_memory_manifest,
    build_project_memory_from_swarm_state,
    build_project_memory_prompt,
    extract_project_artifacts,
    extract_project_evidence,
    extract_project_iterations,
    extract_project_outputs,
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


def test_project_memory_from_dict_extracts_output_id_from_output_bridge():
    source = {
        "id": "swarm-1",
        "dashboard_id": "dashboard-1",
        "final_result": {
            "output_bridge": {
                "status": "accepted",
                "output_id": "output-1",
                "metadata": {"workspace_id": "workspace-1"},
            },
            "project_intake_state": {
                "generated_plan": {"main_goal": "Crear app visual"},
            },
        },
    }

    manifest = build_project_memory_from_swarm_state(source)

    assert manifest["project_id"] == "dashboard-1"
    assert manifest["swarm_id"] == "swarm-1"
    assert manifest["workspace_id"] == "workspace-1"
    assert manifest["current_goal"] == "Crear app visual"
    assert manifest["outputs"][0]["output_id"] == "output-1"
    assert manifest["outputs"][0]["source"] == "output_bridge"


def test_project_memory_extracts_artifacts_from_final_result_when_present():
    source = {
        "final_result": {
            "artifacts": [
                {"artifact_id": "artifact-1", "kind": "static_app"},
            ]
        }
    }

    assert extract_project_artifacts(source) == [{"artifact_id": "artifact-1", "kind": "static_app"}]
    manifest = build_project_memory_from_swarm_state(source)
    assert manifest["artifacts"] == [{"artifact_id": "artifact-1", "kind": "static_app"}]


def test_project_memory_extracts_evidence_and_claim_guard_only_when_present():
    source = {
        "final_result": {
            "evidence": [{"evidence_id": "evidence-1", "kind": "build"}],
            "claim_guard": {"status": "verified", "evidence_refs": ["evidence-1"]},
        }
    }

    evidence = extract_project_evidence(source)

    assert {"evidence_id": "evidence-1", "kind": "build"} in evidence
    assert {
        "source": "claim_guard",
        "kind": "claim_guard",
        "value": {"evidence_refs": ["evidence-1"], "status": "verified"},
    } in evidence
    assert extract_project_evidence({}) == []


def test_project_memory_does_not_invent_candidate_iterations():
    source = {
        "final_result": {
            "output_bridge": {"status": "accepted", "output_id": "output-1"},
        }
    }

    iterations = extract_project_iterations(source)
    manifest = build_project_memory_from_swarm_state(source)

    assert iterations["candidate_iterations"] == []
    assert manifest["candidate_iterations"] == []
    assert manifest["accepted_iterations"] == []


def test_project_memory_source_extractors_work_with_simple_objects():
    source = SimpleNamespace(
        id="swarm-obj",
        project_id="project-obj",
        user_prompt="Crear dashboard local",
        output_bridge={"status": "accepted", "output_id": "output-obj"},
        artifacts=[{"artifact_id": "artifact-obj"}],
        final_evidence=[{"id": "evidence-obj"}],
        iterations=[
            {"iteration_id": "iter-candidate", "status": "candidate", "candidate_workspace_path": "/tmp/candidate"},
            {"iteration_id": "iter-accepted", "status": "accepted"},
        ],
    )

    manifest = build_project_memory_from_swarm_state(source)

    assert manifest["project_id"] == "project-obj"
    assert manifest["swarm_id"] == "swarm-obj"
    assert manifest["current_goal"] == "Crear dashboard local"
    assert manifest["outputs"][0]["output_id"] == "output-obj"
    assert manifest["artifacts"] == [{"artifact_id": "artifact-obj"}]
    assert manifest["evidence"] == [{"id": "evidence-obj"}]
    assert manifest["candidate_iterations"][0]["iteration_id"] == "iter-candidate"
    assert manifest["accepted_iterations"][0]["iteration_id"] == "iter-accepted"


def test_project_memory_source_extractors_handle_none_without_failing():
    manifest = build_project_memory_from_swarm_state(None)

    assert manifest["outputs"] == []
    assert manifest["artifacts"] == []
    assert manifest["evidence"] == []
    assert manifest["candidate_iterations"] == []
    assert manifest["current_goal"] is None
    assert extract_project_outputs(None) == []
