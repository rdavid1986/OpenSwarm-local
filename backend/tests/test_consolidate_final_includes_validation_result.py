from backend.apps.agents.runtime.experimental_dag_consolidator import ExperimentalDAGConsolidator
from backend.apps.agents.orchestration.models import AgentContract, SwarmState, TaskNode


class MemoryStore:
    def __init__(self, swarm):
        self.swarm = swarm

    def load(self, swarm_id):
        return self.swarm

    def save(self, swarm):
        self.swarm = swarm
        return swarm


def test_consolidate_final_includes_validation_result():
    architecture = TaskNode(
        id="task-architecture",
        title="Execute architecture plan",
        description="Generate architecture plan",
        objective="Generate architecture plan",
        assigned_agent_id="architect",
        status="completed",
    )
    architecture.evidence.append(
        {
            "kind": "architecture_plan_result",
            "status": "ready",
            "architecture_plan": {
                "status": "ready",
                "summary": "Architecture plan generated",
                "components": [],
                "constraints": [],
                "risks": [],
            },
        }
    )

    frontend = TaskNode(
        id="task-frontend",
        title="Execute frontend plan",
        description="Generate frontend plan",
        objective="Generate frontend plan",
        assigned_agent_id="frontend",
        depends_on=[architecture.id],
        status="completed",
    )
    frontend.evidence.append(
        {
            "kind": "frontend_plan_result",
            "status": "ready",
            "frontend_plan": {
                "status": "ready",
                "summary": "Frontend plan generated",
                "components": [],
                "routes": [],
                "constraints": [],
                "risks": [],
            },
        }
    )

    worker = TaskNode(
        id="task-worker",
        title="Create README",
        description="Create README.md",
        objective="Create README.md",
        task_type="create_readme",
        assigned_agent_id="worker",
        depends_on=[frontend.id],
        status="completed",
    )
    reviewer = TaskNode(
        id="task-reviewer",
        title="Review README",
        description="Review README.md",
        objective="Review README.md",
        task_type="review_readme",
        assigned_agent_id="reviewer",
        depends_on=[worker.id],
        status="completed",
    )
    validation = TaskNode(
        id="task-validation",
        title="Execute safe validation checks",
        description="Execute safe validation checks",
        objective="Execute safe validation checks",
        task_type="validation_execute",
        assigned_agent_id="tester",
        depends_on=[reviewer.id],
        status="completed",
    )
    validation.validations.append(
        {
            "kind": "validation_result",
            "status": "passed",
            "commands": [{"command": "python -m py_compile ok.py", "ok": True}],
            "evidence": ["command_executed"],
        }
    )
    consolidate = TaskNode(
        id="task-consolidate",
        title="Consolidate evidence final",
        description="Consolidate final evidence",
        objective="Consolidate final evidence",
        task_type="consolidate_final",
        assigned_agent_id="coordinator",
        depends_on=[validation.id],
        status="pending",
    )

    artifact = {
        "id": "artifact-readme",
        "task_id": worker.id,
        "path": "README.md",
        "evidence_id": "evidence-write",
    }
    reviewer.evidence.append(
        {
            "kind": "review_result",
            "artifact_id": artifact["id"],
            "artifact_path": "README.md",
            "status": "approved",
            "required_read_satisfied": True,
        }
    )

    swarm = SwarmState(
        id="swarm-validation-consolidate",
        title="Validation consolidate test",
        user_prompt="Create and validate README.md",
        contracts=[
            AgentContract(agent_id="architect", role="ArchitectAgent", objective="Generate architecture plan"),
            AgentContract(agent_id="frontend", role="FrontendAgent", objective="Generate frontend plan"),
            AgentContract(agent_id="worker", role="DocumentationAgent", objective="Create README.md"),
            AgentContract(agent_id="reviewer", role="ReviewerAgent", objective="Review README.md"),
            AgentContract(agent_id="tester", role="TesterAgent", objective="Execute safe validation checks"),
            AgentContract(agent_id="coordinator", role="CoordinatorAgent", objective="Consolidate final result"),
        ],
        tasks=[architecture, frontend, worker, reviewer, validation, consolidate],
        artifacts=[artifact],
        tool_history=[
            {"tool": "Write", "task_id": worker.id, "status": "completed", "ok": True, "result": {"path": "README.md"}},
            {"tool": "Read", "task_id": reviewer.id, "status": "completed", "ok": True, "result": {"path": "README.md"}},
            {"tool": "SafeShell", "task_id": validation.id, "status": "completed", "ok": True, "result": {"command": "python -m py_compile ok.py"}},
        ],
    )

    result = ExperimentalDAGConsolidator(store=MemoryStore(swarm)).consolidate_final(swarm_id=swarm.id)

    assert result.ok is True
    assert result.status == "completed"
    assert result.final_result["architecture_plan_result"]["status"] == "ready"
    assert result.final_result["frontend_plan_result"]["status"] == "ready"
    assert result.final_result["validation_result"]["status"] == "passed"
    assert result.final_result["validation_result"]["commands"][0]["command"] == "python -m py_compile ok.py"
    assert architecture.id in result.final_result["completed_tasks"]
    assert frontend.id in result.final_result["completed_tasks"]
    assert validation.id in result.final_result["completed_tasks"]

    evidence_kinds = [item.get("kind") for item in result.final_evidence]
    assert "architecture_plan_result" in evidence_kinds
    assert "frontend_plan_result" in evidence_kinds
    assert "validation_result" in evidence_kinds

    tool_items = next(item for item in result.final_evidence if item.get("kind") == "tool_history_summary")
    assert any(item.get("tool") == "SafeShell" and item.get("task_id") == validation.id for item in tool_items["tools"])
