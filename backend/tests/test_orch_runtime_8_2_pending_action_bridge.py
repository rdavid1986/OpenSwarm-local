from backend.apps.swarms.swarms import _attach_pending_action_side_effect_policy


class DummySwarm:
    def __init__(self, task_envelope: dict | None) -> None:
        self.final_result = {
            "project_intake_state": {
                "task_envelope": task_envelope or {},
            }
        }


def test_attach_pending_action_side_effect_policy_injects_side_effect_policy():
    swarm = DummySwarm(
        {
            "task_id": "task-1",
            "side_effect_policy": "requires_approval",
            "requested_outputs": ["preview"],
        }
    )
    resolution = {
        "classification": "confirm_pending_action",
        "pending_action": "confirm_refinement",
    }

    attached = _attach_pending_action_side_effect_policy(swarm, resolution)

    assert attached is not resolution
    assert "side_effect_policy" in attached
    assert attached["side_effect_policy"]["decision"] == "requires_approval"
    assert attached["side_effect_policy"]["requires_approval"] is True
    assert attached["side_effect_policy"]["task_envelope"]["task_id"] == "task-1"
    assert attached["side_effect_policy"]["task_envelope"]["side_effect_policy"] == "requires_approval"


def test_attach_pending_action_side_effect_policy_keeps_resolution_when_no_task_envelope():
    swarm = DummySwarm(None)
    resolution = {
        "classification": "cancel_pending_action",
        "pending_action": "confirm_refinement",
    }

    attached = _attach_pending_action_side_effect_policy(swarm, resolution)

    assert attached == resolution


def test_attach_pending_action_side_effect_policy_keeps_resolution_when_task_envelope_is_empty():
    swarm = DummySwarm({})
    resolution = {
        "classification": "cancel_pending_action",
        "pending_action": "confirm_refinement",
    }

    attached = _attach_pending_action_side_effect_policy(swarm, resolution)

    assert attached == resolution
