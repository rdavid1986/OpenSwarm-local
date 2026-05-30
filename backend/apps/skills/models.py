from pydantic import BaseModel, Field
from typing import Any, Literal, Optional
from uuid import uuid4


class Skill(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    name: str
    description: str = ""
    content: str
    file_path: str = ""
    command: str = ""


class SkillCreate(BaseModel):
    name: str
    description: str = ""
    content: str
    command: str = ""


class SkillUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None
    command: Optional[str] = None


class SkillWorkspaceSeedRequest(BaseModel):
    workspace_id: str
    skill_content: Optional[str] = None
    meta: Optional[dict[str, Any]] = None


SkillMetadataConfidence = Literal["unknown", "inferred", "measured", "unmeasured"]
SkillCandidateStatus = Literal[
    "draft",
    "candidate",
    "needs_validation",
    "validated",
    "rejected",
    "approved_for_install",
    "installed",
]


class SkillSpec(BaseModel):
    """Portable OpenSwarm skill contract.

    This is a side-effect free contract. It does not install a skill, write files,
    approve permissions, or imply validation evidence.
    """

    spec_version: str = "openswarm.skill.v1"
    name: str
    description: str = ""
    command: str = ""
    content: str = ""
    source_format: str = "unknown"
    provenance: dict[str, Any] = Field(default_factory=dict)
    metadata_confidence: SkillMetadataConfidence = "unknown"
    tags: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    required_tools: list[str] = Field(default_factory=list)
    required_mcp_servers: list[str] = Field(default_factory=list)
    compatible_providers: list[str] = Field(default_factory=list)
    tested_models: list[str] = Field(default_factory=list)
    recommended_models: list[str] = Field(default_factory=list)
    unsupported_models: list[str] = Field(default_factory=list)
    validation_plan: dict[str, Any] = Field(default_factory=dict)
    evidence_contract: dict[str, Any] = Field(default_factory=dict)
    compatibility: dict[str, Any] = Field(default_factory=dict)
    risks: list[str] = Field(default_factory=list)


class SkillSpecCandidate(BaseModel):
    """Reviewable candidate wrapper for SkillSpec.

    External, generated, or migrated skills must become candidates before any
    install/publish flow. Candidate creation is not approval.
    """

    candidate_id: str = Field(default_factory=lambda: uuid4().hex)
    skill_spec: SkillSpec
    status: SkillCandidateStatus = "candidate"
    source: str = "unknown"
    source_ref: str = ""
    validation_errors: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    policy_refs: list[str] = Field(default_factory=list)
    install_approved: bool = False
    research_approved: bool = False
    research_evidence: list[dict[str, Any]] = Field(default_factory=list)


class SkillCandidateApprovalRequest(BaseModel):
    approved: bool


class SkillCandidateResearchApprovalRequest(BaseModel):
    approved: bool = False


class SkillCandidateImprovementApplyRequest(BaseModel):
    approved: bool = False
