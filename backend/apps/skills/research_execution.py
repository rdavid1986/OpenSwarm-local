"""Approval-gated web research execution for Skill Candidates.

This module may execute web search through the existing /api/web search
implementation, but it only records research evidence. It never modifies
candidate content, installs skills, approves install, activates tools, or
activates MCP.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from backend.apps.skills.models import SkillSpecCandidate
from backend.apps.skills.research_contract import build_skill_candidate_research_contract

SearchFn = Callable[[str, int], Awaitable[dict[str, Any]]]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_urls(results_text: str) -> list[str]:
    urls: list[str] = []
    for token in str(results_text or "").replace("\n", " ").split():
        cleaned = token.strip("()[]{}<>.,;:'\"")
        if cleaned.startswith(("http://", "https://")) and cleaned not in urls:
            urls.append(cleaned)
    return urls[:10]


async def _default_search(query: str, num_results: int) -> dict[str, Any]:
    from backend.apps.web.web import SearchBody, search

    return await search(SearchBody(query=query, num_results=num_results))


async def execute_skill_candidate_research(
    candidate: SkillSpecCandidate,
    *,
    search_fn: SearchFn | None = None,
    max_queries: int = 3,
    num_results: int = 5,
) -> tuple[SkillSpecCandidate, dict[str, Any]]:
    if not bool(getattr(candidate, "research_approved", False)):
        raise ValueError("skill_research_requires_explicit_approval")

    contract = build_skill_candidate_research_contract(candidate)
    if not contract.get("requires_web_research"):
        raise ValueError("skill_research_not_required")

    queries = [str(q).strip() for q in (contract.get("research_queries") or []) if str(q).strip()]
    if not queries:
        raise ValueError("skill_research_has_no_queries")

    runner = search_fn or _default_search
    evidence: list[dict[str, Any]] = []
    executed_at = _utc_now()

    for query in queries[: max(1, max_queries)]:
        result = await runner(query, num_results)
        results_text = str(result.get("results") or "")
        evidence.append({
            "kind": "web_search_result",
            "query": query,
            "backend": str(result.get("backend") or "unknown"),
            "results": results_text,
            "urls": _extract_urls(results_text),
            "executed_at": executed_at,
        })

    existing = [item for item in (getattr(candidate, "research_evidence", []) or []) if isinstance(item, dict)]
    updated = candidate.model_copy(update={"research_evidence": existing + evidence})
    updated_contract = build_skill_candidate_research_contract(updated)

    return updated, {
        "ok": True,
        "contract": updated_contract,
        "evidence": evidence,
        "audit": {
            "event": "skill_candidate_web_research_executed",
            "candidate_id": updated.candidate_id,
            "research_approved": bool(getattr(updated, "research_approved", False)),
            "web_research_executed": bool(evidence),
            "evidence_count": len(evidence),
            "can_mutate_candidate": False,
            "can_install_skill": False,
            "can_activate_tools": False,
            "can_activate_mcp": False,
        },
    }
