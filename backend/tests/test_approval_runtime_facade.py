from backend.apps.agents.runtime import ApprovalDecision


def test_approval_decision_flags():
    allowed = ApprovalDecision(behavior="allow")
    denied = ApprovalDecision(behavior="deny", timed_out=True)

    assert allowed.behavior == "allow"
    assert denied.behavior == "deny"
    assert denied.timed_out is True
