"""Side-effect-free runtime pattern audit for OpenSwarm.

LG-RUNTIME.1.A maps the current OpenSwarm runtime pieces to persistent-runtime
patterns such as state graph, checkpoints, event trace, evidence, candidates,
pending actions, timers, and memory. It does not read files, call providers,
emit events, mutate SwarmState, or create checkpoints.
"""

from __future__ import annotations

from typing import Any


RUNTIME_PATTERN_COMPONENTS: tuple[dict[str, Any], ...] = (
    {
        "component_id": "swarm_state",
        "runtime_pattern": "durable_thread_state",
        "current_surface": "backend.apps.agents.orchestration.models.SwarmState",
        "status": "present",
        "provides": [
            "contracts",
            "tasks",
            "messages",
            "decisions",
            "artifacts",
            "events",
            "approvals",
            "project_intake_state",
            "evidence",
            "final_evidence",
            "final_result",
            "implementation",
            "output_bridge",
            "implementation_state",
        ],
        "gaps": [
            "no formal checkpoint lineage",
            "no explicit state graph transition contract",
        ],
    },
    {
        "component_id": "swarm_store",
        "runtime_pattern": "persistent_state_store",
        "current_surface": "backend.apps.agents.orchestration.store.SwarmStore",
        "status": "present",
        "provides": [
            "file_backed_swarm_json",
            "save",
            "load",
            "list",
        ],
        "gaps": [
            "no checkpoint snapshots per step",
            "no replay index",
        ],
    },
    {
        "component_id": "event_trace_runtime",
        "runtime_pattern": "event_trace",
        "current_surface": "backend.apps.agents.runtime.events.EventTraceRuntime",
        "status": "present",
        "provides": [
            "session_events",
            "swarm_events",
            "ws_bridge",
            "swarm_event_persistence",
        ],
        "gaps": [
            "event taxonomy is not yet unified with runtime timers",
            "trace viewer UI is future work",
        ],
    },
    {
        "component_id": "runtime_timing",
        "runtime_pattern": "runtime_timer_contract",
        "current_surface": "backend.apps.runtime_timing.RuntimeTimerRecord",
        "status": "contract_only",
        "provides": [
            "timer_record",
            "start_timer",
            "finish_timer",
            "fail_timer",
            "cancel_timer",
            "duration_ms",
        ],
        "gaps": [
            "not yet integrated into backend lifecycle",
            "not yet persisted in SwarmState events",
            "not yet shown in UI",
        ],
    },
    {
        "component_id": "outputs_candidates",
        "runtime_pattern": "output_iteration_checkpoint",
        "current_surface": "backend.apps.outputs.outputs.OutputIterationRecord",
        "status": "present",
        "provides": [
            "candidate_iterations",
            "candidate_workspace",
            "base_workspace",
            "accept_candidate",
            "discard_candidate",
            "restore_iteration",
            "freshness_guard",
        ],
        "gaps": [
            "not generalized as runtime checkpoints for every step",
            "context inclusion/exclusion reasons are future work",
        ],
    },
    {
        "component_id": "pending_actions",
        "runtime_pattern": "waiting_user_state",
        "current_surface": "backend.apps.swarms.pending_action_intelligence",
        "status": "present",
        "provides": [
            "confirm_pending_action",
            "cancel_pending_action",
            "update_pending_action",
            "explain_pending_action",
            "needs_clarification",
        ],
        "gaps": [
            "not yet represented as formal state graph transitions",
        ],
    },
    {
        "component_id": "dag_runtime",
        "runtime_pattern": "task_graph_execution",
        "current_surface": "backend.apps.agents.runtime.experimental_dag_*",
        "status": "present",
        "provides": [
            "dag_task_runner",
            "dag_chain_runner",
            "dag_dependency_runner",
            "dag_mini_runner",
            "dag_consolidator",
        ],
        "gaps": [
            "checkpoint/resume contract is not yet formalized",
            "state transition audit is future work",
        ],
    },
    {
        "component_id": "mini_agent_runtime",
        "runtime_pattern": "specialized_agent_execution",
        "current_surface": "backend.apps.agents.runtime.mini_agent_runtime.MiniAgentRuntime",
        "status": "present",
        "provides": [
            "mini_agent_provider_context",
            "runtime_state",
            "tool_policy",
            "evidence_contract",
        ],
        "gaps": [
            "reusable miniagent profile persistence is future work",
            "MiniAgentCard Context Used UI is future work",
        ],
    },
    {
        "component_id": "project_memory",
        "runtime_pattern": "long_term_project_memory_projection",
        "current_surface": "backend.apps.swarms.project_memory",
        "status": "present",
        "provides": [
            "project_memory_manifest",
            "decisions",
            "outputs",
            "iterations",
            "artifacts",
            "evidence",
            "constraints",
            "open_questions",
        ],
        "gaps": [
            "memory write candidate gate is future work",
            "graph memory and invalidation are future work",
        ],
    },
    {
        "component_id": "context_selection",
        "runtime_pattern": "context_retrieval_policy_contract",
        "current_surface": "backend.apps.swarms.context_selection",
        "status": "present",
        "provides": [
            "selected_sources",
            "excluded_sources",
            "missing_sources",
            "budget",
            "freshness_refs",
            "summary",
        ],
        "gaps": [
            "source ranking is future work",
            "integration with SwarmState sources is future work",
        ],
    },
)


def build_runtime_pattern_audit() -> dict[str, Any]:
    """Return the current conceptual runtime audit without inspecting live state."""

    components = [dict(component) for component in RUNTIME_PATTERN_COMPONENTS]
    present = [item for item in components if item.get("status") == "present"]
    contract_only = [item for item in components if item.get("status") == "contract_only"]
    gaps = [
        {
            "component_id": item["component_id"],
            "gaps": list(item.get("gaps") or []),
        }
        for item in components
        if item.get("gaps")
    ]

    return {
        "audit_id": "LG-RUNTIME.1.A",
        "status": "minimal_audit",
        "implementation_scope": "side_effect_free_contract_only",
        "components": components,
        "summary": {
            "component_count": len(components),
            "present_count": len(present),
            "contract_only_count": len(contract_only),
            "gap_count": sum(len(item["gaps"]) for item in gaps),
            "runtime_deep_implementation_deferred": True,
        },
        "gaps": gaps,
        "next_recommendations": [
            "Use existing SwarmState, events, outputs, candidates, pending actions, evidence and project memory as CTX-RET sources.",
            "Do not create a parallel runtime for CTX-RET.",
            "Design EVAL-HARNESS around existing evidence, events and candidate/output iteration surfaces.",
            "Defer LG-RUNTIME.2+ until CTX-RET and EVAL-HARNESS contracts are clear.",
        ],
    }


def runtime_audit_component_map() -> dict[str, dict[str, Any]]:
    """Return components keyed by component_id for tests and future callers."""

    return {str(item["component_id"]): dict(item) for item in RUNTIME_PATTERN_COMPONENTS}
