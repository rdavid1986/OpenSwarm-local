import os
import json
import logging
import re
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import HTTPException
from backend.config.Apps import SubApp
from backend.apps.skills.candidate_store import SkillCandidateStore
from backend.apps.skills.candidate_approval import apply_skill_candidate_install_approval
from backend.apps.skills.candidate_gate import apply_skill_candidate_gate
from backend.apps.skills.candidate_install import install_approved_skill_candidate
from backend.apps.skills.candidate_validation import apply_skill_candidate_validation
from backend.apps.skills.models import Skill, SkillCandidateApprovalRequest, SkillCandidateImprovementApplyRequest, SkillCandidateResearchApprovalRequest, SkillCreate, SkillImportCandidateCreateRequest, SkillImportPreviewRequest, SkillSpecCandidate, SkillUpdate, SkillWorkspaceSeedRequest
from backend.apps.skills.requirements_contract import build_skill_candidate_requirements_contract
from backend.apps.skills.research_contract import build_skill_candidate_research_contract
from backend.apps.skills.research_execution import execute_skill_candidate_research
from backend.apps.skills.skill_reviewer import review_skill_candidate
from backend.apps.skills.skill_improvement_proposal import build_skill_candidate_improvement_proposal, apply_skill_candidate_improvement_proposal
from backend.apps.skills.import_candidate import build_skill_candidate_from_import_preview
from backend.apps.skills.import_policy import evaluate_skill_import_policy
from backend.apps.skills.import_preview import build_skill_import_preview_report
from backend.apps.skills.import_detection import detect_skill_import_source_format
from backend.apps.skills.import_ingestion_guard import build_prepared_skill_import_ingestion_guard, sanitize_prepared_skill_import_files
from backend.apps.skills.skill_harness import (
    build_skill_dry_run_report,
    build_skill_evidence_quality_report,
    build_skill_harness_full_report,
    build_skill_promotion_gate,
    build_skill_regression_suite,
    build_skill_runtime_validation_report,
    build_skill_test_case_contract,
)
from backend.apps.tools_lib.models import BUILTIN_TOOLS

logger = logging.getLogger(__name__)

SKILLS_DIR = os.path.expanduser("~/.claude/skills")
INDEX_PATH = os.path.join(SKILLS_DIR, ".skills_index.json")

from backend.config.paths import SKILLS_WORKSPACE_DIR


@asynccontextmanager
async def skills_lifespan():
    os.makedirs(SKILLS_DIR, exist_ok=True)
    os.makedirs(SKILLS_WORKSPACE_DIR, exist_ok=True)
    yield


skills = SubApp("skills", skills_lifespan)
skill_candidate_store = SkillCandidateStore()


def _load_index() -> dict[str, dict]:
    if os.path.exists(INDEX_PATH):
        with open(INDEX_PATH) as f:
            return json.load(f)
    return {}


def _save_index(index: dict[str, dict]):
    with open(INDEX_PATH, "w") as f:
        json.dump(index, f, indent=2)


def _sync_skills() -> list[Skill]:
    """Sync skills from the filesystem, updating the index."""
    index = _load_index()
    result = []

    if os.path.exists(SKILLS_DIR):
        for fname in os.listdir(SKILLS_DIR):
            if fname.endswith(".md"):
                fpath = os.path.join(SKILLS_DIR, fname)
                with open(fpath) as f:
                    content = f.read()

                skill_id = fname.replace(".md", "")
                meta = index.get(skill_id, {})
                skill = Skill(
                    id=skill_id,
                    name=meta.get("name", fname.replace(".md", "").replace("-", " ").replace("_", " ").title()),
                    description=meta.get("description", ""),
                    content=content,
                    file_path=fpath,
                    command=meta.get("command", fname.replace(".md", "")),
                )
                result.append(skill)

    return result


@skills.router.get("/list")
async def list_skills():
    return {"skills": [s.model_dump() for s in _sync_skills()]}


def _parse_skill_frontmatter(raw: str) -> dict:
    """Extract YAML frontmatter fields from a SKILL.md file."""
    if not raw.startswith("---"):
        return {}
    end = raw.find("---", 3)
    if end == -1:
        return {}
    fm_block = raw[3:end].strip()
    meta: dict = {}
    for line in fm_block.splitlines():
        m = re.match(r"^(\w[\w_-]*)\s*:\s*(.+)$", line)
        if m:
            meta[m.group(1).strip()] = m.group(2).strip().strip('"').strip("'")
    return meta


@skills.router.post("/workspace/seed")
async def seed_skill_workspace(body: SkillWorkspaceSeedRequest):
    folder = os.path.join(SKILLS_WORKSPACE_DIR, body.workspace_id)
    os.makedirs(folder, exist_ok=True)

    if body.skill_content:
        with open(os.path.join(folder, "SKILL.md"), "w") as f:
            f.write(body.skill_content)
    if body.meta:
        with open(os.path.join(folder, "meta.json"), "w") as f:
            json.dump(body.meta, f, indent=2)

    return {"path": os.path.abspath(folder)}


@skills.router.get("/workspace/{workspace_id}")
async def read_skill_workspace(workspace_id: str):
    folder = os.path.join(SKILLS_WORKSPACE_DIR, workspace_id)
    if not os.path.isdir(folder):
        raise HTTPException(status_code=404, detail="Workspace not found")

    skill_content = None
    skill_path = os.path.join(folder, "SKILL.md")
    if os.path.isfile(skill_path):
        with open(skill_path) as f:
            skill_content = f.read()

    meta = None
    meta_path = os.path.join(folder, "meta.json")
    if os.path.isfile(meta_path):
        try:
            with open(meta_path) as f:
                meta = json.load(f)
        except json.JSONDecodeError:
            pass

    frontmatter = _parse_skill_frontmatter(skill_content) if skill_content else {}

    return {
        "skill_content": skill_content,
        "meta": meta,
        "frontmatter": frontmatter,
    }




def _build_skill_import_preview_payload(body: SkillImportPreviewRequest) -> dict:
    payload = body.model_dump(mode="json", exclude_none=True)
    prepared_ingestion_guard = build_prepared_skill_import_ingestion_guard(payload)
    payload["prepared_ingestion_guard"] = prepared_ingestion_guard
    if isinstance(payload.get("files"), list):
        payload["files"] = sanitize_prepared_skill_import_files(payload)
    detection = detect_skill_import_source_format(payload)
    if not payload.get("source_format") or payload.get("source_format") == "unknown":
        payload["source_format"] = detection.get("detected_format", "unknown")
    payload["detection"] = detection
    preview = build_skill_import_preview_report(payload)
    policy = evaluate_skill_import_policy(preview)
    return {
        "ok": True,
        "detection": detection,
        "preview": preview,
        "policy": policy,
        "prepared_ingestion_guard": prepared_ingestion_guard,
        "can_create_candidate": bool(policy.get("can_create_candidate")),
        "can_install_skill": False,
        "can_execute_source": False,
        "can_activate_tools": False,
        "can_activate_mcp": False,
    }


@skills.router.post("/import/preview")
async def preview_skill_import(body: SkillImportPreviewRequest):
    return _build_skill_import_preview_payload(body)


@skills.router.post("/import/candidates/create")
async def create_skill_candidate_from_import(body: SkillImportCandidateCreateRequest):
    preview_payload = _build_skill_import_preview_payload(body)
    preview = preview_payload["preview"]
    policy = preview_payload["policy"]
    try:
        candidate = build_skill_candidate_from_import_preview(preview, policy)
    except ValueError as exc:
        if str(exc) == "skill_import_policy_blocks_candidate_creation":
            raise HTTPException(status_code=409, detail="Skill import policy blocks candidate creation")
        raise HTTPException(status_code=400, detail=str(exc))

    validated_candidate = apply_skill_candidate_validation(candidate)
    gated_candidate = apply_skill_candidate_gate(validated_candidate)
    saved = skill_candidate_store.save(gated_candidate)
    return {
        "ok": True,
        "candidate": saved.model_dump(mode="json"),
        "preview": preview,
        "policy": policy,
        "can_install_skill": False,
        "can_execute_source": False,
        "can_activate_tools": False,
        "can_activate_mcp": False,
    }



@skills.router.get("/candidates/list")
async def list_skill_candidates():
    return {"candidates": [candidate.model_dump(mode="json") for candidate in skill_candidate_store.list()]}


@skills.router.post("/candidates/create")
async def create_skill_candidate(body: SkillSpecCandidate):
    validated_candidate = apply_skill_candidate_validation(body)
    gated_candidate = apply_skill_candidate_gate(validated_candidate)
    candidate = skill_candidate_store.save(gated_candidate)
    return {"ok": True, "candidate": candidate.model_dump(mode="json")}




@skills.router.post("/candidates/{candidate_id}/approval")
async def approve_skill_candidate(candidate_id: str, body: SkillCandidateApprovalRequest):
    try:
        candidate = skill_candidate_store.load(candidate_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Skill candidate not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    approved_candidate = apply_skill_candidate_install_approval(candidate, approved=body.approved)
    saved = skill_candidate_store.save(approved_candidate)
    return {"ok": saved.install_approved, "candidate": saved.model_dump(mode="json")}




@skills.router.post("/candidates/{candidate_id}/install")
async def install_skill_candidate(candidate_id: str):
    try:
        candidate = skill_candidate_store.load(candidate_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Skill candidate not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        skill, installed_candidate, next_index, audit = install_approved_skill_candidate(
            candidate,
            skills_dir=SKILLS_DIR,
            index=_load_index(),
        )
    except ValueError as exc:
        if str(exc) == "skill_candidate_not_approved_for_install":
            raise HTTPException(status_code=409, detail="Skill candidate is not approved for install")
        raise

    _save_index(next_index)
    saved_candidate = skill_candidate_store.save(installed_candidate)
    return {
        "ok": True,
        "skill": skill.model_dump(),
        "candidate": saved_candidate.model_dump(mode="json"),
        "audit": audit,
    }




@skills.router.post("/candidates/{candidate_id}/reject")
async def reject_skill_candidate(candidate_id: str):
    try:
        candidate = skill_candidate_store.load(candidate_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Skill candidate not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    rejected = candidate.model_copy(update={"status": "rejected", "install_approved": False})
    saved = skill_candidate_store.save(rejected)
    return {"ok": True, "candidate": saved.model_dump(mode="json")}


@skills.router.delete("/candidates/{candidate_id}")
async def delete_skill_candidate(candidate_id: str):
    try:
        skill_candidate_store.delete(candidate_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Skill candidate not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True}


@skills.router.get("/candidates/{candidate_id}/requirements-contract")
async def get_skill_candidate_requirements_contract(candidate_id: str):
    try:
        candidate = skill_candidate_store.load(candidate_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Skill candidate not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    contract_warnings: list[str] = []

    try:
        from backend.apps.tools_lib import tools_lib as tools_module
        tools_snapshot = tools_module._load_all()
        builtin_permissions = tools_module.load_builtin_permissions()
    except Exception as exc:
        tools_snapshot = []
        builtin_permissions = {}
        contract_warnings.append(f"Tools snapshot unavailable; tool availability marked conservatively: {type(exc).__name__}")

    try:
        from backend.apps.modes import modes as modes_module
        persisted_modes = modes_module._load_all()
        by_id = {mode.id: mode for mode in persisted_modes}
        for builtin_mode in modes_module.BUILTIN_MODES:
            by_id.setdefault(builtin_mode.id, builtin_mode)
        modes_snapshot = list(by_id.values())
    except Exception as exc:
        modes_snapshot = []
        contract_warnings.append(f"Modes snapshot unavailable; mode mapping marked unknown: {type(exc).__name__}")

    return build_skill_candidate_requirements_contract(
        candidate,
        tools=tools_snapshot,
        builtin_tools=BUILTIN_TOOLS,
        builtin_permissions=builtin_permissions,
        modes=modes_snapshot,
        warnings=contract_warnings,
    )


def _load_skill_candidate_or_404(candidate_id: str) -> SkillSpecCandidate:
    try:
        return skill_candidate_store.load(candidate_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Skill candidate not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@skills.router.get("/candidates/{candidate_id}/harness/test-contract")
async def get_skill_candidate_harness_test_contract(candidate_id: str):
    candidate = _load_skill_candidate_or_404(candidate_id)
    return build_skill_test_case_contract(candidate.model_dump(mode="json"))


@skills.router.get("/candidates/{candidate_id}/harness/dry-run")
async def get_skill_candidate_harness_dry_run(candidate_id: str):
    candidate = _load_skill_candidate_or_404(candidate_id)
    payload = candidate.model_dump(mode="json")
    test_contract = build_skill_test_case_contract(payload)
    return build_skill_dry_run_report(payload, test_contract)


@skills.router.get("/candidates/{candidate_id}/harness/runtime-validation")
async def get_skill_candidate_harness_runtime_validation(candidate_id: str):
    candidate = _load_skill_candidate_or_404(candidate_id)
    payload = candidate.model_dump(mode="json")
    test_contract = build_skill_test_case_contract(payload)
    dry_run = build_skill_dry_run_report(payload, test_contract)
    return build_skill_runtime_validation_report(payload, dry_run)


@skills.router.get("/candidates/{candidate_id}/harness/regression-suite")
async def get_skill_candidate_harness_regression_suite(candidate_id: str):
    candidate = _load_skill_candidate_or_404(candidate_id)
    payload = candidate.model_dump(mode="json")
    validation = build_skill_runtime_validation_report(payload)
    return build_skill_regression_suite(payload, validation)


@skills.router.get("/candidates/{candidate_id}/harness/evidence-quality")
async def get_skill_candidate_harness_evidence_quality(candidate_id: str):
    candidate = _load_skill_candidate_or_404(candidate_id)
    payload = candidate.model_dump(mode="json")
    validation = build_skill_runtime_validation_report(payload)
    return build_skill_evidence_quality_report(payload, validation, evidence_refs=payload.get("evidence_refs"))


@skills.router.get("/candidates/{candidate_id}/harness/promotion-gate")
async def get_skill_candidate_harness_promotion_gate(candidate_id: str):
    candidate = _load_skill_candidate_or_404(candidate_id)
    payload = candidate.model_dump(mode="json")
    validation = build_skill_runtime_validation_report(payload)
    regression = build_skill_regression_suite(payload, validation)
    evidence = build_skill_evidence_quality_report(payload, validation, evidence_refs=payload.get("evidence_refs"))
    return build_skill_promotion_gate(payload, validation, evidence, regression)


@skills.router.get("/candidates/{candidate_id}/harness/full")
async def get_skill_candidate_harness_full(candidate_id: str):
    candidate = _load_skill_candidate_or_404(candidate_id)
    return build_skill_harness_full_report(candidate.model_dump(mode="json"))


@skills.router.get("/candidates/{candidate_id}/quality-review")
async def get_skill_candidate_quality_review(candidate_id: str):
    try:
        candidate = skill_candidate_store.load(candidate_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Skill candidate not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return review_skill_candidate(candidate)




@skills.router.post("/candidates/{candidate_id}/research-approval")
async def approve_skill_candidate_research(candidate_id: str, body: SkillCandidateResearchApprovalRequest):
    try:
        candidate = skill_candidate_store.load(candidate_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Skill candidate not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    updated = candidate.model_copy(update={"research_approved": body.approved})
    saved = skill_candidate_store.save(updated)
    research_contract = build_skill_candidate_research_contract(saved)
    return {
        "ok": True,
        "candidate": saved.model_dump(mode="json"),
        "research_contract": research_contract,
        "audit": {
            "event": "skill_candidate_research_permission_updated",
            "candidate_id": saved.candidate_id,
            "research_approved": saved.research_approved,
            "install_approved": saved.install_approved,
            "status": saved.status,
            "web_research_executed": False,
        },
    }


@skills.router.get("/candidates/{candidate_id}/research-contract")
async def get_skill_candidate_research_contract(candidate_id: str):
    try:
        candidate = skill_candidate_store.load(candidate_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Skill candidate not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return build_skill_candidate_research_contract(candidate)


@skills.router.post("/candidates/{candidate_id}/research-execute")
async def execute_skill_candidate_research_route(candidate_id: str):
    try:
        candidate = skill_candidate_store.load(candidate_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Skill candidate not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        updated_candidate, result = await execute_skill_candidate_research(candidate)
    except ValueError as exc:
        if str(exc) == "skill_research_requires_explicit_approval":
            raise HTTPException(status_code=409, detail="Skill research requires explicit approval")
        if str(exc) == "skill_research_not_required":
            raise HTTPException(status_code=409, detail="Skill research is not required for this candidate")
        if str(exc) == "skill_research_has_no_queries":
            raise HTTPException(status_code=409, detail="Skill research has no queries to execute")
        raise

    saved = skill_candidate_store.save(updated_candidate)
    return {
        "ok": True,
        "candidate": saved.model_dump(mode="json"),
        "research_contract": result["contract"],
        "evidence": result["evidence"],
        "audit": result["audit"],
    }


@skills.router.get("/candidates/{candidate_id}/improvement-proposal")
async def get_skill_candidate_improvement_proposal(candidate_id: str):
    try:
        candidate = skill_candidate_store.load(candidate_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Skill candidate not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return build_skill_candidate_improvement_proposal(candidate)


@skills.router.post("/candidates/{candidate_id}/improvement-proposal/apply")
async def apply_skill_candidate_improvement_proposal_route(
    candidate_id: str,
    body: SkillCandidateImprovementApplyRequest,
):
    try:
        candidate = skill_candidate_store.load(candidate_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Skill candidate not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        updated_candidate, proposal = apply_skill_candidate_improvement_proposal(
            candidate,
            approved=body.approved,
        )
    except ValueError as exc:
        if str(exc) == "skill_improvement_proposal_requires_explicit_approval":
            raise HTTPException(status_code=409, detail="Skill improvement proposal requires explicit approval")
        if str(exc) == "skill_improvement_proposal_has_no_diff":
            raise HTTPException(status_code=409, detail="Skill improvement proposal has no diff to apply")
        raise

    validated_candidate = apply_skill_candidate_validation(updated_candidate)
    gated_candidate = apply_skill_candidate_gate(validated_candidate)
    saved = skill_candidate_store.save(gated_candidate)
    return {
        "ok": True,
        "candidate": saved.model_dump(mode="json"),
        "proposal": proposal,
        "audit": {
            "event": "skill_candidate_improvement_proposal_applied",
            "candidate_id": saved.candidate_id,
            "install_approved": saved.install_approved,
            "status": saved.status,
        },
    }


@skills.router.get("/candidates/{candidate_id}")
async def get_skill_candidate(candidate_id: str):
    try:
        candidate = skill_candidate_store.load(candidate_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Skill candidate not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return candidate.model_dump(mode="json")


@skills.router.get("/{skill_id}")
async def get_skill(skill_id: str):
    for s in _sync_skills():
        if s.id == skill_id:
            return s.model_dump()
    raise HTTPException(status_code=404, detail="Skill not found")


@skills.router.post("/create")
async def create_skill(body: SkillCreate):
    slug = body.name.lower().replace(" ", "-")
    fpath = os.path.join(SKILLS_DIR, f"{slug}.md")

    with open(fpath, "w") as f:
        f.write(body.content)

    index = _load_index()
    index[slug] = {
        "name": body.name,
        "description": body.description,
        "command": body.command or slug,
    }
    _save_index(index)

    skill = Skill(
        id=slug,
        name=body.name,
        description=body.description,
        content=body.content,
        file_path=fpath,
        command=body.command or slug,
    )
    pass
    return {"ok": True, "skill": skill.model_dump()}


@skills.router.put("/{skill_id}")
async def update_skill(skill_id: str, body: SkillUpdate):
    fpath = os.path.join(SKILLS_DIR, f"{skill_id}.md")
    if not os.path.exists(fpath):
        raise HTTPException(status_code=404, detail="Skill not found")

    if body.content is not None:
        with open(fpath, "w") as f:
            f.write(body.content)

    index = _load_index()
    meta = index.get(skill_id, {})
    if body.name is not None:
        meta["name"] = body.name
    if body.description is not None:
        meta["description"] = body.description
    if body.command is not None:
        meta["command"] = body.command
    index[skill_id] = meta
    _save_index(index)

    with open(fpath) as f:
        content = f.read()

    skill = Skill(
        id=skill_id,
        name=meta.get("name", skill_id),
        description=meta.get("description", ""),
        content=content,
        file_path=fpath,
        command=meta.get("command", skill_id),
    )
    return {"ok": True, "skill": skill.model_dump()}


@skills.router.delete("/{skill_id}")
async def delete_skill(skill_id: str):
    fpath = os.path.join(SKILLS_DIR, f"{skill_id}.md")
    if os.path.exists(fpath):
        os.remove(fpath)
    index = _load_index()
    index.pop(skill_id, None)
    _save_index(index)
    return {"ok": True}
