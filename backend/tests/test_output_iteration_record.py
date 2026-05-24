from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.apps.outputs.models import Output
from backend.apps.outputs import outputs as outputs_module


def _client(tmp_path, monkeypatch):
    data_dir = tmp_path / "outputs"
    workspace_dir = tmp_path / "workspaces"
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
