from backend.apps.swarms.side_effect_policy import (
    SideEffectPolicy,
    build_side_effect_policy_from_task_envelope,
    dump_side_effect_policy,
)
from backend.apps.swarms.task_envelope import build_task_envelope_from_swarm_input


def test_build_side_effect_policy_from_blocked_task_envelope():
    envelope = build_task_envelope_from_swarm_input(
        user_message="Format drive and delete everything",
        swarm_mode="debug",
    )

    policy = build_side_effect_policy_from_task_envelope(envelope)

    assert isinstance(policy, SideEffectPolicy)
    assert policy.blocked is True
    assert policy.requires_approval is False
    assert policy.decision == "blocked"
    assert policy.task_envelope["side_effect_policy"] == "blocked"
    assert dump_side_effect_policy(policy)["policy_id"]


def test_build_side_effect_policy_from_requires_approval_task_envelope():
    envelope = build_task_envelope_from_swarm_input(
        user_message="aplica los cambios y ejecuta el comando",
        swarm_mode="app_builder",
    )

    policy = build_side_effect_policy_from_task_envelope(
        envelope,
        approval_id="approval-123",
        policy_matrix_ref="policy-matrix-7",
        tool_name="SafeShell",
        tool_input={"command": "echo ok"},
    )

    data = dump_side_effect_policy(policy)

    assert policy.requires_approval is True
    assert policy.blocked is False
    assert data["approval_id"] == "approval-123"
    assert data["policy_matrix_ref"] == "policy-matrix-7"
    assert data["tool_name"] == "SafeShell"
    assert data["tool_input"]["command"] == "echo ok"
    assert data["task_envelope"]["side_effect_policy"] == "requires_approval"


def test_dump_side_effect_policy_accepts_dict():
    payload = {
        "policy_id": "policy-1",
        "decision": "none",
        "blocked": False,
        "requires_approval": False,
    }

    dumped = dump_side_effect_policy(payload)

    assert dumped["policy_id"] == "policy-1"
    assert dumped["decision"] == "none"
    assert dumped["blocked"] is False
    assert dumped["requires_approval"] is False


def test_side_effect_policy_normalizes_invalid_decision_to_unknown():
    policy = build_side_effect_policy_from_task_envelope(
        {
            "task_id": "task-invalid",
            "side_effect_policy": "run_everything",
        }
    )

    data = dump_side_effect_policy(policy)

    assert data["policy_id"] == "task-invalid"
    assert data["decision"] == "unknown"
    assert data["blocked"] is False
    assert data["requires_approval"] is False


def test_side_effect_policy_uses_reason_fallbacks_and_policy_id_priority():
    policy = build_side_effect_policy_from_task_envelope(
        {
            "task_id": "task-primary",
            "policy_id": "policy-secondary",
            "trace_id": "trace-third",
            "objective": "objective-fourth",
            "side_effect_policy": "blocked",
            "risk_reason": "Dangerous destructive operation.",
        }
    )

    data = dump_side_effect_policy(policy)

    assert data["policy_id"] == "task-primary"
    assert data["reason"] == "Dangerous destructive operation."
    assert data["blocked"] is True
    assert data["requires_approval"] is False


def test_side_effect_policy_reads_pending_action_refs_when_not_explicit():
    policy = build_side_effect_policy_from_task_envelope(
        {
            "task_id": "task-approval",
            "side_effect_policy": "requires_approval",
            "pending_action": {
                "approval_id": "approval-from-envelope",
                "policy_matrix_ref": "matrix-from-envelope",
            },
        },
        tool_name="SafeShell",
        tool_input={"command": "python -m pytest -q"},
    )

    data = dump_side_effect_policy(policy)

    assert data["approval_id"] == "approval-from-envelope"
    assert data["policy_matrix_ref"] == "matrix-from-envelope"
    assert data["requires_approval"] is True
    assert data["tool_name"] == "SafeShell"
    assert data["tool_input"] == {"command": "python -m pytest -q"}


def test_side_effect_policy_flags_for_supported_decisions():
    cases = [
        ("none", False, False),
        ("requires_approval", False, True),
        ("blocked", True, False),
        ("unknown", False, False),
    ]

    for decision, blocked, requires_approval in cases:
        policy = build_side_effect_policy_from_task_envelope(
            {
                "task_id": f"task-{decision}",
                "side_effect_policy": decision,
            }
        )

        assert policy.decision == decision
        assert policy.blocked is blocked
        assert policy.requires_approval is requires_approval
