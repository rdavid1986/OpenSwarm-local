from backend.apps.swarms.context_selection import (
    apply_context_budget_exclusion_policy,
    apply_context_budget_to_policy,
    apply_context_inclusion_explanations,
    build_context_budget_summary,
    build_context_inclusion_explanations,
    build_context_selection_policy,
    build_ranked_context_selection_policy,
    explain_context_source_inclusion,
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

def test_context_budget_summary_calculates_reserved_remaining_and_status():
    summary = build_context_budget_summary(
        context_budget_total=32000,
        selected_sources=[
            {"source_kind": "filesystem", "source_id": "a.py", "budget_cost": 1200},
            {"source_kind": "evidence", "source_id": "e1", "budget_cost": 300},
        ],
        reserved_response_budget=4000,
        reserved_tool_budget=1000,
        reserved_evidence_budget=500,
        context_budget_source="configured",
    )

    assert summary["context_budget_total"] == 32000
    assert summary["context_budget_used"] == 1500
    assert summary["context_budget_reserved_total"] == 5500
    assert summary["context_budget_available_for_context"] == 26500
    assert summary["context_budget_remaining"] == 25000
    assert summary["context_budget_status"] == "within_budget"
    assert summary["context_budget_source"] == "configured"


def test_context_budget_summary_detects_overflow_without_inventing_context():
    summary = build_context_budget_summary(
        context_budget_total=4000,
        selected_sources=[
            {"source_kind": "filesystem", "source_id": "large.py", "budget_cost": 3500},
        ],
        reserved_response_budget=1000,
        reserved_tool_budget=250,
        reserved_evidence_budget=250,
    )

    assert summary["context_budget_used"] == 3500
    assert summary["context_budget_available_for_context"] == 2500
    assert summary["context_budget_status"] == "over_budget"
    assert summary["overflow_amount"] == 1000
    assert summary["overflow_strategy"] == "exclude_lowest_ranked_sources"


def test_apply_context_budget_to_policy_attaches_budget_summary():
    policy = build_context_selection_policy(
        selected_sources=[
            {"source_kind": "filesystem", "source_id": "frontend/src/App.tsx", "budget_cost": 700},
            {"source_kind": "docs", "source_id": "README.md", "budget_cost": 300},
        ],
        context_budget_total=8000,
        context_budget_source="configured",
    )

    enriched = apply_context_budget_to_policy(
        policy,
        reserved_response_budget=2000,
        reserved_tool_budget=500,
        reserved_evidence_budget=500,
        overflow_strategy="summarize_lowest_ranked_sources",
    )

    assert enriched["context_budget_used"] == 1000
    assert enriched["context_budget_total"] == 8000
    assert enriched["context_budget"]["context_budget_available_for_context"] == 5000
    assert enriched["context_budget"]["context_budget_remaining"] == 4000
    assert enriched["context_budget"]["overflow_strategy"] == "summarize_lowest_ranked_sources"

def test_apply_context_budget_exclusion_policy_preserves_overflow_as_excluded():
    policy = build_context_selection_policy(
        selected_sources=[
            {
                "source_kind": "filesystem",
                "source_id": "important.py",
                "freshness": "fresh",
                "confidence": 0.9,
                "budget_cost": 1000,
                "metadata": {"directly_related": True, "allowed": True},
            },
            {
                "source_kind": "docs",
                "source_id": "large_reference.md",
                "confidence": 0.1,
                "budget_cost": 3000,
            },
        ],
        context_budget_total=3000,
        context_budget_source="configured",
    )

    result = apply_context_budget_exclusion_policy(
        policy,
        reserved_response_budget=1000,
    )

    assert [source["source_id"] for source in result["selected_sources"]] == ["important.py"]
    assert result["excluded_sources"][0]["source_id"] == "large_reference.md"
    assert result["excluded_sources"][0]["status"] == "excluded"
    assert result["excluded_sources"][0]["reason"] == "excluded_by_context_budget"
    assert result["excluded_sources"][0]["metadata"]["excluded_by"] == "context_budget_policy"
    assert result["excluded_sources"][0]["metadata"]["excluded_reason"] == "context_budget_exceeded"
    assert result["context_budget"]["context_budget_status"] == "within_budget"
    assert result["context_budget_used"] == 1000


def test_apply_context_budget_exclusion_policy_keeps_existing_excluded_sources():
    policy = build_context_selection_policy(
        selected_sources=[
            {"source_kind": "filesystem", "source_id": "a.py", "budget_cost": 500},
        ],
        excluded_sources=[
            {"source_kind": "filesystem", "source_id": "forbidden.py", "reason": "forbidden_file"},
        ],
        context_budget_total=2000,
        context_budget_source="configured",
    )

    result = apply_context_budget_exclusion_policy(policy, reserved_response_budget=500)

    assert [source["source_id"] for source in result["selected_sources"]] == ["a.py"]
    assert any(source["source_id"] == "forbidden.py" for source in result["excluded_sources"])
    assert result["context_budget"]["context_budget_status"] == "within_budget"


def test_apply_context_budget_exclusion_policy_is_noop_when_budget_unknown():
    policy = build_context_selection_policy(
        selected_sources=[
            {"source_kind": "filesystem", "source_id": "a.py", "budget_cost": 500},
        ],
    )

    result = apply_context_budget_exclusion_policy(policy)

    assert [source["source_id"] for source in result["selected_sources"]] == ["a.py"]
    assert result["excluded_sources"] == []
    assert result["context_budget"]["context_budget_status"] == "unknown_budget"


def test_explain_context_source_inclusion_uses_existing_source_metadata():
    explanation = explain_context_source_inclusion(
        {
            "source_kind": "filesystem",
            "source_id": "frontend/src/App.tsx",
            "status": "selected",
            "reason": "allowed_file_for_task",
            "freshness": "fresh",
            "confidence": 0.85,
            "budget_cost": 700,
            "metadata": {
                "directly_related": True,
                "allowed": True,
                "has_evidence": True,
            },
        }
    )

    assert explanation["source_kind"] == "filesystem"
    assert explanation["source_id"] == "frontend/src/App.tsx"
    assert explanation["status"] == "selected"
    assert explanation["explanation_status"] == "included"
    assert explanation["reason"] == "allowed_file_for_task"
    assert explanation["freshness"] == "fresh"
    assert explanation["confidence"] == 0.85
    assert explanation["budget_cost"] == 700
    assert explanation["metadata"]["directly_related"] is True
    assert "allowed_file_for_task" in explanation["explanation_reasons"]
    assert "directly_related" in explanation["explanation_reasons"]
    assert "allowed" in explanation["explanation_reasons"]
    assert "has_evidence" in explanation["explanation_reasons"]


def test_explain_context_source_inclusion_preserves_budget_exclusion_reason():
    explanation = explain_context_source_inclusion(
        {
            "source_kind": "docs",
            "source_id": "large_reference.md",
            "status": "excluded",
            "reason": "excluded_by_context_budget",
            "confidence": 0.1,
            "budget_cost": 3000,
            "excluded_by": "context_budget_policy",
            "excluded_reason": "context_budget_exceeded",
        }
    )

    assert explanation["explanation_status"] == "excluded"
    assert explanation["excluded_by"] == "context_budget_policy"
    assert explanation["excluded_reason"] == "context_budget_exceeded"
    assert "excluded_by_context_budget" in explanation["explanation_reasons"]
    assert "context_budget_policy" in explanation["explanation_reasons"]
    assert "context_budget_exceeded" in explanation["explanation_reasons"]


def test_build_context_inclusion_explanations_groups_policy_sources():
    policy = build_context_selection_policy(
        selected_sources=[
            {
                "source_kind": "filesystem",
                "source_id": "frontend/src/App.tsx",
                "reason": "direct_task_file",
                "freshness": "fresh",
                "confidence": 0.9,
            }
        ],
        excluded_sources=[
            {
                "source_kind": "filesystem",
                "source_id": "backend/main.py",
                "reason": "forbidden_file",
                "metadata": {"forbidden": True},
            }
        ],
        required_sources_missing=[
            {
                "source_kind": "runtime_checkpoints",
                "source_id": "checkpoint-1",
                "reason": "not_available_to_caller",
            }
        ],
    )

    explanations = build_context_inclusion_explanations(policy)

    assert explanations["selected_sources"][0]["explanation_status"] == "included"
    assert explanations["excluded_sources"][0]["explanation_status"] == "excluded"
    assert explanations["required_sources_missing"][0]["explanation_status"] == "missing"
    assert explanations["selected_sources"][0]["reason"] == "direct_task_file"
    assert explanations["excluded_sources"][0]["reason"] == "forbidden_file"
    assert explanations["required_sources_missing"][0]["reason"] == "not_available_to_caller"


def test_apply_context_inclusion_explanations_attaches_trace_without_mutating_sources():
    policy = build_context_selection_policy(
        selected_sources=[
            {
                "source_kind": "filesystem",
                "source_id": "a.py",
                "reason": "allowed_file",
                "budget_cost": 500,
            }
        ],
        excluded_sources=[
            {
                "source_kind": "docs",
                "source_id": "old.md",
                "reason": "stale_context",
                "freshness": "stale",
            }
        ],
    )

    enriched = apply_context_inclusion_explanations(policy)

    assert enriched["selected_sources"] == policy["selected_sources"]
    assert enriched["excluded_sources"] == policy["excluded_sources"]
    assert enriched["context_inclusion_explanations"]["selected_sources"][0]["source_id"] == "a.py"
    assert enriched["context_inclusion_explanations"]["excluded_sources"][0]["source_id"] == "old.md"
    assert enriched["context_inclusion_explanations"]["excluded_sources"][0]["freshness"] == "stale"
