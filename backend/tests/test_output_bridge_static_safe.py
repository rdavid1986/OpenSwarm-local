from pathlib import Path

from backend.apps.agents.orchestration.orchestrator import SwarmOrchestrator
from backend.apps.agents.orchestration.store import SwarmStore
from backend.apps.outputs.outputs import build_output_from_workspace


def _workspace(tmp_path):
    workspace = tmp_path / ".openswarm" / "workspaces" / "static-app-test"
    workspace.mkdir(parents=True)
    (workspace / "index.html").write_text(
        "<!doctype html><html><head><link rel='stylesheet' href='styles.css'></head><body><h1>OpenSwarm</h1></body></html>",
        encoding="utf-8",
    )
    (workspace / "styles.css").write_text("body { font-family: sans-serif; }", encoding="utf-8")
    (workspace / "content.json").write_text('{"title":"OpenSwarm"}', encoding="utf-8")
    return workspace


def test_build_output_from_static_workspace_creates_allowlisted_output(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workspace = _workspace(tmp_path)

    output, errors, metadata = build_output_from_workspace(
        workspace_path=str(workspace),
        name="Static App",
        description="Safe static app",
    )

    assert errors == []
    assert output is not None
    assert output.name == "Static App"
    assert sorted(output.files) == ["content.json", "index.html", "styles.css"]
    assert "backend.py" not in output.files
    assert metadata["output_id"] == output.id
    assert sorted(metadata["allowed_files"]) == ["content.json", "index.html", "styles.css"]


def test_build_output_rejects_backend_py(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workspace = _workspace(tmp_path)
    (workspace / "backend.py").write_text("result = {}", encoding="utf-8")

    output, errors, _ = build_output_from_workspace(workspace_path=str(workspace))

    assert output is None
    assert errors[0]["error"] == "backend_py_not_allowed"


def test_build_output_allows_local_script_without_unsafe_patterns(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workspace = _workspace(tmp_path)
    (workspace / "index.html").write_text(
        "<html><body><ul id='items'></ul><script>fetch('content.json').then(r => r.json()).then(() => {})</script></body></html>",
        encoding="utf-8",
    )

    output, errors, _ = build_output_from_workspace(workspace_path=str(workspace))

    assert errors == []
    assert output is not None


def test_build_output_rejects_inner_html(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workspace = _workspace(tmp_path)
    (workspace / "index.html").write_text(
        "<html><body><script>document.querySelector('#items').innerHTML = '<li>x</li>';</script></body></html>",
        encoding="utf-8",
    )

    output, errors, _ = build_output_from_workspace(workspace_path=str(workspace))

    assert output is None
    assert errors[0]["error"] == "unsafe_html_content"


def test_build_output_rejects_workspace_outside_allowed_root(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workspace = tmp_path / "outside"
    workspace.mkdir()
    (workspace / "index.html").write_text("<html></html>", encoding="utf-8")
    (workspace / "styles.css").write_text("", encoding="utf-8")
    (workspace / "content.json").write_text("{}", encoding="utf-8")

    output, errors, _ = build_output_from_workspace(workspace_path=str(workspace))

    assert output is None
    assert errors[0]["error"] == "workspace_outside_allowed_root"


def test_orchestrator_output_bridge_requires_verified_static_app(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    orchestrator = SwarmOrchestrator(SwarmStore(root=tmp_path / "store"))
    workspace = _workspace(tmp_path)

    swarm = orchestrator.create_swarm(
        user_prompt="Implement static app",
        intent="chat",
        workspace_path=str(workspace),
    )
    swarm.final_result = {
        "status": "completed",
        "artifact_kind": "static_app",
        "implementation_performed": True,
        "claim_guard": {"status": "verified"},
    }
    swarm = orchestrator.store.save(swarm)

    updated, errors, metadata = orchestrator.create_output_bridge_from_static_app(
        swarm_id=swarm.id,
        approve=True,
        name="Output Bridge Test",
    )

    assert errors == []
    assert metadata["output_id"]
    assert updated.decisions[-1]["kind"] == "output_bridge_created"
    assert updated.decisions[-1]["status"] == "accepted"


def test_orchestrator_output_bridge_rejects_without_approval(tmp_path):
    orchestrator = SwarmOrchestrator(SwarmStore(root=tmp_path / "store"))
    swarm = orchestrator.create_swarm(user_prompt="Static app", intent="chat")

    _, errors, _ = orchestrator.create_output_bridge_from_static_app(
        swarm_id=swarm.id,
        approve=False,
    )

    assert errors == [{"error": "approval_required"}]


def test_orchestrator_output_bridge_rejects_non_static_final_result(tmp_path):
    orchestrator = SwarmOrchestrator(SwarmStore(root=tmp_path / "store"))
    swarm = orchestrator.create_swarm(user_prompt="Planning only", intent="chat")
    swarm.final_result = {
        "status": "completed",
        "artifact_kind": "implementation_brief",
        "implementation_performed": False,
        "claim_guard": {"status": "verified"},
    }
    swarm = orchestrator.store.save(swarm)

    _, errors, _ = orchestrator.create_output_bridge_from_static_app(
        swarm_id=swarm.id,
        approve=True,
    )

    assert errors[0]["error"] == "source_artifact_kind_not_static_app"
