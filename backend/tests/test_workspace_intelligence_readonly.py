from pathlib import Path

from backend.apps.agents.orchestration.models import EvidenceRecord, SwarmState
from backend.apps.outputs.models import Output
from backend.apps.swarms.workspace_intelligence import build_workspace_intelligence


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
