from pathlib import Path

from backend.apps.agents.orchestration.models import EvidenceRecord, SwarmState
from backend.apps.outputs.models import Output, OutputIterationRecord
from backend.apps.swarms.workspace_intelligence import build_output_version_freshness, build_workspace_intelligence


def _workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / ".openswarm" / "workspaces" / "pm1"
    workspace.mkdir(parents=True)
    (workspace / "index.html").write_text("<html><body>PM-1</body></html>", encoding="utf-8")
    (workspace / "styles.css").write_text("body { color: #111; }", encoding="utf-8")
    (workspace / "content.json").write_text('{"title":"PM-1"}', encoding="utf-8")
    return workspace


def _output_from_workspace(workspace: Path) -> Output:
    return Output(
        name="PM-1 Output",
        files={
            "index.html": (workspace / "index.html").read_text(encoding="utf-8"),
            "styles.css": (workspace / "styles.css").read_text(encoding="utf-8"),
            "content.json": (workspace / "content.json").read_text(encoding="utf-8"),
        },
        source_swarm_id="swarm-1",
        source_task_id="task-1",
        artifact_refs=["artifact-1"],
        evidence_refs=["evidence-output-1"],
        validation_status="passed",
    )


def test_workspace_intelligence_returns_hashes_sizes_and_mtime(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workspace = _workspace(tmp_path)

    snapshot = build_workspace_intelligence(workspace_path=str(workspace))

    assert snapshot["exists"] is True
    assert snapshot["freshness"] == "unknown"
    files = {item["path"]: item for item in snapshot["files"]}
    assert set(files) == {"index.html", "styles.css", "content.json"}
    assert files["index.html"]["exists"] is True
    assert files["index.html"]["size"] > 0
    assert len(files["index.html"]["sha256"]) == 64
    assert files["index.html"]["mtime"] is not None
    assert files["index.html"]["freshness"] == "unknown"


def test_workspace_intelligence_marks_fresh_when_output_matches(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workspace = _workspace(tmp_path)
    output = _output_from_workspace(workspace)

    snapshot = build_workspace_intelligence(workspace_path=str(workspace), output=output)

    assert snapshot["freshness"] == "fresh"
    assert snapshot["output"]["id"] == output.id
    assert snapshot["output"]["source_swarm_id"] == "swarm-1"
    assert snapshot["output"]["source_task_id"] == "task-1"
    assert snapshot["output"]["artifact_refs"] == ["artifact-1"]
    assert snapshot["output"]["evidence_refs"] == ["evidence-output-1"]
    assert snapshot["output"]["validation_status"] == "passed"
    assert {item["freshness"] for item in snapshot["files"]} == {"fresh"}


def test_workspace_intelligence_marks_stale_when_workspace_differs_from_output(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workspace = _workspace(tmp_path)
    output = _output_from_workspace(workspace)
    (workspace / "index.html").write_text("<html><body>changed</body></html>", encoding="utf-8")

    snapshot = build_workspace_intelligence(workspace_path=str(workspace), output=output)

    files = {item["path"]: item for item in snapshot["files"]}
    assert snapshot["freshness"] == "stale"
    assert files["index.html"]["freshness"] == "stale"
    assert files["styles.css"]["freshness"] == "fresh"


def test_workspace_intelligence_marks_missing_required_file(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workspace = _workspace(tmp_path)
    (workspace / "content.json").unlink()

    snapshot = build_workspace_intelligence(workspace_path=str(workspace))

    files = {item["path"]: item for item in snapshot["files"]}
    assert snapshot["freshness"] == "missing"
    assert files["content.json"]["exists"] is False
    assert files["content.json"]["freshness"] == "missing"


def test_workspace_intelligence_reports_outside_root_without_reading(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "index.html").write_text("secret", encoding="utf-8")

    snapshot = build_workspace_intelligence(workspace_path=str(outside))

    assert snapshot["exists"] is False
    assert snapshot["freshness"] == "unknown"
    assert snapshot["errors"][0]["error"] == "workspace_outside_allowed_root"
    assert all(item["sha256"] is None for item in snapshot["files"])


def test_workspace_intelligence_rejects_symlink_outside_workspace(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workspace = _workspace(tmp_path)
    (workspace / "content.json").unlink()
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    try:
        (workspace / "content.json").symlink_to(outside)
    except OSError:
        return

    snapshot = build_workspace_intelligence(workspace_path=str(workspace))

    assert snapshot["freshness"] == "missing"
    assert any(error["error"] == "symlink_outside_workspace" for error in snapshot["errors"])
    files = {item["path"]: item for item in snapshot["files"]}
    assert files["content.json"]["exists"] is False


def test_workspace_intelligence_rejects_path_traversal_allowed_file(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workspace = _workspace(tmp_path)

    snapshot = build_workspace_intelligence(
        workspace_path=str(workspace),
        allowed_files={"../secret.txt"},
    )

    assert snapshot["freshness"] == "missing"
    assert any(error["error"] == "path_traversal_not_allowed" for error in snapshot["errors"])


def test_workspace_intelligence_includes_swarm_artifacts_and_evidence_refs(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workspace = _workspace(tmp_path)
    swarm = SwarmState(title="Swarm", user_prompt="Build", workspace_path=str(workspace))
    swarm.artifacts.append({"id": "artifact-1", "path": "index.html"})
    swarm.evidence.append(
        EvidenceRecord(
            id="evidence-1",
            kind="file_read",
            tool_call_id="read-1",
            file_path="index.html",
        )
    )
    swarm.final_evidence.append({"evidence_ref": "final-ref-1", "kind": "artifact"})
    output = _output_from_workspace(workspace)

    snapshot = build_workspace_intelligence(swarm=swarm, output=output)

    assert snapshot["artifacts"] == [{"id": "artifact-1", "path": "index.html"}]
    assert snapshot["evidence_refs"] == ["evidence-output-1", "evidence-1", "final-ref-1"]


def test_workspace_intelligence_resolves_workspace_from_output_id(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workspace = tmp_path / ".openswarm" / "workspaces" / "output-ws"
    workspace.mkdir(parents=True)
    (workspace / "index.html").write_text("<html><body>Output WS</body></html>", encoding="utf-8")
    (workspace / "styles.css").write_text("body { color: #222; }", encoding="utf-8")
    (workspace / "content.json").write_text('{"title":"Output WS"}', encoding="utf-8")

    output = Output(
        id="out-ws",
        name="Output Workspace",
        workspace_id="output-ws",
        files={
            "index.html": (workspace / "index.html").read_text(encoding="utf-8"),
            "styles.css": (workspace / "styles.css").read_text(encoding="utf-8"),
            "content.json": (workspace / "content.json").read_text(encoding="utf-8"),
        },
        source_swarm_id="swarm-output-ws",
    )

    from backend.apps.swarms import workspace_intelligence as module
    monkeypatch.setattr(module, "load_output", lambda output_id: output)

    snapshot = build_workspace_intelligence(output_id=output.id)

    assert snapshot["exists"] is True
    assert snapshot["workspace_path"] == str(workspace.resolve())
    assert snapshot["freshness"] == "fresh"
    assert snapshot["output"]["id"] == output.id


def test_workspace_intelligence_output_id_missing_workspace_stays_unknown(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    output = Output(
        id="out-no-ws",
        name="Output Without Workspace",
        files={"index.html": "<html></html>"},
    )

    from backend.apps.swarms import workspace_intelligence as module
    monkeypatch.setattr(module, "load_output", lambda output_id: output)

    snapshot = build_workspace_intelligence(output_id=output.id)

    assert snapshot["exists"] is False
    assert snapshot["workspace_path"] is None
    assert snapshot["freshness"] == "unknown"
    assert snapshot["errors"][0]["error"] == "workspace_path_missing"


def _write_output_files(workspace: Path, files: dict[str, str]) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    for rel_path, content in files.items():
        (workspace / rel_path).write_text(content, encoding="utf-8")


def _candidate_iteration_for(
    output: Output,
    *,
    base_workspace: Path,
    candidate_workspace: Path,
    files_after: dict[str, str] | None = None,
) -> OutputIterationRecord:
    return OutputIterationRecord(
        output_id=output.id,
        base_workspace_path=str(base_workspace),
        candidate_workspace_path=str(candidate_workspace),
        requested_change="Refine output.",
        files_before=dict(output.files),
        files_after=dict(files_after or output.files),
        status="candidate",
    )


def test_output_version_freshness_is_fresh_for_matching_candidate(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    workspace = tmp_path / ".openswarm" / "workspaces" / "stable"
    base_workspace = tmp_path / ".openswarm" / "workspaces" / "base"
    candidate_workspace = tmp_path / ".openswarm" / "workspaces" / "candidate"

    files = {
        "index.html": "<html><body>Fresh</body></html>",
        "styles.css": "body { color: #333; }",
        "content.json": '{"title":"Fresh"}',
    }
    _write_output_files(workspace, files)
    _write_output_files(base_workspace, files)
    _write_output_files(candidate_workspace, files)

    output = Output(id="out-fresh", name="Fresh", workspace_id="stable", files=dict(files))
    candidate = _candidate_iteration_for(output, base_workspace=base_workspace, candidate_workspace=candidate_workspace)

    from backend.apps.swarms import workspace_intelligence as module
    monkeypatch.setattr(module, "load_output", lambda output_id: output)
    monkeypatch.setattr(module, "load_output_iterations", lambda output_id: [candidate])

    snapshot = build_output_version_freshness(output_id=output.id)

    assert snapshot["status"] == "fresh"
    assert snapshot["stable_freshness"] == "fresh"
    assert snapshot["base_freshness"] == "fresh"
    assert snapshot["candidate_freshness"] == "fresh"
    assert snapshot["output_changed_since_candidate"] is False
    assert snapshot["base_matches_files_before"] is True
    assert snapshot["candidate_matches_files_after"] is True
    assert snapshot["errors"] == []


def test_output_version_freshness_detects_output_changed_since_candidate(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    workspace = tmp_path / ".openswarm" / "workspaces" / "stable"
    base_workspace = tmp_path / ".openswarm" / "workspaces" / "base"
    candidate_workspace = tmp_path / ".openswarm" / "workspaces" / "candidate"

    original_files = {
        "index.html": "<html><body>Original</body></html>",
        "styles.css": "body { color: #333; }",
        "content.json": '{"title":"Original"}',
    }
    changed_files = dict(original_files)
    changed_files["content.json"] = '{"title":"Changed"}'

    _write_output_files(workspace, changed_files)
    _write_output_files(base_workspace, original_files)
    _write_output_files(candidate_workspace, original_files)

    output = Output(id="out-changed", name="Changed", workspace_id="stable", files=dict(changed_files))
    candidate = OutputIterationRecord(
        output_id=output.id,
        base_workspace_path=str(base_workspace),
        candidate_workspace_path=str(candidate_workspace),
        requested_change="Refine output.",
        files_before=dict(original_files),
        files_after=dict(original_files),
        status="candidate",
    )

    from backend.apps.swarms import workspace_intelligence as module
    monkeypatch.setattr(module, "load_output", lambda output_id: output)
    monkeypatch.setattr(module, "load_output_iterations", lambda output_id: [candidate])

    snapshot = build_output_version_freshness(output_id=output.id)

    assert snapshot["status"] == "stale"
    assert snapshot["output_changed_since_candidate"] is True
    assert any(error["error"] == "output_changed_since_candidate" for error in snapshot["errors"])


def test_output_version_freshness_detects_candidate_workspace_stale(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    workspace = tmp_path / ".openswarm" / "workspaces" / "stable"
    base_workspace = tmp_path / ".openswarm" / "workspaces" / "base"
    candidate_workspace = tmp_path / ".openswarm" / "workspaces" / "candidate"

    files = {
        "index.html": "<html><body>Stable</body></html>",
        "styles.css": "body { color: #333; }",
        "content.json": '{"title":"Stable"}',
    }
    files_after = dict(files)
    files_after["content.json"] = '{"title":"Candidate"}'

    _write_output_files(workspace, files)
    _write_output_files(base_workspace, files)
    _write_output_files(candidate_workspace, files)
    (candidate_workspace / "content.json").write_text('{"title":"Different"}', encoding="utf-8")

    output = Output(id="out-stale-candidate", name="Candidate", workspace_id="stable", files=dict(files))
    candidate = _candidate_iteration_for(
        output,
        base_workspace=base_workspace,
        candidate_workspace=candidate_workspace,
        files_after=files_after,
    )

    from backend.apps.swarms import workspace_intelligence as module
    monkeypatch.setattr(module, "load_output", lambda output_id: output)
    monkeypatch.setattr(module, "load_output_iterations", lambda output_id: [candidate])

    snapshot = build_output_version_freshness(output_id=output.id)

    assert snapshot["status"] == "stale"
    assert snapshot["candidate_matches_files_after"] is False
    assert snapshot["candidate_freshness"] == "stale"
    assert any(error["error"] == "candidate_workspace_not_fresh" for error in snapshot["errors"])


def test_output_version_freshness_reports_missing_candidate(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    workspace = tmp_path / ".openswarm" / "workspaces" / "stable"
    files = {"index.html": "<html></html>", "styles.css": "", "content.json": "{}"}
    _write_output_files(workspace, files)

    output = Output(id="out-missing-candidate", name="Missing Candidate", workspace_id="stable", files=dict(files))

    from backend.apps.swarms import workspace_intelligence as module
    monkeypatch.setattr(module, "load_output", lambda output_id: output)
    monkeypatch.setattr(module, "load_output_iterations", lambda output_id: [])

    snapshot = build_output_version_freshness(output_id=output.id)

    assert snapshot["status"] == "missing_candidate"
    assert snapshot["errors"][0]["error"] == "candidate_iteration_not_found"


def test_output_version_freshness_accepts_missing_stable_workspace_when_output_matches_candidate_base(
    tmp_path,
    monkeypatch,
):
    from backend.apps.outputs import outputs as outputs_module
    from backend.apps.outputs.models import Output
    from backend.apps.swarms.workspace_intelligence import build_output_version_freshness

    data_dir = tmp_path / "outputs"
    workspace_dir = tmp_path / "outputs_workspace"
    iterations_dir = data_dir / "_iterations"
    data_dir.mkdir(parents=True, exist_ok=True)
    workspace_dir.mkdir(parents=True, exist_ok=True)
    iterations_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(outputs_module, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(outputs_module, "WORKSPACE_DIR", str(workspace_dir))
    monkeypatch.setattr(outputs_module, "ITERATIONS_DIR", str(iterations_dir))

    output = Output(
        id="out-no-stable-workspace",
        name="No stable workspace",
        files={
            "index.html": "<html>Before</html>",
            "styles.css": "body{}",
            "content.json": "{\"title\":\"Before\"}",
        },
        workspace_id=None,
        validation_status="passed",
    )
    outputs_module._save(output)

    candidate = outputs_module._create_candidate_iteration_from_output(
        output=output,
        requested_change="Change title.",
    )
    candidate = outputs_module.apply_candidate_iteration_files(
        iteration_id=candidate.iteration_id,
        requested_change="Change title.",
        file_updates={
            "index.html": "<html>After</html>",
            "content.json": "{\"title\":\"After\"}",
        },
    )

    result = build_output_version_freshness(
        output_id=output.id,
        iteration_id=candidate.iteration_id,
    )

    assert result["output_changed_since_candidate"] is False
    assert result["base_matches_files_before"] is True
    assert result["candidate_matches_files_after"] is True
    assert result["stable_freshness"] == "unknown"
    assert result["base_freshness"] == "fresh"
    assert result["candidate_freshness"] == "fresh"
    assert result["status"] == "fresh"
    assert result["errors"] == []
