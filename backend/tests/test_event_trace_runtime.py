from backend.apps.agents.runtime import EventTraceRuntime, TraceEvent


def test_trace_event_serializes_required_shape():
    event = TraceEvent(
        type="tool_requested",
        session_id="s1",
        agent_id="a1",
        task_id="t1",
        payload={"tool_name": "Read"},
    )

    data = event.to_dict()

    assert data["id"] == event.id
    assert data["type"] == "tool_requested"
    assert data["session_id"] == "s1"
    assert data["agent_id"] == "a1"
    assert data["task_id"] == "t1"
    assert data["payload"]["tool_name"] == "Read"


def test_event_trace_runtime_records_by_session_and_swarm():
    runtime = EventTraceRuntime()
    event = runtime.create(
        "agent_started",
        swarm_id="sw1",
        session_id="s1",
        agent_id="a1",
        payload={"role": "Worker"},
    )

    assert runtime.list_session_events("s1") == [event]
    assert runtime.list_swarm_events("sw1") == [event]


def test_event_trace_runtime_clear_removes_recorded_events():
    runtime = EventTraceRuntime()
    runtime.create("swarm_completed", swarm_id="sw1")

    assert len(runtime.list_swarm_events("sw1")) == 1

    runtime.clear()

    assert runtime.list_swarm_events("sw1") == []
