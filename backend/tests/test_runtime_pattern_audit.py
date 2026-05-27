from backend.apps.swarms.runtime_pattern_audit import (
    build_runtime_pattern_audit,
    runtime_audit_component_map,
)


def test_runtime_pattern_audit_is_minimal_and_side_effect_free():
    audit = build_runtime_pattern_audit()

    assert audit["audit_id"] == "LG-RUNTIME.1.A"
    assert audit["status"] == "minimal_audit"
    assert audit["implementation_scope"] == "side_effect_free_contract_only"
    assert audit["summary"]["runtime_deep_implementation_deferred"] is True
    assert audit["summary"]["component_count"] >= 9
    assert audit["summary"]["gap_count"] > 0


def test_runtime_pattern_audit_maps_existing_runtime_surfaces():
    components = runtime_audit_component_map()

    assert components["swarm_state"]["status"] == "present"
    assert "final_result" in components["swarm_state"]["provides"]
    assert "output_bridge" in components["swarm_state"]["provides"]

    assert components["swarm_store"]["runtime_pattern"] == "persistent_state_store"
    assert "save" in components["swarm_store"]["provides"]

    assert components["event_trace_runtime"]["runtime_pattern"] == "event_trace"
    assert "swarm_event_persistence" in components["event_trace_runtime"]["provides"]

    assert components["outputs_candidates"]["runtime_pattern"] == "output_iteration_checkpoint"
    assert "candidate_iterations" in components["outputs_candidates"]["provides"]

    assert components["pending_actions"]["runtime_pattern"] == "waiting_user_state"
    assert "confirm_pending_action" in components["pending_actions"]["provides"]


def test_runtime_pattern_audit_marks_runtime_timer_as_contract_only():
    components = runtime_audit_component_map()

    timer = components["runtime_timing"]

    assert timer["status"] == "contract_only"
    assert "not yet integrated into backend lifecycle" in timer["gaps"]


def test_runtime_pattern_audit_connects_context_selection_to_existing_sources():
    audit = build_runtime_pattern_audit()
    recommendations = " ".join(audit["next_recommendations"])

    assert "Do not create a parallel runtime for CTX-RET." in recommendations
    assert "SwarmState" in recommendations
    assert "outputs" in recommendations
    assert "candidates" in recommendations
    assert "pending actions" in recommendations
    assert "evidence" in recommendations
    assert "project memory" in recommendations
