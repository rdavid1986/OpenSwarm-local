"""Model-assisted candidate refinement file update planning.

REFINE-REAL.1 keeps planning side-effect free: this module never mutates
Outputs, workspaces, Swarms, tools, or evidence. It only proposes text file
updates for a Candidate Output Iteration. Callers must apply guards before
executing returned updates.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable

from backend.apps.agents.providers.ollama_adapter import OllamaAdapter
from backend.apps.agents.runtime.provider import ProviderTurnContext


ALLOWED_CANDIDATE_FILES = {"index.html", "styles.css", "content.json", "schema.json"}


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _extract_json_object(text: str) -> dict[str, Any] | None:
    raw = (text or "").strip()
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            parsed = json.loads(raw[start : end + 1])
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None


def _truncate_files(files: dict[str, str], *, max_chars_per_file: int = 12000) -> dict[str, str]:
    truncated: dict[str, str] = {}
    for rel_path, content in files.items():
        if rel_path not in ALLOWED_CANDIDATE_FILES:
            continue
        text = str(content or "")
        if len(text) > max_chars_per_file:
            truncated[rel_path] = text[:max_chars_per_file] + "\n<!-- TRUNCATED_FOR_PLANNING -->"
        else:
            truncated[rel_path] = text
    return truncated


def build_candidate_refinement_prompt(
    *,
    requested_change: str,
    files_after: dict[str, str],
) -> str:
    payload = {
        "task": "Plan safe text file updates for a candidate app refinement.",
        "requested_change": requested_change,
        "allowed_files": sorted(ALLOWED_CANDIDATE_FILES),
        "rules": [
            "Return only one JSON object.",
            "Only include file_updates for files that need changes.",
            "Every key in file_updates must be one of allowed_files.",
            "Every value in file_updates must be the complete new text content for that file.",
            "Do not include explanations outside JSON.",
            "Do not request tool execution.",
            "Do not modify backend.py or any file outside allowed_files.",
        ],
        "expected_json_shape": {
            "status": "planned | no_change | failed",
            "reason": "short reason",
            "file_updates": {
                "index.html": "complete updated text if changed",
                "styles.css": "complete updated text if changed",
                "content.json": "complete updated text if changed",
                "schema.json": "complete updated text if changed",
            },
        },
        "current_files": _truncate_files(files_after),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


COLOR_WORDS = {
    "verde": "green",
    "green": "green",
    "azul": "blue",
    "blue": "blue",
    "rojo": "red",
    "red": "red",
    "amarillo": "yellow",
    "yellow": "yellow",
    "negro": "black",
    "black": "black",
    "blanco": "white",
    "white": "white",
    "violeta": "purple",
    "morado": "purple",
    "purple": "purple",
    "naranja": "orange",
    "orange": "orange",
    "gris": "gray",
    "gray": "gray",
    "grey": "gray",
}


def _detect_title_color_change(requested_change: str) -> str | None:
    text = _as_text(requested_change).lower()
    if not text:
        return None
    title_terms = ("titulo", "título", "title", "hero")
    color_terms = ("color", "verde", "green", "azul", "blue", "rojo", "red", "amarillo", "yellow")
    if not any(term in text for term in title_terms):
        return None
    if not any(term in text for term in color_terms):
        return None
    for word, css_color in COLOR_WORDS.items():
        if re.search(rf"\b{re.escape(word)}\b", text):
            return css_color
    return None


def _replace_or_append_title_color(styles: str, css_color: str) -> str:
    selectors = [
        ".hero h1",
        ".hero-title",
        "h1",
    ]

    for selector in selectors:
        pattern = re.compile(rf"({re.escape(selector)}\s*\{{)(.*?)(\}})", re.DOTALL)
        match = pattern.search(styles)
        if not match:
            continue
        body = match.group(2)
        if re.search(r"color\s*:", body):
            new_body = re.sub(r"color\s*:\s*[^;]+;", f"color: {css_color};", body, count=1)
        else:
            suffix = "" if body.endswith("\n") else "\n"
            new_body = f"{body}{suffix}  color: {css_color};\n"
        return styles[:match.start()] + match.group(1) + new_body + match.group(3) + styles[match.end():]

    suffix = "" if styles.endswith("\n") or not styles else "\n"
    return f"{styles}{suffix}.hero h1 {{\n  color: {css_color};\n}}\n"


def plan_candidate_refinement_fast_path(
    *,
    requested_change: str,
    files_after: dict[str, str],
) -> dict[str, Any] | None:
    """Plan deterministic updates for common safe refinement requests.

    Returns None when the request is not recognized, so callers can fall back
    to the model planner.
    """

    css_color = _detect_title_color_change(requested_change)
    if css_color:
        styles = files_after.get("styles.css")
        if isinstance(styles, str):
            updated_styles = _replace_or_append_title_color(styles, css_color)
            if updated_styles != styles:
                return {
                    "ok": True,
                    "status": "planned",
                    "reason": f"Fast path updated title color to {css_color}.",
                    "file_updates": {"styles.css": updated_styles},
                    "planner": "fast_path",
                }
            return {
                "ok": True,
                "status": "no_change",
                "reason": f"Title color already appears to be {css_color}.",
                "file_updates": {},
                "planner": "fast_path",
            }

    return None


def normalize_candidate_refinement_plan(
    model_output: Any,
    *,
    existing_files: dict[str, str],
) -> dict[str, Any]:
    parsed = model_output if isinstance(model_output, dict) else _extract_json_object(str(model_output or ""))
    if not parsed:
        return {
            "ok": False,
            "status": "failed",
            "reason": "Model did not return a valid JSON object.",
            "file_updates": {},
        }

    status = _as_text(parsed.get("status")).lower()
    if status not in {"planned", "no_change", "failed"}:
        return {
            "ok": False,
            "status": "failed",
            "reason": "Model returned an unknown status.",
            "file_updates": {},
        }

    raw_updates = parsed.get("file_updates")
    if raw_updates is None:
        raw_updates = {}
    if not isinstance(raw_updates, dict):
        return {
            "ok": False,
            "status": "failed",
            "reason": "file_updates must be an object.",
            "file_updates": {},
        }

    updates: dict[str, str] = {}
    for rel_path, content in raw_updates.items():
        path = _as_text(rel_path)
        if path not in ALLOWED_CANDIDATE_FILES:
            return {
                "ok": False,
                "status": "failed",
                "reason": f"Model attempted to update a disallowed file: {path}",
                "file_updates": {},
            }
        if path not in existing_files:
            return {
                "ok": False,
                "status": "failed",
                "reason": f"Model attempted to update a file not present in candidate: {path}",
                "file_updates": {},
            }
        if not isinstance(content, str):
            return {
                "ok": False,
                "status": "failed",
                "reason": f"Model returned non-text content for file: {path}",
                "file_updates": {},
            }
        if content != existing_files.get(path):
            updates[path] = content

    normalized_status = "planned" if updates else "no_change"
    return {
        "ok": status in {"planned", "no_change"},
        "status": normalized_status,
        "reason": _as_text(parsed.get("reason")) or ("No changes required." if not updates else "Candidate updates planned."),
        "file_updates": updates,
    }


async def plan_candidate_refinement_file_updates(
    *,
    requested_change: str,
    files_after: dict[str, str],
    model: str = "qwen2.5-coder:14b",
    adapter_factory: Callable[[], OllamaAdapter] | None = None,
) -> dict[str, Any]:
    """Ask a model to propose candidate file updates without side effects."""

    change = _as_text(requested_change)
    if not change:
        return {
            "ok": False,
            "status": "failed",
            "reason": "requested_change is required.",
            "file_updates": {},
        }

    allowed_existing_files = {
        path: content
        for path, content in dict(files_after or {}).items()
        if path in ALLOWED_CANDIDATE_FILES and isinstance(content, str)
    }
    if not allowed_existing_files:
        return {
            "ok": False,
            "status": "failed",
            "reason": "Candidate has no allowed text files to update.",
            "file_updates": {},
        }

    fast_path_plan = plan_candidate_refinement_fast_path(
        requested_change=change,
        files_after=allowed_existing_files,
    )
    if fast_path_plan is not None:
        return fast_path_plan

    adapter = adapter_factory() if adapter_factory else OllamaAdapter(allow_network=True, supports_json_mode=True)
    context = ProviderTurnContext(
        session_id="candidate-refinement-planner",
        agent_id="candidate-refinement-planner",
        model=model,
        system_prompt=(
            "You are OpenSwarm's candidate refinement file planner. "
            "Return only one JSON object. Do not execute tools. "
            "Plan complete replacement text for allowed candidate files only."
        ),
        messages=[
            {
                "role": "user",
                "content": build_candidate_refinement_prompt(
                    requested_change=change,
                    files_after=allowed_existing_files,
                ),
            }
        ],
        tools=[],
    )

    assistant_content = ""
    try:
        async for event in adapter.run_turn(context):
            if event.type == "message_final":
                message = event.payload.get("message") if isinstance(event.payload, dict) else {}
                assistant_content = _as_text((message or {}).get("content"))
            elif event.type == "error":
                return {
                    "ok": False,
                    "status": "failed",
                    "reason": _as_text(event.payload.get("error")) or "Model planner failed.",
                    "file_updates": {},
                }
    except Exception as exc:
        return {
            "ok": False,
            "status": "failed",
            "reason": f"Model planner failed: {exc}",
            "file_updates": {},
        }

    return normalize_candidate_refinement_plan(
        assistant_content,
        existing_files=allowed_existing_files,
    )
