from pathlib import Path

import pytest

from backend.apps.agents.orchestration.models import EvidenceRecord, SwarmState
from backend.apps.outputs.models import Output
from backend.apps.swarms import refinement_action_guard
from backend.apps.swarms.refinement_action_guard import evaluate_refinement_execution_guard


def _workspace(tmp_path: Path, *, name: str = "ri7d") -> Path:
    workspace = tmp_path / ".openswarm" / "workspaces" / name
    workspace.mkdir(parents=True)
    (workspace / "index.html").write_text("<html><body>RI-7.D</body></html>", encoding="utf-8")
    (workspace / "styles.css").write_text("body { color: #111; }", encoding="utf-8")
    (workspace / "content.json").write_text('{"title":"RI-7.D"}', encoding="utf-8")
    return workspace


def _output_from_workspace(workspace: Path, *, output_id: str = "out-guard", source_swarm_id: str = "swarm-guard") -> Output:
    return Output(
        id=output_id,
        name="Guarded Output",
        files={
            "index.html": (workspace / "index.html").read_text(encoding="utf-8"),
            "styles.css": (workspace / "styles.css").read_text(encoding="utf-8"),
            "content.json": (workspace / "content.json").read_text(encoding="utf-8"),
        },
        source_swarm_id=source_swarm_id,
        artifact_refs=["artifact-output-1"],
        evidence_refs=["evidence-output-1"],
        validation_status="passed",
    )


def _prepared_swarm(workspace: Path, *, output_id: str = "out-guard", requested_change: str = "Mejorar hero.") -> SwarmState:
    swarm = SwarmState(
        id="swarm-guard",
        title="RI-7.D",
        user_prompt="Refine output",
        intent="chat",
        workspace_path=str(workspace),
    )
    swarm.artifacts.append({"id": "artifact-swarm-1", "path": "index.html"})
    swarm.evidence.append(
        EvidenceRecord(
            id="evidence-swarm-1",
            kind="file_read",
            file_path="index.html",
        )
    )
    swarm.final_result = {
        "refinement_request": {
            "output_id": output_id,
            "source_swarm_id": "swarm-guard",
            "requested_change": requested_change,
            "status": "confirmed",
            "next_action": "run_refinement_pipeline",
        },
        "prepare_output_refinement": {
            "metadata": {
                "source_swarm_id": "swarm-guard",
                "output_id": output_id,
                "requested_change": requested_change,
                "workspace_path": str(workspace),
                "refinement_status": "prepared",
            },
            "validation_errors": [],
        },
    }
    return swarm


def _codes(result: dict) -> set[str]:
    return {reason["code"] for reason in result["blocked_reasons"]}


def test_refinement_execution_guard_blocks_when_not_prepared(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workspace = _workspace(tmp_path)
    output = _output_from_workspace(workspace)
    monkeypatch.setattr(refinement_action_guard, "load_output", lambda output_id: output)
    swarm = _prepared_swarm(workspace)
    swarm.final_result.pop("prepare_output_refinement")

    result = evaluate_refinement_execution_guard(
        swarm=swarm,
        output_id=output.id,
        requested_change="Mejorar hero.",
        approve=True,
    )

    assert result["allowed"] is False
    assert result["guard_status"] == "blocked"
    assert result["action_stage"] == "confirmed"
    assert "action_stage_not_prepared" in _codes(result)


def test_refinement_execution_guard_blocks_missing_output(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workspace = _workspace(tmp_path)
    monkeypatch.setattr(refinement_action_guard, "load_output", lambda output_id: None)
    swarm = _prepared_swarm(workspace)

    result = evaluate_refinement_execution_guard(
        swarm=swarm,
        output_id="missing-output",
        requested_change="Mejorar hero.",
        approve=True,
    )

    assert result["allowed"] is False
    assert "output_not_found" in _codes(result)
    assert result["metadata"]["has_output"] is False


def test_refinement_execution_guard_blocks_requested_change_mismatch(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workspace = _workspace(tmp_path)
    output = _output_from_workspace(workspace)
    monkeypatch.setattr(refinement_action_guard, "load_output", lambda output_id: output)
    swarm = _prepared_swarm(workspace, requested_change="Cambio original.")

    result = evaluate_refinement_execution_guard(
        swarm=swarm,
        output_id=output.id,
        requested_change="Cambio distinto.",
        approve=True,
    )

    assert result["allowed"] is False
    assert "requested_change_mismatch" in _codes(result)


@pytest.mark.parametrize(
    ("mode", "expected_code", "expected_freshness"),
    [
        ("stale", "workspace_stale", "stale"),
        ("missing", "workspace_missing", "missing"),
        ("unknown", "workspace_unknown", "unknown"),
    ],
)
def test_refinement_execution_guard_blocks_workspace_not_fresh(
    tmp_path: Path,
    monkeypatch,
    mode: str,
    expected_code: str,
    expected_freshness: str,
):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workspace = _workspace(tmp_path, name=f"ri7d-{mode}")
    output = _output_from_workspace(workspace)
    monkeypatch.setattr(refinement_action_guard, "load_output", lambda output_id: output)
    swarm = _prepared_swarm(workspace)
    if mode == "stale":
        (workspace / "index.html").write_text("<html><body>changed</body></html>", encoding="utf-8")
    elif mode == "missing":
        (workspace / "content.json").unlink()
    elif mode == "unknown":
        swarm.workspace_path = None

    result = evaluate_refinement_execution_guard(
        swarm=swarm,
        output_id=output.id,
        requested_change="Mejorar hero.",
        approve=True,
    )

    assert result["allowed"] is False
    assert expected_code in _codes(result)
    assert result["metadata"]["workspace_freshness"] == expected_freshness


def test_refinement_execution_guard_blocks_missing_approval(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workspace = _workspace(tmp_path)
    output = _output_from_workspace(workspace)
    monkeypatch.setattr(refinement_action_guard, "load_output", lambda output_id: output)
    swarm = _prepared_swarm(workspace)

    result = evaluate_refinement_execution_guard(
        swarm=swarm,
        output_id=output.id,
        requested_change="Mejorar hero.",
        approve=False,
    )

    assert result["allowed"] is False
    assert "approval_missing" in _codes(result)
    assert result["metadata"]["approval_state"] == "missing"


def test_refinement_execution_guard_blocks_snapshot_missing(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workspace = _workspace(tmp_path)
    output = _output_from_workspace(workspace)
    monkeypatch.setattr(refinement_action_guard, "load_output", lambda output_id: output)
    swarm = _prepared_swarm(workspace)
    swarm.final_result["prepare_output_refinement"]["metadata"]["rollback_available"] = True

    result = evaluate_refinement_execution_guard(
        swarm=swarm,
        output_id=output.id,
        requested_change="Mejorar hero.",
        approve=True,
    )

    assert result["allowed"] is False
    assert "snapshot_missing" in _codes(result)
    assert result["metadata"]["has_snapshot"] is False


def test_refinement_execution_guard_blocks_rollback_missing(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workspace = _workspace(tmp_path)
    output = _output_from_workspace(workspace)
    monkeypatch.setattr(refinement_action_guard, "load_output", lambda output_id: output)
    swarm = _prepared_swarm(workspace)
    swarm.final_result["prepare_output_refinement"]["metadata"]["base_version_id"] = "version-1"

    result = evaluate_refinement_execution_guard(
        swarm=swarm,
        output_id=output.id,
        requested_change="Mejorar hero.",
        approve=True,
    )

    assert result["allowed"] is False
    assert "rollback_missing" in _codes(result)
    assert result["metadata"]["has_rollback"] is False


def test_refinement_execution_guard_blocks_fresh_approved_without_snapshot_or_rollback(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workspace = _workspace(tmp_path)
    output = _output_from_workspace(workspace)
    monkeypatch.setattr(refinement_action_guard, "load_output", lambda output_id: output)
    swarm = _prepared_swarm(workspace)

    result = evaluate_refinement_execution_guard(
        swarm=swarm,
        output_id=output.id,
        requested_change="Mejorar hero.",
        approve=True,
    )

    assert result["allowed"] is False
    assert result["metadata"]["workspace_freshness"] == "fresh"
    assert result["metadata"]["approval_state"] == "provided"
    assert {"snapshot_missing", "rollback_missing"}.issubset(_codes(result))


def test_refinement_execution_guard_returns_ui_ready_reasons_and_next_steps(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    workspace = _workspace(tmp_path)
    output = _output_from_workspace(workspace)
    monkeypatch.setattr(refinement_action_guard, "load_output", lambda output_id: output)
    swarm = _prepared_swarm(workspace)

    result = evaluate_refinement_execution_guard(
        swarm=swarm,
        output_id=output.id,
        requested_change="Mejorar hero.",
        approve=True,
    )

    assert result["guard_status"] == "blocked"
    assert result["risk_level"] == "high"
    assert result["blocked_reasons"]
    assert all({"code", "message", "severity"}.issubset(reason) for reason in result["blocked_reasons"])
    assert result["required_next_steps"]
    assert all({"code", "label", "phase"}.issubset(step) for step in result["required_next_steps"])
    assert result["metadata"]["evidence_state"] == "sufficient"
    assert result["metadata"]["execution_pipeline_state"] == "unavailable"


def test_pending_refinement_chat_content_reports_guard_block():
    from backend.apps.swarms.swarms import _pending_refinement_chat_content

    content = _pending_refinement_chat_content(
        classification="confirm_pending_action",
        refinement_request={
            "output_id": "out-guard",
            "requested_change": "Mejorar hero.",
        },
        resolution={
            "classification": "confirm_pending_action",
            "output_id": "out-guard",
            "requested_change": "Mejorar hero.",
        },
        prepare_metadata={
            "output_id": "out-guard",
            "requested_change": "Mejorar hero.",
            "refinement_status": "prepared",
        },
        validation_errors=[],
        guard_result={
            "guard_status": "blocked",
            "risk_level": "high",
            "blocked_reasons": [
                {
                    "code": "snapshot_missing",
                    "message": "No existe snapshot/version base del Output para ejecución segura.",
                    "severity": "high",
                },
                {
                    "code": "rollback_missing",
                    "message": "No existe rollback mínimo disponible para revertir la iteración.",
                    "severity": "high",
                },
            ],
            "required_next_steps": [
                {
                    "code": "create_output_iteration_snapshot",
                    "label": "Crear snapshot/version base del Output antes de ejecutar.",
                    "phase": "Apps-3.G.4.A",
                }
            ],
        },
    )

    assert "Guard de ejecucion: blocked." in content
    assert "Riesgo: high." in content
    assert "snapshot_missing" in content
    assert "rollback_missing" in content
    assert "create_output_iteration_snapshot" in content
    assert "la ejecucion sigue bloqueada por guard" in content
