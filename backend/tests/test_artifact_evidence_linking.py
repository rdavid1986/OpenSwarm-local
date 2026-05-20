from pathlib import Path

from backend.apps.agents.orchestration.executor import SwarmMVPExecutor
from backend.apps.agents.orchestration.models import AgentContract, EvidenceRecord
from backend.apps.agents.orchestration.orchestrator import SwarmOrchestrator
from backend.apps.agents.orchestration.store import SwarmStore
from backend.apps.agents.runtime.experimental_dag_task_runner import ExperimentalDAGTaskRunner
from backend.apps.agents.runtime.mini_agent_runtime import MiniAgentRuntimeResult


def test_dag_task_artifact_links_matching_evidence_id(tmp_path: Path):
    task_id = "task-1"
    contract = AgentContract(role="DocumentationAgent", objective="Create artifact")
    evidence = EvidenceRecord(
        kind="file_created",
        task_id=task_id,
        agent_id=contract.id,
        tool_call_id="write-1",
        tool_name="Write",
        file_path="README.md",
        action="created",
    )
    result = MiniAgentRuntimeResult(
        status="completed",
        task_id=task_id,
        agent_contract_id=contract.id,
        final_message=None,
        tool_history=[
            {
                "call_id": "write-1",
                "tool": "Write",
                "ok": True,
                "result": {"path": "README.md", "absolute_path": str(tmp_path / "README.md"), "bytes": 10},
            }
        ],
    )

    artifacts = ExperimentalDAGTaskRunner._artifacts_from_tool_history(
        task_id=task_id,
        contract=contract,
        result=result,
        workspace=tmp_path,
        evidence_records=[evidence],
    )

    assert artifacts[0]["evidence_id"] == evidence.id
    assert artifacts[0]["evidence_ref"] == "write-1"


def test_swarm_mvp_executor_links_readme_artifact_to_write_evidence(tmp_path: Path, monkeypatch):
    import backend.apps.agents.orchestration.store as store_module

    store = SwarmStore(root=tmp_path / "swarms")
    monkeypatch.setattr(store_module, "swarm_store", store)
    orchestrator = SwarmOrchestrator(store=store)
    executor = SwarmMVPExecutor(store=store)
    swarm = orchestrator.create_swarm(user_prompt="Crear README")

    result = executor.run_readme_review_mvp(swarm.id, workspace_path=str(tmp_path / "workspace"))

    artifact = next(item for item in result.artifacts if item.get("path") == "README.md")
    evidence_ids = {item.id for item in result.evidence}

    claim_guard = result.final_result.get("claim_guard") or {}
    claim_checks = claim_guard.get("checks") or {}

    assert artifact["evidence_id"] in evidence_ids
    assert artifact["evidence_ref"]
    assert result.final_result["status"] == "completed"
    assert claim_guard["status"] == "verified"
    assert claim_checks["artifact_supported"] is True
    assert claim_checks["review_supported"] is True
    assert claim_checks["workspace_supported"] is True
    assert claim_checks["task_refs_supported"] is True
