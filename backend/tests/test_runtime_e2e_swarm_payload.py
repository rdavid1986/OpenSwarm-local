from types import SimpleNamespace

from backend.apps.swarms.swarms import _runtime_e2e_integration_payload


def test_runtime_e2e_payload_is_side_effect_free_and_blocks_when_swarm_lacks_e2e_data():
    swarm = SimpleNamespace(id="swarm-test", process_trace=[], final_result={}, experimental_approvals=[])

    payload = _runtime_e2e_integration_payload(swarm)

    assert payload["ok"] is True
    assert payload["source_kind"] == "runtime_e2e_integration"
    assert payload["can_start_runtime_e2e"] is False
    assert payload["can_mark_runtime_e2e_complete"] is False
    assert payload["state"]["contains_private_reasoning"] is False
    assert payload["state"]["can_execute"] is False
    assert payload["state"]["can_write_files"] is False
    assert payload["selection"]["can_execute"] is False
    assert payload["selection"]["can_write_files"] is False
    assert "missing_candidate_id" in payload["selection"]["blockers"]


def test_runtime_e2e_payload_reports_error_without_breaking_swarm_dump():
    class BrokenSwarm:
        @property
        def id(self):
            raise RuntimeError("broken swarm")

    payload = _runtime_e2e_integration_payload(BrokenSwarm())

    assert payload["ok"] is False
    assert payload["source_kind"] == "runtime_e2e_integration"
    assert payload["can_start_runtime_e2e"] is False
    assert payload["can_mark_runtime_e2e_complete"] is False
    assert "broken swarm" in payload["error"]
