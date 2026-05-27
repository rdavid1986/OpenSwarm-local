from backend.apps.swarms.context_selection import (
    build_context_selection_policy,
    build_ranked_context_selection_policy,
    normalize_context_selection_value,
    normalize_context_source,
    rank_context_sources,
    score_context_source,
    summarize_context_selection_policy,
)


def test_context_selection_policy_defaults_without_inventing_state():
    policy = build_context_selection_policy()

    assert policy["request_id"] is None
    assert policy["scope"] == "missing"
    assert policy["mode"] == "missing"
    assert policy["task_kind"] == "missing"
    assert policy["user_goal"] == "missing"
    assert policy["selected_sources"] == []
    assert policy["excluded_sources"] == []
    assert policy["required_sources_missing"] == []
    assert policy["allowed_files"] == []
    assert policy["forbidden_files"] == []
    assert policy["context_budget_used"] == 0
    assert policy["context_budget_total"] == 0
    assert policy["context_budget_source"] == "missing"
    assert policy["confidence"] == 0.0
    assert policy["fallback_used"] is False


def test_context_selection_policy_preserves_context_refs_and_budget():
    policy = build_context_selection_policy(
        request_id="req-1",
        scope="mini_agent",
        mode="swarm_card",
        task_kind="frontend_patch",
        user_goal="Cambiar el hero visual",
        selected_sources=[
            {
                "source_kind": "filesystem",
                "source_id": "frontend/src/App.tsx",
                "reason": "allowed_file_for_task",
                "freshness": "fresh",
                "confidence": 0.9,
                "budget_cost": 250,
            },
            {
                "source_kind": "evidence",
                "source_id": "evidence-1",
                "reason": "validates_previous_output",
            },
        ],
        excluded_sources=[
            {
                "source_kind": "filesystem",
                "source_id": "backend/main.py",
                "reason": "forbidden_file",
            }
        ],
        required_sources_missing=[
            {
                "source_kind": "runtime_checkpoints",
                "source_id": "checkpoint-1",
                "reason": "not_available_to_caller",
            }
        ],
        allowed_files=["frontend/src/App.tsx"],
        relevant_files=["frontend/src/styles.css"],
        forbidden_files=["backend/main.py"],
        evidence_refs=["evidence-1"],
        artifact_refs=["artifact-1"],
        output_refs=["output-1"],
        candidate_refs=["candidate-1"],
        memory_refs=["memory-1"],
        dependency_output_refs=["task-0"],
        freshness_refs={"frontend/src/App.tsx": {"hash": "abc", "fresh": True}},
        context_budget_used=1200,
        context_budget_total=32000,
        context_budget_source="configured",
        selection_reason="task_specific_context",
        risk_notes=["backend excluded"],
        confidence=0.8,
        fallback_used=True,
    )

    assert policy["scope"] == "mini_agent"
    assert policy["selected_sources"][0]["source_kind"] == "filesystem"
    assert policy["selected_sources"][0]["source_id"] == "frontend/src/App.tsx"
    assert policy["selected_sources"][0]["budget_cost"] == 250
    assert policy["excluded_sources"][0]["status"] == "excluded"
    assert policy["required_sources_missing"][0]["status"] == "missing"
    assert policy["allowed_files"] == ["frontend/src/App.tsx"]
    assert policy["forbidden_files"] == ["backend/main.py"]
    assert policy["evidence_refs"] == ["evidence-1"]
    assert policy["freshness_refs"]["frontend/src/App.tsx"]["fresh"] is True
    assert policy["context_budget_used"] == 1200
    assert policy["context_budget_total"] == 32000
    assert policy["context_budget_source"] == "configured"
    assert policy["confidence"] == 0.8
    assert policy["fallback_used"] is True


def test_context_source_unknown_kind_is_explicit_not_invented():
    source = normalize_context_source({"source_kind": "made_up", "source_id": "x"})

    assert source["source_kind"] == "unknown"
    assert source["source_id"] == "x"
    assert source["reason"] == "caller_provided"


def test_context_selection_summary_is_compact():
    policy = build_context_selection_policy(
        scope="mini_agent",
        task_kind="debug",
        selected_sources=[{"source_kind": "filesystem", "source_id": "a.py"}],
        excluded_sources=[{"source_kind": "filesystem", "source_id": "b.py"}],
        required_sources_missing=[{"source_kind": "evidence", "source_id": "e1"}],
        context_budget_used=10,
        context_budget_total=100,
        context_budget_source="configured",
    )

    summary = summarize_context_selection_policy(policy)

    assert "scope=mini_agent" in summary
    assert "task_kind=debug" in summary
    assert "selected=1" in summary
    assert "excluded=1" in summary
    assert "missing=1" in summary
    assert "budget=10/100" in summary
    assert "source=configured" in summary


def test_normalize_context_selection_value_is_bounded():
    value = normalize_context_selection_value(
        {
            "long": "x" * 1000,
            "items": list(range(50)),
            "nested": {"b": 2, "a": None},
        }
    )

    assert len(value["long"]) == 600
    assert len(value["items"]) == 24
    assert value["nested"] == {"a": None, "b": 2}


def test_score_context_source_rewards_relevant_fresh_allowed_evidence():
    scored = score_context_source(
        {
            "source_kind": "filesystem",
            "source_id": "frontend/src/App.tsx",
            "status": "selected",
            "freshness": "fresh",
            "confidence": 0.8,
            "budget_cost": 500,
            "refs": {"evidence_refs": ["evidence-1"]},
            "metadata": {
                "directly_related": True,
                "allowed": True,
                "has_evidence": True,
            },
        }
    )

    assert scored["rank_score"] > 80
    assert "selected" in scored["rank_reasons"]
    assert "fresh" in scored["rank_reasons"]
    assert "directly_related" in scored["rank_reasons"]
    assert "allowed" in scored["rank_reasons"]
    assert "has_evidence" in scored["rank_reasons"]


def test_score_context_source_penalizes_forbidden_blocked_or_stale_context():
    scored = score_context_source(
        {
            "source_kind": "filesystem",
            "source_id": "backend/main.py",
            "status": "blocked",
            "freshness": "stale",
            "confidence": 0.9,
            "metadata": {
                "directly_related": True,
                "forbidden": True,
                "risk": "high",
            },
        }
    )

    assert scored["rank_score"] < -150
    assert "blocked" in scored["rank_reasons"]
    assert "forbidden" in scored["rank_reasons"]
    assert "risk_penalty" in scored["rank_reasons"]


def test_rank_context_sources_orders_best_context_first():
    ranked = rank_context_sources(
        [
            {
                "source_kind": "filesystem",
                "source_id": "backend/main.py",
                "status": "blocked",
                "metadata": {"forbidden": True},
            },
            {
                "source_kind": "filesystem",
                "source_id": "frontend/src/App.tsx",
                "status": "selected",
                "freshness": "fresh",
                "confidence": 0.8,
                "metadata": {"directly_related": True, "allowed": True},
            },
            {
                "source_kind": "docs",
                "source_id": "README.md",
                "status": "selected",
                "confidence": 0.2,
            },
        ]
    )

    assert ranked[0]["source_id"] == "frontend/src/App.tsx"
    assert ranked[-1]["source_id"] == "backend/main.py"


def test_build_ranked_context_selection_policy_ranks_selected_sources():
    policy = build_ranked_context_selection_policy(
        scope="mini_agent",
        task_kind="frontend_patch",
        selected_sources=[
            {
                "source_kind": "docs",
                "source_id": "README.md",
                "confidence": 0.1,
            },
            {
                "source_kind": "filesystem",
                "source_id": "frontend/src/App.tsx",
                "freshness": "fresh",
                "confidence": 0.9,
                "metadata": {"directly_related": True, "allowed": True},
            },
        ],
    )

    assert policy["selected_sources"][0]["source_id"] == "frontend/src/App.tsx"
    assert "rank_score" in policy["selected_sources"][0]
