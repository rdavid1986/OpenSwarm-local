"""Canonical mode identifiers and aliases for AgentCard and SwarmCard.

This module is intentionally side-effect free. It does not read or write mode
JSON files and does not depend on FastAPI. It only normalizes mode identifiers
used by Agent, Swarm, Response Intelligence, Skill Builder and future Refine.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Final, Mapping


CANONICAL_MODE_IDS: Final[frozenset[str]] = frozenset({
    "agent",
    "ask",
    "plan",
    "app_builder",
    "skill_builder",
    "debug",
    "refine",
})

MODE_ID_ALIASES: Final[Mapping[str, str]] = MappingProxyType({
    "agent": "agent",
    "ask": "ask",
    "chat": "ask",
    "plan": "plan",
    "debug": "debug",
    "app_builder": "app_builder",
    "app-builder": "app_builder",
    "view-builder": "app_builder",
    "view_builder": "app_builder",
    "skill_builder": "skill_builder",
    "skill-builder": "skill_builder",
    "refine": "refine",
    "output_refine": "refine",
    "output-refine": "refine",
    "candidate_refinement": "refine",
    "candidate-refinement": "refine",
})


def normalize_mode_id(value: str | None, *, default: str = "ask") -> str:
    """Return the canonical mode id for known Agent/Swarm aliases."""
    fallback = MODE_ID_ALIASES.get(str(default or "ask").strip().lower(), "ask")
    raw = str(value or "").strip().lower()
    if not raw:
        return fallback
    return MODE_ID_ALIASES.get(raw, fallback)


def is_known_mode_id(value: str | None) -> bool:
    """Return true when value is a known canonical mode id or alias."""
    raw = str(value or "").strip().lower()
    return raw in MODE_ID_ALIASES


def mode_aliases(canonical_mode_id: str | None) -> list[str]:
    """Return all aliases for a canonical mode id, sorted for stable tests/UI."""
    canonical = normalize_mode_id(canonical_mode_id)
    return sorted(alias for alias, target in MODE_ID_ALIASES.items() if target == canonical)


def is_project_mode(value: str | None) -> bool:
    """Return true for modes that usually need project/context clarification."""
    return normalize_mode_id(value) in {"plan", "app_builder", "skill_builder", "debug", "refine"}
