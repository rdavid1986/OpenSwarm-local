import asyncio
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.apps.agents.orchestration.orchestrator import SwarmOrchestrator
from backend.apps.agents.orchestration.store import SwarmStore
from backend.apps.agents.runtime.provider import ProviderEvent
from backend.apps.swarms import swarms as swarms_module
from backend.apps.swarms.pending_action_intelligence import resolve_pending_action_intent
from backend.apps.outputs.models import Output
from backend.apps.outputs import outputs as outputs_module


class _FakeChatAdapter:
    def __init__(self, content: str):
        self.content = content

    async def run_turn(self, context):
        yield ProviderEvent(type="provider_request", payload={"routed": True})
        yield ProviderEvent(
            type="message_final",
            payload={"message": {"role": "assistant", "content": self.content}},
        )


class _FakeNormalChatAdapter:
    def __init__(self, *args, **kwargs):
        pass

    async def run_turn(self, context):
        yield ProviderEvent(type="provider_request", payload={"routed": True})
        yield ProviderEvent(
            type="message_final",
            payload={"message": {"role": "assistant", "content": "No hay accion pendiente para preparar."}},
        )


def _client(monkeypatch, tmp_path):
    store = SwarmStore(root=tmp_path / "swarms")
    orchestrator = SwarmOrchestrator(store=store)
    monkeypatch.setattr(swarms_module, "swarm_orchestrator", orchestrator)
    app = FastAPI()
    app.include_router(swarms_module.swarms.router, prefix="/api/swarms")
    return TestClient(app), orchestrator, store


def _create_chat_swarm(store, orchestrator, *, pending: bool = True):
    swarm = orchestrator.create_swarm(user_prompt="Build app", dashboard_id="dash-1", intent="chat")
    if pending:
        swarm.final_result = {
            "status": "completed",
            "route": "refinement_request",
            "refinement_request": {
                "output_id": "out-123",
                "source_swarm_id": swarm.id,
                "requested_change": "Make the hero blue.",
                "status": "received",
                "next_action": "refinement_pipeline_pending",
            },
        }
        store.save(swarm)
    return swarm


def test_invalid_model_json_falls_back_to_clarification():
    from backend.apps.agents.orchestration.models import AgentContract, SwarmState

    coordinator = AgentContract(role="CoordinatorAgent", objective="Coordinate", allowed_tools=[])
    swarm = SwarmState(
        title="resolver test",
        user_prompt="Build app",
        intent="chat",
        coordinator_contract_id=coordinator.id,
        contracts=[coordinator],
        final_result={
            "refinement_request": {
                "output_id": "out-123",
                "requested_change": "Make the hero blue.",
                "status": "received",
            }
        },
    )

    result = asyncio.run(
        resolve_pending_action_intent(
            swarm=swarm,
            user_message="go ahead",
            swarm_mode="app_builder",
            adapter_factory=lambda: _FakeChatAdapter("not json"),
        )
    )

    assert result["classification"] == "needs_clarification"
    assert result["safe_to_prepare"] is False


def test_semantic_confirm_triggers_prepare(monkeypatch, tmp_path):
    client, orchestrator, store = _client(monkeypatch, tmp_path)
    swarm = _create_chat_swarm(store, orchestrator)
    called = {}

    async def fake_resolver(**kwargs):
        return {
            "classification": "confirm_pending_action",
            "pending_action": "confirm_refinement",
            "output_id": "out-123",
            "requested_change": "Make the hero blue.",
            "confidence": 0.91,
            "safe_to_prepare": True,
            "reason": "Clear semantic confirmation.",
            "clarification_question": None,
        }

    def fake_prepare(**kwargs):
        called.update(kwargs)
        current = store.load(kwargs["swarm_id"])
        metadata = {
            "source_swarm_id": kwargs["swarm_id"],
            "output_id": kwargs["output_id"],
            "requested_change": kwargs["requested_change"],
            "refinement_status": "prepared",
        }
        current.decisions.append({"kind": "output_refinement_prepared", "status": "accepted", "metadata": metadata})
        return store.save(current), [], metadata

    monkeypatch.setattr(swarms_module, "resolve_pending_action_intent", fake_resolver)
    monkeypatch.setattr(orchestrator, "prepare_output_refinement", fake_prepare)

    response = client.post(f"/api/swarms/{swarm.id}/experimental/chat", json={"message": "please proceed", "swarm_mode": "app_builder"})

    assert response.status_code == 200
    assert called["approve"] is True
    body = response.json()
    assert body["final_result"]["refinement_request"]["status"] == "confirmed"
    assert body["final_result"]["prepare_output_refinement"]["metadata"]["refinement_status"] == "prepared"
    assert "todavía no modifiqué la app" in body["final_result"]["summary"].lower() or "todavia no modifique la app" in body["final_result"]["summary"].lower()


def test_confirmation_phrase_overrides_needs_clarification(monkeypatch, tmp_path):
    client, orchestrator, store = _client(monkeypatch, tmp_path)
    swarm = _create_chat_swarm(store, orchestrator)
    called = {"prepare": False}

    async def fake_resolver(**kwargs):
        return {
            "classification": "needs_clarification",
            "pending_action": "confirm_refinement",
            "output_id": "out-123",
            "requested_change": "Make the hero blue.",
            "confidence": 0.2,
            "safe_to_prepare": False,
            "reason": "Model was unsure.",
            "clarification_question": "Queres confirmar, actualizar, cancelar o solo revisar este refinamiento pendiente?",
        }

    def fake_prepare(**kwargs):
        called["prepare"] = True
        current = store.load(kwargs["swarm_id"])
        metadata = {
            "source_swarm_id": kwargs["swarm_id"],
            "output_id": kwargs["output_id"],
            "requested_change": kwargs["requested_change"],
            "refinement_status": "prepared",
        }
        return store.save(current), [], metadata

    monkeypatch.setattr(swarms_module, "resolve_pending_action_intent", fake_resolver)
    monkeypatch.setattr(orchestrator, "prepare_output_refinement", fake_prepare)

    response = client.post(
        f"/api/swarms/{swarm.id}/experimental/chat",
        json={"message": "ok haz los cambios", "swarm_mode": "app_builder"},
    )

    assert response.status_code == 200
    body = response.json()
    assert called["prepare"] is True
    assert body["final_result"]["pending_action_resolution"]["classification"] == "confirm_pending_action"
    assert body["final_result"]["refinement_request"]["status"] == "confirmed"


def test_structured_confirm_action_bypasses_text_resolver(monkeypatch, tmp_path):
    client, orchestrator, store = _client(monkeypatch, tmp_path)
    swarm = _create_chat_swarm(store, orchestrator)
    called = {"prepare": False, "resolver": False}

    async def fake_resolver(**kwargs):
        called["resolver"] = True
        raise AssertionError("structured action should not call model resolver")

    def fake_prepare(**kwargs):
        called["prepare"] = True
        current = store.load(kwargs["swarm_id"])
        metadata = {
            "source_swarm_id": kwargs["swarm_id"],
            "output_id": kwargs["output_id"],
            "requested_change": kwargs["requested_change"],
            "refinement_status": "prepared",
        }
        return store.save(current), [], metadata

    monkeypatch.setattr(swarms_module, "resolve_pending_action_intent", fake_resolver)
    monkeypatch.setattr(orchestrator, "prepare_output_refinement", fake_prepare)

    response = client.post(
        f"/api/swarms/{swarm.id}/experimental/chat",
        json={"message": "__openswarm_pending_action__:confirm_refinement", "swarm_mode": "app_builder"},
    )

    assert response.status_code == 200
    body = response.json()
    assert called["resolver"] is False
    assert called["prepare"] is True
    assert body["final_result"]["pending_action_resolution"]["classification"] == "confirm_pending_action"
    assert body["final_result"]["refinement_request"]["status"] == "confirmed"


def test_confirmation_typo_phrase_overrides_needs_clarification(monkeypatch, tmp_path):
    client, orchestrator, store = _client(monkeypatch, tmp_path)
    swarm = _create_chat_swarm(store, orchestrator)
    called = {"prepare": False}

    async def fake_resolver(**kwargs):
        return {
            "classification": "needs_clarification",
            "pending_action": "confirm_refinement",
            "output_id": "out-123",
            "requested_change": "Make the hero blue.",
            "confidence": 0.2,
            "safe_to_prepare": False,
            "reason": "Model was unsure.",
            "clarification_question": "Queres confirmar, actualizar, cancelar o solo revisar este refinamiento pendiente?",
        }

    def fake_prepare(**kwargs):
        called["prepare"] = True
        current = store.load(kwargs["swarm_id"])
        metadata = {
            "source_swarm_id": kwargs["swarm_id"],
            "output_id": kwargs["output_id"],
            "requested_change": kwargs["requested_change"],
            "refinement_status": "prepared",
        }
        return store.save(current), [], metadata

    monkeypatch.setattr(swarms_module, "resolve_pending_action_intent", fake_resolver)
    monkeypatch.setattr(orchestrator, "prepare_output_refinement", fake_prepare)

    response = client.post(
        f"/api/swarms/{swarm.id}/experimental/chat",
        json={"message": "comfirmo, quiero confirmar el cambio", "swarm_mode": "app_builder"},
    )

    assert response.status_code == 200
    body = response.json()
    assert called["prepare"] is True
    assert body["final_result"]["pending_action_resolution"]["classification"] == "confirm_pending_action"
    assert body["final_result"]["refinement_request"]["status"] == "confirmed"


def test_no_pending_action_ok_does_not_prepare(monkeypatch, tmp_path):
    client, orchestrator, store = _client(monkeypatch, tmp_path)
    swarm = _create_chat_swarm(store, orchestrator, pending=False)
    called = {"prepare": False}

    def fake_prepare(**kwargs):
        called["prepare"] = True
        raise AssertionError("prepare_output_refinement must not be called")

    monkeypatch.setattr(orchestrator, "prepare_output_refinement", fake_prepare)
    monkeypatch.setattr(swarms_module, "OllamaAdapter", _FakeNormalChatAdapter)

    response = client.post(f"/api/swarms/{swarm.id}/experimental/chat", json={"message": "ok", "swarm_mode": "app_builder"})

    assert response.status_code == 200
    assert called["prepare"] is False
    assert response.json()["final_result"]["route"] == "implementation_request"


def test_preview_refine_registers_candidate_metadata_without_execution(monkeypatch, tmp_path):
    client, orchestrator, store = _client(monkeypatch, tmp_path)
    swarm = _create_chat_swarm(store, orchestrator, pending=False)
    monkeypatch.setattr(swarms_module, "OllamaAdapter", _FakeNormalChatAdapter)

    message = "\n".join([
        "Quiero refinar la app generada desde esta Preview.",
        "",
        "Output ID: out-123",
        "Output name: Demo",
        "Preset actual: desktop",
        f"Source swarm: {swarm.id}",
        "Source task: task-1",
        "Validation status: verified",
        "Artifacts: art-1",
        "Evidence: ev-1",
        "",
        "Cambio solicitado:",
        "Make the hero clearer.",
        "",
        "Refinamiento preparado para esta app. Se creó una candidate para revisión en Preview.",
    ])

    response = client.post(
        f"/api/swarms/{swarm.id}/experimental/chat",
        json={"message": message, "swarm_mode": "app_builder"},
    )

    assert response.status_code == 200
    body = response.json()
    refinement = body["final_result"]["refinement_request"]
    assert refinement["output_id"] == "out-123"
    assert refinement["requested_change"] == "Make the hero clearer."
    assert "candidate_iteration_id" not in refinement
    assert "candidate_workspace_path" not in refinement
    assert "base_workspace_path" not in refinement
    assert refinement.get("candidate_status") is None
    assert refinement.get("files_changed") is not True
    assert refinement["status"] == "received"
    assert refinement["next_action"] == "refinement_pipeline_pending"
    assert body["final_result"].get("execution_status") is None
    summary = body["final_result"]["summary"].lower()
    assert (
        "todavía no modifiqué la app" in summary
        or "todavia no modifique la app" in summary
        or "no se modific" in summary
        or "no se generaron nuevos artifacts" in summary
    )
    visible_user_message = [
        message["payload"]["content"]
        for message in body["messages"]
        if message["payload"].get("role") == "user"
    ][-1]
    assert "Output ID:" not in visible_user_message
    assert "Source swarm:" not in visible_user_message
    assert "Source task:" not in visible_user_message
    assert "Artifacts:" not in visible_user_message
    assert "Evidence:" not in visible_user_message
    assert "Candidate iteration ID:" not in visible_user_message
    assert "Candidate workspace:" not in visible_user_message
    assert "Base workspace:" not in visible_user_message
    assert "Quiero refinar la app generada desde esta Preview" not in visible_user_message
    assert "Cambio solicitado:" not in visible_user_message


def test_update_changes_requested_change_only(monkeypatch, tmp_path):
    client, orchestrator, store = _client(monkeypatch, tmp_path)
    swarm = _create_chat_swarm(store, orchestrator)

    async def fake_resolver(**kwargs):
        return {
            "classification": "update_pending_action",
            "pending_action": "confirm_refinement",
            "output_id": "out-123",
            "requested_change": "Make the hero green.",
            "confidence": 0.88,
            "safe_to_prepare": False,
            "reason": "User changed the request.",
            "clarification_question": None,
        }

    monkeypatch.setattr(swarms_module, "resolve_pending_action_intent", fake_resolver)
    response = client.post(f"/api/swarms/{swarm.id}/experimental/chat", json={"message": "actually make it green", "swarm_mode": "app_builder"})

    assert response.status_code == 200
    refinement = response.json()["final_result"]["refinement_request"]
    assert refinement["requested_change"] == "Make the hero green."
    assert refinement["status"] == "received"
    assert not response.json()["decisions"]


def test_cancel_marks_refinement_request_cancelled(monkeypatch, tmp_path):
    client, orchestrator, store = _client(monkeypatch, tmp_path)
    swarm = _create_chat_swarm(store, orchestrator)

    async def fake_resolver(**kwargs):
        return {
            "classification": "cancel_pending_action",
            "pending_action": "confirm_refinement",
            "output_id": "out-123",
            "requested_change": "Make the hero blue.",
            "confidence": 0.9,
            "safe_to_prepare": False,
            "reason": "User cancelled.",
            "clarification_question": None,
        }

    monkeypatch.setattr(swarms_module, "resolve_pending_action_intent", fake_resolver)
    response = client.post(f"/api/swarms/{swarm.id}/experimental/chat", json={"message": "cancel that", "swarm_mode": "app_builder"})

    assert response.status_code == 200
    refinement = response.json()["final_result"]["refinement_request"]
    assert refinement["status"] == "cancelled"
    assert refinement["next_action"] is None


def test_explain_does_not_prepare(monkeypatch, tmp_path):
    client, orchestrator, store = _client(monkeypatch, tmp_path)
    swarm = _create_chat_swarm(store, orchestrator)
    called = {"prepare": False}

    async def fake_resolver(**kwargs):
        return {
            "classification": "explain_pending_action",
            "pending_action": "confirm_refinement",
            "output_id": "out-123",
            "requested_change": "Make the hero blue.",
            "confidence": 0.87,
            "safe_to_prepare": False,
            "reason": "User asked for explanation.",
            "clarification_question": None,
        }

    def fake_prepare(**kwargs):
        called["prepare"] = True
        raise AssertionError("prepare_output_refinement must not be called")

    monkeypatch.setattr(swarms_module, "resolve_pending_action_intent", fake_resolver)
    monkeypatch.setattr(orchestrator, "prepare_output_refinement", fake_prepare)
    response = client.post(f"/api/swarms/{swarm.id}/experimental/chat", json={"message": "what will happen?", "swarm_mode": "app_builder"})

    assert response.status_code == 200
    assert called["prepare"] is False
    assert "no se ejecuta el pipeline real" in response.json()["final_result"]["summary"].lower()


def test_mismatched_output_id_change_is_blocked(monkeypatch, tmp_path):
    client, orchestrator, store = _client(monkeypatch, tmp_path)
    swarm = _create_chat_swarm(store, orchestrator)
    called = {"prepare": False}

    async def fake_resolver(**kwargs):
        return {
            "classification": "confirm_pending_action",
            "pending_action": "confirm_refinement",
            "output_id": "out-other",
            "requested_change": "Make the hero red.",
            "confidence": 0.95,
            "safe_to_prepare": True,
            "reason": "Unsafe mismatch.",
            "clarification_question": None,
        }

    def fake_prepare(**kwargs):
        called["prepare"] = True
        raise AssertionError("prepare_output_refinement must not be called")

    monkeypatch.setattr(swarms_module, "resolve_pending_action_intent", fake_resolver)
    monkeypatch.setattr(orchestrator, "prepare_output_refinement", fake_prepare)
    response = client.post(f"/api/swarms/{swarm.id}/experimental/chat", json={"message": "go ahead", "swarm_mode": "app_builder"})

    assert response.status_code == 200
    assert called["prepare"] is False
    assert response.json()["final_result"]["pending_action_resolution"]["classification"] == "needs_clarification"


def test_existing_preview_draft_route_still_stores_pending_refinement(monkeypatch, tmp_path):
    client, orchestrator, store = _client(monkeypatch, tmp_path)
    swarm = _create_chat_swarm(store, orchestrator, pending=False)
    draft = """Quiero refinar la app generada desde esta Preview.

Output ID: out-999
Output name: Demo
Source swarm: source-999
Source task: task-1
Validation status: passed
Artifacts: []
Evidence: []

Cambio solicitado: Add a better CTA
"""

    response = client.post(f"/api/swarms/{swarm.id}/experimental/chat", json={"message": draft, "swarm_mode": "app_builder"})

    assert response.status_code == 200
    refinement = response.json()["final_result"]["refinement_request"]
    assert refinement["output_id"] == "out-999"
    assert refinement["requested_change"] == "Add a better CTA"
    assert refinement["status"] == "received"

def test_closed_refinement_statuses_are_not_treated_as_pending(monkeypatch, tmp_path):
    client, orchestrator, store = _client(monkeypatch, tmp_path)
    called = {"prepare": False, "resolver": False}

    def fake_prepare(**kwargs):
        called["prepare"] = True
        raise AssertionError("prepare_output_refinement must not be called")

    async def fake_resolver(**kwargs):
        called["resolver"] = True
        raise AssertionError("resolver must not be called for closed refinement states")

    monkeypatch.setattr(orchestrator, "prepare_output_refinement", fake_prepare)
    monkeypatch.setattr(swarms_module, "resolve_pending_action_intent", fake_resolver)
    monkeypatch.setattr(swarms_module, "OllamaAdapter", _FakeNormalChatAdapter)

    for status in ["cancelled", "confirmed", "prepared", "executed", "validated", "failed"]:
        swarm = _create_chat_swarm(store, orchestrator)
        swarm.final_result["refinement_request"]["status"] = status
        swarm.final_result["refinement_request"]["next_action"] = "run_refinement_pipeline"
        store.save(swarm)

        response = client.post(
            f"/api/swarms/{swarm.id}/experimental/chat",
            json={"message": "ok", "swarm_mode": "app_builder"},
        )

        assert response.status_code == 200
        assert called["prepare"] is False
        assert called["resolver"] is False


def test_confirm_pending_refinement_executes_candidate_iteration_without_mutating_output(monkeypatch, tmp_path):
    client, orchestrator, store = _client(monkeypatch, tmp_path)

    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    data_dir = tmp_path / "outputs"
    workspace_dir = tmp_path / ".openswarm" / "workspaces"
    iterations_dir = data_dir / "_iterations"
    data_dir.mkdir(parents=True, exist_ok=True)
    workspace_dir.mkdir(parents=True, exist_ok=True)
    iterations_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(outputs_module, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(outputs_module, "WORKSPACE_DIR", str(workspace_dir))
    monkeypatch.setattr(outputs_module, "ITERATIONS_DIR", str(iterations_dir))

    output = Output(
        id="out-123",
        name="Demo",
        files={
            "index.html": "<html><body>Before</body></html>",
            "styles.css": "body { margin: 0; }",
            "content.json": '{"title":"Before"}',
        },
        source_swarm_id="",
        artifact_refs=["artifact-1"],
        evidence_refs=["evidence-1"],
        validation_status="passed",
    )
    outputs_module._save(output)

    swarm = _create_chat_swarm(store, orchestrator, pending=False)
    output.source_swarm_id = swarm.id
    outputs_module._save(output)

    candidate = outputs_module._create_candidate_iteration_from_output(
        output=output,
        requested_change="Make the hero blue.",
        source_swarm_id=swarm.id,
    )

    swarm.workspace_path = candidate.base_workspace_path
    swarm.artifacts.append({"id": "artifact-1", "path": "index.html"})
    swarm.final_result = {
        "status": "completed",
        "route": "refinement_request",
        "refinement_request": {
            "output_id": output.id,
            "source_swarm_id": swarm.id,
            "requested_change": "Make the hero blue.",
            "status": "received",
            "next_action": "refinement_pipeline_pending",
            "candidate_iteration_id": candidate.iteration_id,
            "candidate_workspace_path": candidate.candidate_workspace_path,
            "base_workspace_path": candidate.base_workspace_path,
        },
    }
    store.save(swarm)

    async def fake_resolver(**kwargs):
        return {
            "classification": "confirm_pending_action",
            "pending_action": "confirm_refinement",
            "output_id": output.id,
            "requested_change": "Make the hero blue.",
            "confidence": 0.95,
            "safe_to_prepare": True,
            "reason": "Clear semantic confirmation.",
            "clarification_question": None,
        }

    def fake_prepare(**kwargs):
        current = store.load(kwargs["swarm_id"])
        metadata = {
            "source_swarm_id": kwargs["swarm_id"],
            "output_id": kwargs["output_id"],
            "requested_change": kwargs["requested_change"],
            "workspace_path": candidate.base_workspace_path,
            "refinement_status": "prepared",
        }
        current.decisions.append({"kind": "output_refinement_prepared", "status": "accepted", "metadata": metadata})
        return store.save(current), [], metadata

    async def fake_plan_candidate_refinement_file_updates(**kwargs):
        return {
            "ok": True,
            "status": "planned",
            "reason": "Test planner update.",
            "file_updates": {"content.json": '{"title":"After"}'},
        }

    monkeypatch.setattr(swarms_module, "resolve_pending_action_intent", fake_resolver)
    monkeypatch.setattr(swarms_module, "plan_candidate_refinement_file_updates", fake_plan_candidate_refinement_file_updates)
    monkeypatch.setattr(orchestrator, "prepare_output_refinement", fake_prepare)

    response = client.post(
        f"/api/swarms/{swarm.id}/experimental/chat",
        json={"message": "please proceed", "swarm_mode": "app_builder"},
    )

    assert response.status_code == 200
    body = response.json()
    final_result = body["final_result"]

    assert final_result["refinement_request"]["status"] == "executed"
    assert final_result["refinement_request"]["next_action"] == "review_candidate_diff"
    assert final_result["refinement_execution_guard"]["allowed"] is True
    assert final_result["refinement_execution_guard"]["metadata"]["execution_pipeline_state"] == "available"
    assert final_result["refinement_execution_result"]["status"] == "executed"
    assert final_result["refinement_execution_result"]["candidate_iteration_id"] == candidate.iteration_id
    assert "content.json" in final_result["refinement_execution_result"]["files_changed"]

    updated_candidate = outputs_module._load_iteration(candidate.iteration_id)
    assert updated_candidate.status == "candidate"
    assert updated_candidate.files_before == output.files
    assert updated_candidate.files_after["content.json"] != output.files["content.json"]
    assert updated_candidate.diff_summary["status"] == "candidate_applied"
    assert updated_candidate.diff_summary["changed"] == ["content.json"]

    unchanged_output = outputs_module._load(output.id)
    assert unchanged_output.files == output.files

    summary = final_result["summary"]
    assert "candidate" in summary.lower()
    assert "Output activo todavía no fue modificado" in summary
    assert "Accept o Discard" in summary
