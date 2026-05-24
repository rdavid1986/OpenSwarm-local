from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.apps.outputs.models import Output
from backend.apps.outputs import outputs as outputs_module


def _client(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    data_dir = tmp_path / "outputs"
    workspace_dir = tmp_path / ".openswarm" / "workspaces"
    iterations_dir = data_dir / "_iterations"

    monkeypatch.setattr(outputs_module, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(outputs_module, "WORKSPACE_DIR", str(workspace_dir))
    monkeypatch.setattr(outputs_module, "ITERATIONS_DIR", str(iterations_dir))

    data_dir.mkdir(parents=True, exist_ok=True)
    workspace_dir.mkdir(parents=True, exist_ok=True)
    iterations_dir.mkdir(parents=True, exist_ok=True)

    app = FastAPI()
    app.include_router(outputs_module.outputs.router, prefix="/api/outputs")
    return TestClient(app)


def test_create_output_iteration_records_base_files_without_mutating_output(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    output = Output(
        name="Demo",
        files={
            "index.html": "<html><body>Before</body></html>",
            "styles.css": "body { margin: 0; }",
            "content.json": '{"title":"Before"}',
        },
        source_swarm_id="swarm-1",
        validation_status="verified",
    )
    outputs_module._save(output)

    stable_workspace = tmp_path / "workspaces" / "stable-ws"
    stable_workspace.mkdir(parents=True, exist_ok=True)
    for rel_path, content in output.files.items():
        (stable_workspace / rel_path).write_text(content, encoding="utf-8")

    response = client.post(
        "/api/outputs/iterations/create",
        json={
            "output_id": output.id,
            "requested_change": "Change title",
            "files_after": {"content.json": '{"title":"After"}'},
            "diff_summary": {"changed": ["content.json"]},
            "evidence_refs": ["ev-1"],
            "validation_refs": ["val-1"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True

    iteration = payload["iteration"]
    assert iteration["output_id"] == output.id
    assert iteration["source_swarm_id"] == "swarm-1"
    assert iteration["status"] == "candidate"
    assert iteration["requested_change"] == "Change title"
    assert iteration["files_before"] == output.files
    assert iteration["files_after"] == {"content.json": '{"title":"After"}'}
    assert iteration["diff_summary"] == {"changed": ["content.json"]}
    assert iteration["evidence_refs"] == ["ev-1"]
    assert iteration["validation_refs"] == ["val-1"]

    unchanged = outputs_module._load(output.id)
    assert unchanged.files == output.files


def test_list_and_get_output_iterations(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    output = Output(name="Demo", files={"index.html": "A"})
    outputs_module._save(output)

    first = client.post(
        "/api/outputs/iterations/create",
        json={"output_id": output.id, "requested_change": "First"},
    ).json()["iteration"]
    second = client.post(
        "/api/outputs/iterations/create",
        json={"output_id": output.id, "requested_change": "Second"},
    ).json()["iteration"]

    listed = client.get(f"/api/outputs/{output.id}/iterations")
    assert listed.status_code == 200
    assert [item["iteration_id"] for item in listed.json()["iterations"]] == [
        first["iteration_id"],
        second["iteration_id"],
    ]

    fetched = client.get(f"/api/outputs/iterations/{first['iteration_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["requested_change"] == "First"


def test_create_candidate_output_iteration_creates_base_and_candidate_workspaces(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    output = Output(
        name="Demo",
        files={
            "index.html": "<html><body>Stable</body></html>",
            "styles.css": "body { margin: 0; }",
            "content.json": '{"title":"Stable"}',
        },
        source_swarm_id="swarm-1",
    )
    outputs_module._save(output)

    response = client.post(
        f"/api/outputs/{output.id}/iterations/candidate",
        json={
            "output_id": output.id,
            "requested_change": "Make the hero clearer",
            "evidence_refs": ["ev-1"],
            "validation_refs": ["val-1"],
        },
    )

    assert response.status_code == 200
    iteration = response.json()["iteration"]

    assert iteration["status"] == "candidate"
    assert iteration["requested_change"] == "Make the hero clearer"
    assert iteration["files_before"] == output.files
    assert iteration["files_after"] == output.files
    assert iteration["diff_summary"] == {"status": "candidate_created", "changed": []}
    assert iteration["base_workspace_path"]
    assert iteration["candidate_workspace_path"]

    base = Path(iteration["base_workspace_path"])
    candidate = Path(iteration["candidate_workspace_path"])

    assert base.is_dir()
    assert candidate.is_dir()
    assert (base / "index.html").read_text(encoding="utf-8") == output.files["index.html"]
    assert (candidate / "index.html").read_text(encoding="utf-8") == output.files["index.html"]
    assert (candidate / "styles.css").read_text(encoding="utf-8") == output.files["styles.css"]
    assert (candidate / "content.json").read_text(encoding="utf-8") == output.files["content.json"]

    unchanged = outputs_module._load(output.id)
    assert unchanged.files == output.files


def test_create_candidate_output_iteration_rejects_output_id_mismatch(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    output = Output(name="Demo", files={"index.html": "A"})
    outputs_module._save(output)

    response = client.post(
        f"/api/outputs/{output.id}/iterations/candidate",
        json={"output_id": "different-output", "requested_change": "Nope"},
    )

    assert response.status_code == 400


def test_accept_output_iteration_promotes_fresh_candidate(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    output = Output(
        name="Demo",
        workspace_id="stable-ws",
        files={
            "index.html": "<html><body>Before</body></html>",
            "styles.css": "body { margin: 0; }",
            "content.json": '{"title":"Before"}',
        },
        source_swarm_id="swarm-1",
    )
    outputs_module._save(output)

    stable_workspace = tmp_path / ".openswarm" / "workspaces" / "stable-ws"
    stable_workspace.mkdir(parents=True, exist_ok=True)
    for rel_path, content in output.files.items():
        (stable_workspace / rel_path).write_text(content, encoding="utf-8")

    response = client.post(
        f"/api/outputs/{output.id}/iterations/candidate",
        json={
            "output_id": output.id,
            "requested_change": "Change title",
        },
    )
    assert response.status_code == 200
    iteration = response.json()["iteration"]

    updated_files = dict(output.files)
    updated_files["content.json"] = '{"title":"After"}'

    candidate_path = Path(iteration["candidate_workspace_path"])
    (candidate_path / "content.json").write_text(updated_files["content.json"], encoding="utf-8")

    record = outputs_module._load_iteration(iteration["iteration_id"])
    record.files_after = updated_files
    outputs_module._save_iteration(record)

    accept = client.post(f"/api/outputs/iterations/{record.iteration_id}/accept")
    assert accept.status_code == 200

    payload = accept.json()
    assert payload["ok"] is True
    assert payload["output"]["files"] == updated_files
    assert payload["iteration"]["status"] == "accepted"
    assert payload["freshness"]["status"] == "fresh"

    saved_output = outputs_module._load(output.id)
    saved_iteration = outputs_module._load_iteration(record.iteration_id)

    assert saved_output.files == updated_files
    assert saved_iteration.status == "accepted"
    assert saved_iteration.diff_summary["accepted_output_id"] == output.id
    assert saved_iteration.diff_summary["accepted_at"]


def test_accept_output_iteration_blocks_stale_candidate(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    output = Output(
        name="Demo",
        workspace_id="stable-ws",
        files={
            "index.html": "<html><body>Before</body></html>",
            "styles.css": "body { margin: 0; }",
            "content.json": '{"title":"Before"}',
        },
    )
    outputs_module._save(output)

    response = client.post(
        f"/api/outputs/{output.id}/iterations/candidate",
        json={"output_id": output.id, "requested_change": "Change title"},
    )
    iteration = response.json()["iteration"]

    record = outputs_module._load_iteration(iteration["iteration_id"])
    record.files_after = {
        **record.files_after,
        "content.json": '{"title":"After"}',
    }
    outputs_module._save_iteration(record)

    accept = client.post(f"/api/outputs/iterations/{record.iteration_id}/accept")
    assert accept.status_code == 409
    assert accept.json()["detail"]["error"] == "candidate_not_fresh"

    unchanged = outputs_module._load(output.id)
    still_candidate = outputs_module._load_iteration(record.iteration_id)

    assert unchanged.files == output.files
    assert still_candidate.status == "candidate"


def test_accept_output_iteration_blocks_non_candidate_iteration(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    output = Output(name="Demo", files={"index.html": "A", "styles.css": "", "content.json": "{}"})
    outputs_module._save(output)

    response = client.post(
        "/api/outputs/iterations/create",
        json={"output_id": output.id, "requested_change": "Already accepted"},
    )
    iteration = response.json()["iteration"]

    record = outputs_module._load_iteration(iteration["iteration_id"])
    record.status = "accepted"
    outputs_module._save_iteration(record)

    accept = client.post(f"/api/outputs/iterations/{record.iteration_id}/accept")
    assert accept.status_code == 400


def test_discard_output_iteration_marks_candidate_discarded_without_mutating_output(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    output = Output(
        name="Demo",
        files={
            "index.html": "<html><body>Stable</body></html>",
            "styles.css": "body { margin: 0; }",
            "content.json": '{"title":"Stable"}',
        },
    )
    outputs_module._save(output)

    response = client.post(
        f"/api/outputs/{output.id}/iterations/candidate",
        json={"output_id": output.id, "requested_change": "Discard this candidate"},
    )
    assert response.status_code == 200
    iteration = response.json()["iteration"]

    record = outputs_module._load_iteration(iteration["iteration_id"])
    record.files_after = {
        **record.files_after,
        "content.json": '{"title":"Candidate"}',
    }
    outputs_module._save_iteration(record)

    discard = client.post(f"/api/outputs/iterations/{record.iteration_id}/discard")
    assert discard.status_code == 200

    payload = discard.json()
    assert payload["ok"] is True
    assert payload["iteration"]["status"] == "discarded"
    assert payload["iteration"]["diff_summary"]["discarded_output_id"] == output.id
    assert payload["iteration"]["diff_summary"]["discarded_at"]

    unchanged = outputs_module._load(output.id)
    discarded = outputs_module._load_iteration(record.iteration_id)

    assert unchanged.files == output.files
    assert discarded.status == "discarded"
    assert discarded.diff_summary["discarded_output_id"] == output.id
    assert discarded.diff_summary["discarded_at"]


def test_discard_output_iteration_blocks_non_candidate_iteration(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    output = Output(name="Demo", files={"index.html": "A", "styles.css": "", "content.json": "{}"})
    outputs_module._save(output)

    response = client.post(
        "/api/outputs/iterations/create",
        json={"output_id": output.id, "requested_change": "Already accepted"},
    )
    iteration = response.json()["iteration"]

    record = outputs_module._load_iteration(iteration["iteration_id"])
    record.status = "accepted"
    outputs_module._save_iteration(record)

    discard = client.post(f"/api/outputs/iterations/{record.iteration_id}/discard")
    assert discard.status_code == 400
