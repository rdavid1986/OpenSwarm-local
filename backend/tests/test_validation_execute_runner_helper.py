import tempfile
from pathlib import Path
from uuid import uuid4

from backend.apps.agents.orchestration.models import AgentContract, SwarmState, TaskNode
from backend.apps.agents.runtime.experimental_dag_dependency_runner import ExperimentalDAGDependencyRunner
from backend.apps.agents.runtime.experimental_task_type_registry import get_experimental_task_spec


def test_validation_execute_runner_helper_runs_safe_py_compile_check():
    workspace = Path(tempfile.mkdtemp(prefix="openswarm-validation-execute-")).resolve()
    (workspace / "ok.py").write_text("x = 1\n", encoding="utf-8")

    spec = get_experimental_task_spec("validation_execute")
    contract = AgentContract(
        id=str(uuid4()),
        role="TesterAgent",
        objective="Run safe validation checks.",
        capabilities=["safe validation"],
        allowed_tools=list(spec.allowed_tools),
        output_contract=dict(spec.output_contract),
    )
    task = TaskNode(
        title=spec.title,
        objective="Run safe validation checks.",
        assigned_contract_id=contract.id,
    )
    swarm = SwarmState(
        id="test-swarm",
        title="Test swarm",
        goal="test",
        user_prompt="test",
        contracts=[contract],
        tasks=[task],
    )

    result = ExperimentalDAGDependencyRunner()._run_validation_execute_task(
        swarm=swarm,
        task=task,
        contract=contract,
        workspace_path=str(workspace),
    )

    assert result["status"] == "passed"
    assert result["commands"][0]["command"] == "python -m py_compile ok.py"
    assert result["commands"][0]["ok"] is True
    assert task.status == "completed"
    assert task.validations[-1]["commands"][0]["command"] == "python -m py_compile ok.py"
    assert "command_executed" in task.evidence
    assert swarm.tool_history
    assert swarm.tool_history[-1]["tool"] == "SafeShell"
