from pydantic import BaseModel


class UsageSummary(BaseModel):
    total_sessions: int = 0
    total_cost_usd: float = 0.0
    total_messages: int = 0
    total_tool_calls: int = 0
    avg_session_duration_seconds: float = 0.0
    session_completion_rate: float = 0.0
    approval_rate: float = 0.0
    models_used: dict[str, int] = {}
    modes_used: dict[str, int] = {}
    top_tools: list[list] = []
