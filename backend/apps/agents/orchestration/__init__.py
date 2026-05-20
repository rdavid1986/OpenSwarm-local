"""Minimal swarm orchestration primitives.

Phase 9 is intentionally non-executing: it persists swarm/task/agent-contract
state but does not launch AgentManager sessions yet.
"""

from .models import (
    AgentContract,
    AgentRole,
    AgentToAgentMessage,
    SwarmState,
    SwarmStatus,
    TaskNode,
    TaskStatus,
)
from .store import SwarmStore, swarm_store
from .orchestrator import SwarmOrchestrator, swarm_orchestrator


def __getattr__(name: str):
    if name in {"SwarmMVPExecutor", "swarm_mvp_executor"}:
        from .executor import SwarmMVPExecutor, swarm_mvp_executor

        return {
            "SwarmMVPExecutor": SwarmMVPExecutor,
            "swarm_mvp_executor": swarm_mvp_executor,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "AgentContract",
    "AgentRole",
    "AgentToAgentMessage",
    "SwarmOrchestrator",
    "SwarmMVPExecutor",
    "SwarmState",
    "SwarmStatus",
    "SwarmStore",
    "TaskNode",
    "TaskStatus",
    "swarm_orchestrator",
    "swarm_mvp_executor",
    "swarm_store",
]
