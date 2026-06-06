from pathlib import Path

TARGET = Path("frontend/src/app/pages/Dashboard/canvasProceduralSwarmLayout.ts")


def read_source() -> str:
    assert TARGET.exists(), f"missing target file: {TARGET}"
    return TARGET.read_text(encoding="utf-8")


def test_live_execution_state_contract_exports_exist():
    source = read_source()

    assert "export type CanvasProceduralLiveStateTone" in source
    assert "export interface CanvasProceduralLiveStateMeta" in source
    assert "export function resolveProceduralLiveExecutionState" in source


def test_live_execution_states_cover_required_statuses():
    source = read_source()

    required_statuses = [
        "running",
        "next_to_run",
        "waiting_approval",
        "blocked",
        "completed",
        "failed",
        "skipped",
        "pending",
    ]

    for status in required_statuses:
        assert status in source


def test_live_execution_state_metadata_contract_fields_exist():
    source = read_source()

    required_fields = [
        "tone:",
        "label:",
        "description:",
        "active:",
        "attention:",
        "terminal:",
        "dimmed:",
        "pulse:",
        "glow:",
    ]

    for field in required_fields:
        assert field in source


def test_layout_nodes_expose_live_state_metadata():
    source = read_source()

    assert "procedural_live_state: CanvasProceduralLiveStateMeta" in source
    assert "resolveProceduralLiveExecutionState(node.status)" in source
