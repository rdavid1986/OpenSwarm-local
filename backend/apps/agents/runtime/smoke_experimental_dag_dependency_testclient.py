"""TestClient smoke for experimental dependency-ordered README DAG runner."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi.testclient import TestClient

from backend.apps.agents.runtime.smoke_experimental_worker_review_testclient import FakeChainOllamaAdapter


os.environ["OPENSWARM_EXPERIMENTAL_MINI_RUNTIME"] = "1"
os.environ["OPENSWARM_EXPERIMENTAL_DAG_TASK_RUNTIME"] = "1"
os.environ["OPENSWARM_EXPERIMENTAL_DAG_CHAIN_RUNTIME"] = "1"
os.environ["OPENSWARM_EXPERIMENTAL_DAG_CONSOLIDATE_RUNTIME"] = "1"
os.environ["OPENSWARM_EXPERIMENTAL_DAG_MINI_RUNNER"] = "1"
os.environ["OPENSWARM_EXPERIMENTAL_DAG_DEPENDENCY_RUNNER"] = "1"
os.environ["OPENSWARM_EXPERIMENTAL_PLANNER_AGENT_RUNTIME"] = "1"

from backend.apps.agents.orchestration.models import TaskNode  # noqa: E402
from backend.apps.agents.providers.ollama_adapter import OllamaAdapter  # noqa: E402
from backend.apps.agents.runtime.experimental_dag_chain_runner import ExperimentalDAGChainRunner  # noqa: E402
from backend.apps.agents.runtime.experimental_dag_consolidator import ExperimentalDAGConsolidator  # noqa: E402
from backend.apps.agents.runtime.experimental_dag_dependency_runner import ExperimentalDAGDependencyRunner  # noqa: E402
from backend.apps.agents.runtime.provider import ProviderEvent, ProviderTurnContext  # noqa: E402
from backend.apps.swarms import swarms as swarms_module  # noqa: E402
from backend.main import app  # noqa: E402


class FakePlannerAdapter(OllamaAdapter):
    instance_count = 0
    mode = "valid"

    def __init__(self, **kwargs: Any) -> None:
        kwargs.pop("allow_network", None)
        super().__init__(allow_network=False, **kwargs)
        FakePlannerAdapter.instance_count += 1

    def healthcheck(self, timeout_seconds: float = 2.0) -> dict[str, Any]:
        return {"ok": True, "mock": True}

    async def run_turn(self, context: ProviderTurnContext) -> AsyncIterator[ProviderEvent]:
        content = (
            '{"status":"plan_validated","reason":"README DAG dependencies are valid."}'
            if FakePlannerAdapter.mode == "valid"
            else '{"status":"plan_rejected","reason":"Rejected by fake planner."}'
        )
        yield ProviderEvent(
            type="provider_request",
            session_id=context.session_id,
            agent_id=context.agent_id,
            task_id=context.task_id,
            payload={"provider": self.id, "mock": True, "planner_mode": FakePlannerAdapter.mode},
        )
        yield ProviderEvent(
            type="message_final",
            session_id=context.session_id,
            agent_id=context.agent_id,
            task_id=context.task_id,
            payload={"message": {"role": "assistant", "content": content}},
        )


def main() -> int:
    FakeChainOllamaAdapter.instance_count = 0
    FakePlannerAdapter.instance_count = 0
    workspace = Path(tempfile.mkdtemp(prefix="openswarm-dag-deps-")).resolve()
    diagnostics: dict[str, Any] = {"workspace_path": str(workspace)}
    store = swarms_module.swarm_orchestrator.store
    chain_runner = ExperimentalDAGChainRunner(store=store, adapter_factory=FakeChainOllamaAdapter)
    swarms_module.experimental_dag_dependency_runner = ExperimentalDAGDependencyRunner(
        store=store,
        chain_runner=chain_runner,
        consolidator=ExperimentalDAGConsolidator(store=store),
        planner_adapter_factory=FakePlannerAdapter,
    )
    headers = {"x-api-key": "local-dev-token"}

    with TestClient(app) as client:
        swarm = client.post(
            "/api/swarms/create",
            headers=headers,
            json={
                "user_prompt": "Crea un README.md básico en el workspace, revisalo con un agente reviewer y reportá evidencia.",
                "workspace_path": str(workspace),
            },
        )
        if swarm.status_code != 200:
            return fail("create_swarm_failed", swarm.text, diagnostics)
        swarm_id = swarm.json()["id"]
        diagnostics["swarm_id"] = swarm_id

        payload = {
            "model": "qwen2.5-coder:14b",
            "allowed_tools": ["Read", "Write", "Edit", "SearchFiles", "SearchText"],
            "workspace_path": str(workspace),
            "max_turns": 4,
        }
        FakePlannerAdapter.mode = "valid"
        first = client.post(f"/api/swarms/{swarm_id}/experimental/run-dag-dependencies", headers=headers, json=payload)
        if first.status_code != 200:
            return fail("run_dag_dependencies_failed", first.text, diagnostics)
        first_body = first.json()
        second = client.post(f"/api/swarms/{swarm_id}/experimental/run-dag-dependencies", headers=headers, json=payload)
        if second.status_code != 200:
            return fail("rerun_dag_dependencies_failed", second.text, diagnostics)
        second_body = second.json()

        FakePlannerAdapter.mode = "reject"
        reject_swarm = client.post(
            "/api/swarms/create",
            headers=headers,
            json={"user_prompt": "Crea un README.md básico en el workspace.", "workspace_path": str(workspace / "reject")},
        ).json()
        rejected = client.post(f"/api/swarms/{reject_swarm['id']}/experimental/run-dag-dependencies", headers=headers, json={**payload, "workspace_path": str(workspace / "reject")})
        rejected_body = rejected.json()

        FakePlannerAdapter.mode = "valid"
        unknown_swarm = client.post(
            "/api/swarms/create",
            headers=headers,
            json={"user_prompt": "Crea un README.md básico en el workspace.", "workspace_path": str(workspace / "unknown")},
        ).json()
        state = store.load(unknown_swarm["id"])
        state.tasks.append(TaskNode(title="Unknown experimental task", objective="This should fail closed."))
        store.save(state)
        unknown = client.post(f"/api/swarms/{unknown_swarm['id']}/experimental/run-dag-dependencies", headers=headers, json={**payload, "workspace_path": str(workspace / "unknown")})
        unknown_body = unknown.json()

        allowed_tools_extra_body = run_contract_negative(
            client=client,
            headers=headers,
            store=store,
            workspace=workspace / "allowed-extra",
            payload=payload,
            mutate=lambda state: append_contract_tool(state, "Review README.md", "Write"),
        )
        output_contract_invalid_body = run_contract_negative(
            client=client,
            headers=headers,
            store=store,
            workspace=workspace / "bad-output",
            payload=payload,
            mutate=lambda state: replace_contract_output(state, "Create README.md", {"wrong": True}),
        )
        missing_contract_body = run_contract_negative(
            client=client,
            headers=headers,
            store=store,
            workspace=workspace / "missing-contract",
            payload=payload,
            mutate=lambda state: set_task_contract_id(state, "Create README.md", "missing-contract-id"),
        )

    diagnostics["result_summary"] = summarize(first_body)
    diagnostics["rerun_summary"] = summarize(second_body)
    diagnostics["rejected_summary"] = summarize(rejected_body)
    diagnostics["unknown_summary"] = summarize(unknown_body)
    diagnostics["allowed_tools_extra_summary"] = summarize(allowed_tools_extra_body)
    diagnostics["output_contract_invalid_summary"] = summarize(output_contract_invalid_body)
    diagnostics["missing_contract_summary"] = summarize(missing_contract_body)
    diagnostics["readme_exists"] = (workspace / "README.md").exists()

    validate_body(first_body, diagnostics)
    validate_body(second_body, diagnostics)
    if len(first_body.get("artifacts") or []) != len(second_body.get("artifacts") or []):
        return fail("artifact_duplicate", "Rerun changed artifact count", diagnostics)
    if len(first_body.get("messages") or []) != len(second_body.get("messages") or []):
        return fail("message_duplicate", "Rerun changed message count", diagnostics)
    if not all(item.get("action") == "skipped_completed" for item in second_body.get("execution_order", [])):
        return fail("rerun_not_skipped", "Expected rerun to skip completed tasks", diagnostics)
    if rejected_body.get("status") != "failed" or task_status(rejected_body, "Create README.md") == "completed":
        return fail("planner_rejection_failed_open", "Expected rejected planner to stop before Worker", diagnostics)
    if unknown_body.get("status") != "failed" or not any(err.get("error") == "unknown_task_type" for err in unknown_body.get("errors", [])):
        return fail("unknown_task_not_blocked", "Expected unknown task type to fail closed", diagnostics)
    validate_contract_negative(allowed_tools_extra_body, "allowed_tools_exceed_task_type", diagnostics)
    validate_contract_negative(output_contract_invalid_body, "output_contract_mismatch", diagnostics)
    validate_contract_negative(missing_contract_body, "missing_assigned_contract", diagnostics)

    print(json.dumps({"ok": True, **diagnostics}, ensure_ascii=False, indent=2))
    return 0


def run_contract_negative(
    *,
    client: TestClient,
    headers: dict[str, str],
    store: Any,
    workspace: Path,
    payload: dict[str, Any],
    mutate: Any,
) -> dict[str, Any]:
    FakePlannerAdapter.mode = "valid"
    workspace.mkdir(parents=True, exist_ok=True)
    swarm = client.post(
        "/api/swarms/create",
        headers=headers,
        json={"user_prompt": "Crea un README.md bÃ¡sico en el workspace.", "workspace_path": str(workspace)},
    ).json()
    before_fake_chain = FakeChainOllamaAdapter.instance_count
    before_fake_planner = FakePlannerAdapter.instance_count
    state = store.load(swarm["id"])
    mutate(state)
    store.save(state)
    response = client.post(
        f"/api/swarms/{swarm['id']}/experimental/run-dag-dependencies",
        headers=headers,
        json={**payload, "workspace_path": str(workspace)},
    )
    body = response.json()
    saved = store.load(swarm["id"])
    body["_diagnostics"] = {
        "status_code": response.status_code,
        "provider_instance_delta": (FakePlannerAdapter.instance_count - before_fake_planner)
        + (FakeChainOllamaAdapter.instance_count - before_fake_chain),
        "persisted_tool_history_count": len(saved.tool_history),
        "events": [event.get("type") for event in saved.events],
    }
    return body


def append_contract_tool(state: Any, task_title: str, tool: str) -> None:
    contract = contract_for_task_title(state, task_title)
    if tool not in contract.allowed_tools:
        contract.allowed_tools.append(tool)


def replace_contract_output(state: Any, task_title: str, output_contract: dict[str, Any]) -> None:
    contract = contract_for_task_title(state, task_title)
    contract.output_contract = output_contract


def set_task_contract_id(state: Any, task_title: str, contract_id: str) -> None:
    task = task_by_title(state, task_title)
    task.assigned_contract_id = contract_id


def contract_for_task_title(state: Any, task_title: str) -> Any:
    task = task_by_title(state, task_title)
    for contract in state.contracts:
        if contract.id == task.assigned_contract_id:
            return contract
    raise AssertionError(f"Contract not found for task: {task_title}")


def task_by_title(state: Any, task_title: str) -> Any:
    for task in state.tasks:
        if task.title == task_title:
            return task
    raise AssertionError(f"Task not found: {task_title}")


def validate_contract_negative(body: dict[str, Any], expected_code: str, diagnostics: dict[str, Any]) -> None:
    if body.get("status") != "failed" or body.get("ok") is not False:
        raise AssertionError(json.dumps({"error": "contract_negative_not_failed", "body": body, "diagnostics": diagnostics}, ensure_ascii=False, indent=2))
    if not any(err.get("error") == "contract_validation_failed" and err.get("code") == expected_code for err in body.get("errors", [])):
        raise AssertionError(json.dumps({"error": "contract_negative_wrong_error", "expected_code": expected_code, "body": body, "diagnostics": diagnostics}, ensure_ascii=False, indent=2))
    negative_diagnostics = body.get("_diagnostics") or {}
    if negative_diagnostics.get("provider_instance_delta") != 0:
        raise AssertionError(json.dumps({"error": "contract_negative_called_provider", "body": body, "diagnostics": diagnostics}, ensure_ascii=False, indent=2))
    if negative_diagnostics.get("persisted_tool_history_count") != 0:
        raise AssertionError(json.dumps({"error": "contract_negative_ran_tools", "body": body, "diagnostics": diagnostics}, ensure_ascii=False, indent=2))
    if "task_contract_validation_failed" not in negative_diagnostics.get("events", []):
        raise AssertionError(json.dumps({"error": "contract_negative_event_missing", "body": body, "diagnostics": diagnostics}, ensure_ascii=False, indent=2))


def summarize(body: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": body.get("ok"),
        "status": body.get("status"),
        "execution_order": [(i.get("title"), i.get("type"), i.get("action")) for i in body.get("execution_order", [])],
        "tasks": [(t.get("title"), t.get("status")) for t in body.get("tasks", [])],
        "final_result": body.get("final_result"),
        "final_evidence_count": len(body.get("final_evidence") or []),
        "tool_history": [(h.get("tool"), h.get("status"), h.get("ok")) for h in body.get("tool_history", [])],
        "artifact_count": len(body.get("artifacts") or []),
        "message_count": len(body.get("messages") or []),
    }


def validate_body(body: dict[str, Any], diagnostics: dict[str, Any]) -> None:
    def require(condition: bool, kind: str, message: str) -> None:
        if not condition:
            raise AssertionError(json.dumps({"error": kind, "message": message, "diagnostics": diagnostics}, ensure_ascii=False, indent=2))

    require(body.get("status") == "completed" and body.get("ok"), "not_completed", "Expected completed")
    for title in ("Plan task DAG", "Create README.md", "Review README.md", "Consolidate final evidence"):
        require(task_status(body, title) == "completed", "task_not_completed", f"Expected {title} completed")
    require(any(item.get("type") == "plan_reused" for item in body.get("execution_order", [])), "plan_missing", "Expected plan_reused")
    require(task_has_evidence(body, "Plan task DAG", "planner_result"), "planner_evidence_missing", "Expected planner_result evidence")
    require((body.get("final_result") or {}).get("status") == "completed", "final_result_missing", "Expected final_result completed")
    require(bool(body.get("final_evidence")), "final_evidence_missing", "Expected final_evidence")
    require(any(a.get("path") == "README.md" for a in body.get("artifacts", [])), "artifact_missing", "Expected README artifact")
    require(any(m.get("type") == "submit_artifact" for m in body.get("messages", [])), "submit_artifact_missing", "Expected submit_artifact")
    require(any(m.get("type") == "request_review" for m in body.get("messages", [])), "request_review_missing", "Expected request_review")
    tools = [(h.get("tool"), h.get("ok")) for h in body.get("tool_history", [])]
    require(("Write", True) in tools and ("Read", True) in tools, "tool_history_missing", "Expected Write and Read")


def task_status(body: dict[str, Any], title: str) -> str | None:
    for task in body.get("tasks") or []:
        if task.get("title") == title:
            return task.get("status")
    return None


def task_has_evidence(body: dict[str, Any], title: str, kind: str) -> bool:
    for task in body.get("tasks") or []:
        if task.get("title") == title:
            return any(item.get("kind") == kind for item in task.get("evidence", []))
    return False


def fail(kind: str, message: str, diagnostics: dict[str, Any]) -> int:
    print(json.dumps({"ok": False, "error": kind, "message": message, "diagnostics": diagnostics}, ensure_ascii=False, indent=2))
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as exc:
        print(exc)
        sys.exit(1)
