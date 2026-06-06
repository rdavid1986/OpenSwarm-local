from pathlib import Path

TARGET = Path("frontend/src/app/pages/Dashboard/SwarmOrchestrationPreview.tsx")


def read_source() -> str:
    assert TARGET.exists(), f"missing target file: {TARGET}"
    return TARGET.read_text(encoding="utf-8")


def test_preview_node_accepts_procedural_live_state_metadata():
    source = read_source()

    assert "type CanvasProceduralLiveStateMeta" in source
    assert "procedural_live_state?: CanvasProceduralLiveStateMeta" in source


def test_preview_status_meta_can_use_live_state_metadata():
    source = read_source()

    assert "liveState?: CanvasProceduralLiveStateMeta" in source
    assert "if (liveState)" in source
    assert "liveState.label" in source
    assert "liveState.description" in source
    assert "liveState.active" in source
    assert "liveState.attention" in source
    assert "liveState.pulse" in source
    assert "liveState.glow" in source
    assert "liveState.dimmed" in source


def test_preview_passes_node_live_state_to_status_meta():
    source = read_source()

    assert "getStatusMeta(node.status, node.procedural_live_state)" in source


def test_preview_uses_live_state_visual_flags_in_render():
    source = read_source()

    assert "meta.pulse" in source
    assert "meta.glow" in source
    assert "meta.dimmed" in source
