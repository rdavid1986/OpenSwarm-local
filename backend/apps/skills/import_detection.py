"""Read-only source format detection for prepared external skill inputs."""

from __future__ import annotations

from typing import Any

SAFE_FALSE_FLAGS = {
    "can_create_candidate": False,
    "can_execute_source": False,
    "can_activate_tools": False,
    "can_activate_mcp": False,
}


def _norm(value: Any) -> str:
    return str(value or "").strip().lower().replace("\\", "/")


def _collect(input_data: dict[str, Any]) -> tuple[list[dict[str, Any]], str, str, str]:
    files = input_data.get("files") if isinstance(input_data, dict) else []
    file_list = files if isinstance(files, list) else []
    raw_text = str(input_data.get("raw_text") or "") if isinstance(input_data, dict) else ""
    source_hint = _norm(input_data.get("source_hint")) if isinstance(input_data, dict) else ""
    source_url = _norm(input_data.get("source_url")) if isinstance(input_data, dict) else ""
    chunks = [raw_text, source_hint, source_url]
    for file in file_list:
        if isinstance(file, dict):
            chunks.extend([str(file.get("path") or ""), str(file.get("name") or ""), str(file.get("content") or "")])
    return file_list, _norm("\n".join(chunks)), source_hint, source_url


def _has_file(files: list[dict[str, Any]], predicate) -> bool:
    for file in files:
        if not isinstance(file, dict):
            continue
        path = _norm(file.get("path") or file.get("name"))
        content = _norm(file.get("content"))
        if predicate(path, content):
            return True
    return False


def _result(fmt: str, confidence: float, matched: list[str], missing: list[str] | None = None, warnings: list[str] | None = None) -> dict[str, Any]:
    return {
        "detected_format": fmt,
        "confidence": max(0.0, min(1.0, confidence)),
        "matched_signals": matched,
        "missing_signals": missing or [],
        "warnings": warnings or [],
        "safe_to_continue_preview": True,
        **SAFE_FALSE_FLAGS,
    }


def detect_skill_import_source_format(input: dict[str, Any]) -> dict[str, Any]:
    """Detect source format from caller-provided filenames, snippets, and metadata only."""

    files, text, source_hint, source_url = _collect(input or {})

    if source_hint in {"repo", "zip", "folder"}:
        return _result(source_hint, 0.85, [f"source_hint:{source_hint}"])
    if source_url.endswith(".zip"):
        return _result("zip", 0.75, ["source_url:.zip"])

    if _has_file(files, lambda p, c: "manifest" in p and "skill_pack" in c):
        return _result("skill_pack", 0.9, ["manifest:skill_pack"])
    if "\"spec_version\"" in text and "openswarm.skill.v1" in text:
        return _result("openswarm_skillspec", 0.95, ["spec_version:openswarm.skill.v1"])
    if _has_file(files, lambda p, c: p.endswith("skill.md") and (c.startswith("---") or "name:" in c[:500])):
        platform = "anthropic_skill" if "anthropic" in text else "claude_skill"
        return _result(platform, 0.88, ["SKILL.md", "frontmatter"])
    if ".cursor/rules" in text or "cursor rule" in text:
        return _result("cursor_rule", 0.9, ["cursor rule signal"])
    if ".windsurf/rules" in text or "windsurf" in text:
        return _result("windsurf_rule", 0.9, ["windsurf rule signal"])
    if "copilot-instructions.md" in text or "github copilot" in text:
        return _result("copilot_instruction", 0.9, ["copilot instructions signal"])
    if "agents.md" in text or "codex" in text or "agent instructions" in text:
        return _result("codex_instruction", 0.82, ["codex/AGENTS signal"])
    if "gemini" in text and ("cli" in text or "config" in text):
        return _result("gemini_cli_config", 0.78, ["gemini config signal"])
    if "qwen" in text and ("code" in text or "config" in text):
        return _result("qwen_code_config", 0.78, ["qwen config signal"])
    if "kiro" in text and ("spec" in text or ".kiro" in text):
        return _result("kiro_spec", 0.78, ["kiro spec signal"])
    if "mcp" in text and any(token in text for token in ("tool", "server", "model context protocol")):
        return _result("mcp_tool_instruction", 0.82, ["mcp tool instruction signal"])
    if "prompt" in text or _has_file(files, lambda p, c: p.endswith("readme.md") and "prompt" in c):
        return _result("markdown_prompt_pack", 0.62, ["markdown/prompt signal"], warnings=["ambiguous markdown prompt material"])

    return _result("unknown", 0.0, [], ["recognized source signals"], ["Unknown format; preview only"])
