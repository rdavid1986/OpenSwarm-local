"""Provider-agnostic runtime contracts for OpenSwarm agents.

This package is intentionally small in Phase 3. It defines stable boundary
types before Claude SDK and Ollama are wrapped behind adapters. Importing it
must not start providers, mutate sessions, or change the existing AgentManager
flow.
"""

from .provider import (
    ProviderAdapter,
    ProviderCapabilities,
    ProviderEvent,
    ProviderEventType,
    ProviderTurnContext,
)
from .approvals import (
    ApprovalDecision,
    ApprovalRequestEnvelope,
    ApprovalRuntime,
    approval_runtime,
)
from .events import (
    EventTraceRuntime,
    TraceEvent,
    TraceEventType,
    event_trace_runtime,
)
from .policy import PolicyDecision, PolicyRuntime, policy_runtime
from .tools import (
    ToolCall,
    ToolExecutionContext,
    ToolResolution,
    ToolResult,
    ToolRuntime,
    ToolSpec,
    tool_runtime,
)
from .tool_mapping import LEGACY_TOOL_NAME_MAP, map_tool_call, normalize_tool_input, normalize_tool_name
from .provider_tool_bridge import (
    ProviderToolBridge,
    ProviderToolBridgeResult,
    ProviderToolCallEnvelope,
    provider_tool_bridge,
)
from .provider_turn_harness import (
    FakeProviderAdapter,
    ProviderTurnHarness,
    ProviderTurnHarnessResult,
)
from .mini_agent_runtime import (
    MiniAgentRuntime,
    MiniAgentRuntimeContext,
    MiniAgentRuntimeResult,
    mini_agent_runtime,
)

__all__ = [
    "ApprovalDecision",
    "ApprovalRequestEnvelope",
    "ApprovalRuntime",
    "EventTraceRuntime",
    "ProviderAdapter",
    "ProviderCapabilities",
    "ProviderEvent",
    "ProviderEventType",
    "ProviderToolBridge",
    "ProviderToolBridgeResult",
    "ProviderToolCallEnvelope",
    "ProviderTurnHarness",
    "ProviderTurnHarnessResult",
    "FakeProviderAdapter",
    "MiniAgentRuntime",
    "MiniAgentRuntimeContext",
    "MiniAgentRuntimeResult",
    "ProviderTurnContext",
    "PolicyDecision",
    "PolicyRuntime",
    "TraceEvent",
    "TraceEventType",
    "ToolCall",
    "ToolExecutionContext",
    "ToolResolution",
    "ToolResult",
    "ToolRuntime",
    "ToolSpec",
    "LEGACY_TOOL_NAME_MAP",
    "approval_runtime",
    "event_trace_runtime",
    "map_tool_call",
    "mini_agent_runtime",
    "normalize_tool_input",
    "normalize_tool_name",
    "policy_runtime",
    "provider_tool_bridge",
    "tool_runtime",
]
