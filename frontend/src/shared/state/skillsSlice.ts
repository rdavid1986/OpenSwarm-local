import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import { API_BASE } from '@/shared/config';

const SKILLS_API = `${API_BASE}/skills`;

export interface Skill {
  id: string;
  name: string;
  description: string;
  content: string;
  file_path: string;
  command: string;
}

export type SkillMetadataConfidence = 'unknown' | 'inferred' | 'measured' | 'unmeasured';

export type SkillCandidateStatus =
  | 'draft'
  | 'candidate'
  | 'needs_validation'
  | 'validated'
  | 'rejected'
  | 'approved_for_install'
  | 'installed';

export interface SkillSpec {
  spec_version: string;
  name: string;
  description: string;
  command: string;
  content: string;
  source_format: string;
  provenance: Record<string, any>;
  metadata_confidence: SkillMetadataConfidence;
  tags: string[];
  categories: string[];
  required_tools: string[];
  required_mcp_servers: string[];
  compatible_providers: string[];
  tested_models: string[];
  recommended_models: string[];
  unsupported_models: string[];
  validation_plan: Record<string, any>;
  evidence_contract: Record<string, any>;
  compatibility: Record<string, any>;
  risks: string[];
}

export interface SkillSpecCandidate {
  candidate_id: string;
  skill_spec: SkillSpec;
  status: SkillCandidateStatus;
  source: string;
  source_ref: string;
  validation_errors: Record<string, any>[];
  warnings: Record<string, any>[];
  evidence_refs: string[];
  policy_refs: string[];
  install_approved: boolean;
  research_approved?: boolean;
}

export interface SkillCandidateRequirementsContract {
  contract_kind: 'skill_candidate_requirements_contract';
  candidate_id: string;
  candidate_status: string;
  install_approved: boolean;
  requirements: {
    required_tools?: string[];
    required_mcp_servers?: string[];
    compatible_providers?: string[];
    tested_models?: string[];
    recommended_models?: string[];
    unsupported_models?: string[];
  };
  tools: Array<{
    name: string;
    declared: boolean;
    known: boolean | 'unknown';
    permission: 'always_allow' | 'ask' | 'deny' | 'unknown' | 'not_found' | string;
    source: 'builtin' | 'custom' | 'mcp' | 'unknown' | string;
    notes: string[];
  }>;
  mcp_servers: Array<{
    name: string;
    declared: boolean;
    known: boolean | 'unknown';
    activation_state: 'active' | 'blocked' | 'inactive' | 'unknown' | 'not_found' | string;
    notes: string[];
  }>;
  modes: Array<{
    mode_id: string;
    name: string;
    mentions_required_tools: boolean | 'unknown';
    allowed_tools_policy: 'all_actions' | 'specific_actions' | 'unknown' | string;
    notes: string[];
  }>;
  summary: Record<string, number>;
  warnings: string[];
}

export interface SkillCandidateQualityReviewItem {
  code?: string;
  severity?: 'low' | 'medium' | 'high' | string;
  title?: string;
  message?: string;
  suggested_section?: string;
  reason?: string;
  auto_apply_supported?: boolean;
}

export interface SkillCandidateQualityReview {
  review_kind?: 'skill_quality_review' | string;
  candidate_id: string;
  skill_name?: string;
  status?: string;
  candidate_status?: string;
  install_approved?: boolean;
  quality_contract?: {
    contract_kind?: string;
    skill_name?: string;
    has_role_definition?: boolean;
    has_expert_methodology?: boolean;
    has_decision_criteria?: boolean;
    has_validation_guidance?: boolean;
    has_pitfalls?: boolean;
    has_operational_boundaries?: boolean;
    has_action_boundary_statement?: boolean;
    warnings?: Array<Record<string, any>>;
    [key: string]: any;
  } | null;
  improvement_summary?: string;
  human_summary?: string;
  human_status_label?: string;
  human_next_steps?: string[];
  human_strengths?: string[];
  human_missing_items?: string[];
  technical_details_label?: string;
  improvement_items?: SkillCandidateQualityReviewItem[];
  recommended_sections?: string[];
  missing_sections?: string[];
  action_boundary_status?: string;
  risk_notes?: string[];
  research_recommendation?: {
    status?: string;
    message?: string;
    [key: string]: any;
  } | null;
  safe_to_auto_apply?: boolean;
}


export interface SkillCandidateResearchContract {
  contract_kind?: 'skill_candidate_research_contract' | string;
  candidate_id: string;
  skill_name?: string;
  requires_web_research?: boolean;
  research_allowed?: boolean;
  web_research_executed?: boolean;
  can_mutate_candidate?: boolean;
  can_install_skill?: boolean;
  can_activate_tools?: boolean;
  can_activate_mcp?: boolean;
  research_queries?: string[];
  expected_source_types?: string[];
  research_gap_items?: string[];
  summary?: string;
  next_step?: string;
  guardrails?: string[];
}

export interface SkillCandidateImprovementProposalItem {
  source?: string;
  code?: string;
  severity?: 'low' | 'medium' | 'high' | string;
  title?: string;
  target_section?: string;
  rationale?: string;
  proposed_change?: string;
  auto_apply_supported?: boolean;
}

export interface SkillCandidateImprovementProposal {
  proposal_kind?: 'skill_improvement_proposal' | string;
  candidate_id: string;
  skill_name?: string;
  review_kind?: string;
  status?: string;
  summary?: string;
  proposal_items?: SkillCandidateImprovementProposalItem[];
  item_count?: number;
  requires_user_approval?: boolean;
  requires_web_research?: boolean;
  safe_to_auto_apply?: boolean;
  can_generate_diff?: boolean;
  can_update_candidate?: boolean;
  proposed_content?: string;
  preview_diff?: string;
  next_step?: string;
  guardrails?: string[];
}

export type SkillCandidateCreateBody = Partial<Omit<SkillSpecCandidate, 'skill_spec'>> & {
  skill_spec: Partial<SkillSpec> & Pick<SkillSpec, 'name'>;
};


export interface SkillImportPreviewRequest {
  source_format?: string;
  source_platform?: string;
  source_version?: string;
  source_url?: string;
  source_author?: string;
  source_license?: string;
  source_hint?: string;
  name?: string;
  description?: string;
  content?: string;
  raw_text?: string;
  files?: Array<Record<string, any>>;
  required_tools?: string[];
  required_mcp_servers?: string[];
  provenance?: Record<string, any>;
  existing_skill_spec?: Record<string, any> | null;
}

export interface SkillImportPreviewResult {
  ok: boolean;
  detection: Record<string, any>;
  preview: Record<string, any>;
  policy: Record<string, any>;
  can_create_candidate: boolean;
  can_install_skill: boolean;
  can_execute_source: boolean;
  can_activate_tools: boolean;
  can_activate_mcp: boolean;
}

interface SkillsState {
  items: Record<string, Skill>;
  loading: boolean;
  loaded: boolean;
  candidates: Record<string, SkillSpecCandidate>;
  candidatesLoading: boolean;
  candidatesLoaded: boolean;
  candidateRequirementsContracts: Record<string, SkillCandidateRequirementsContract>;
  candidateRequirementsContractsLoading: Record<string, boolean>;
  candidateRequirementsContractsError: Record<string, string | null>;
  candidateQualityReviews: Record<string, SkillCandidateQualityReview>;
  candidateQualityReviewsLoading: Record<string, boolean>;
  candidateQualityReviewsError: Record<string, string | null>;
  candidateResearchContracts: Record<string, SkillCandidateResearchContract>;
  candidateResearchContractsLoading: Record<string, boolean>;
  candidateResearchContractsError: Record<string, string | null>;
  candidateResearchApprovalLoading: Record<string, boolean>;
  candidateResearchApprovalError: Record<string, string | null>;
  candidateResearchExecutionLoading: Record<string, boolean>;
  candidateResearchExecutionError: Record<string, string | null>;
  candidateImprovementProposals: Record<string, SkillCandidateImprovementProposal>;
  candidateImprovementProposalsLoading: Record<string, boolean>;
  candidateImprovementProposalsError: Record<string, string | null>;
  candidateImprovementApplyLoading: Record<string, boolean>;
  candidateImprovementApplyError: Record<string, string | null>;
  skillImportPreview: SkillImportPreviewResult | null;
  skillImportPreviewLoading: boolean;
  skillImportPreviewError: string | null;
  skillImportCandidateCreateLoading: boolean;
  skillImportCandidateCreateError: string | null;
}

const initialState: SkillsState = {
  items: {},
  loading: false,
  loaded: false,
  candidates: {},
  candidatesLoading: false,
  candidatesLoaded: false,
  candidateRequirementsContracts: {},
  candidateRequirementsContractsLoading: {},
  candidateRequirementsContractsError: {},
  candidateQualityReviews: {},
  candidateQualityReviewsLoading: {},
  candidateQualityReviewsError: {},
  candidateResearchContracts: {},
  candidateResearchContractsLoading: {},
  candidateResearchContractsError: {},
  candidateResearchApprovalLoading: {},
  candidateResearchApprovalError: {},
  candidateResearchExecutionLoading: {},
  candidateResearchExecutionError: {},
  candidateImprovementProposals: {},
  candidateImprovementProposalsLoading: {},
  candidateImprovementProposalsError: {},
  candidateImprovementApplyLoading: {},
  candidateImprovementApplyError: {},
  skillImportPreview: null,
  skillImportPreviewLoading: false,
  skillImportPreviewError: null,
  skillImportCandidateCreateLoading: false,
  skillImportCandidateCreateError: null,
};

export const fetchSkills = createAsyncThunk(
  'skills/fetch',
  async () => {
    const res = await fetch(`${SKILLS_API}/list`);
    const data = await res.json();
    return data.skills as Skill[];
  },
  { condition: (_, { getState }) => !(getState() as { skills: SkillsState }).skills.loading },
);

export const createSkill = createAsyncThunk(
  'skills/create',
  async (body: { name: string; description?: string; content: string; command?: string }) => {
    const res = await fetch(`${SKILLS_API}/create`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return data.skill as Skill;
  }
);

export const updateSkill = createAsyncThunk(
  'skills/update',
  async ({ id, ...updates }: Partial<Skill> & { id: string }) => {
    const res = await fetch(`${SKILLS_API}/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates),
    });
    const data = await res.json();
    return data.skill as Skill;
  }
);

export const fetchSkillCandidates = createAsyncThunk(
  'skills/fetchCandidates',
  async () => {
    const res = await fetch(`${SKILLS_API}/candidates/list`);
    const data = await res.json();
    return data.candidates as SkillSpecCandidate[];
  },
  { condition: (_, { getState }) => !(getState() as { skills: SkillsState }).skills.candidatesLoading },
);

export const fetchSkillCandidateRequirementsContract = createAsyncThunk(
  'skills/fetchCandidateRequirementsContract',
  async (candidateId: string) => {
    const res = await fetch(`${SKILLS_API}/candidates/${candidateId}/requirements-contract`);
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || 'Failed to fetch skill candidate requirements contract');
    }
    return await res.json() as SkillCandidateRequirementsContract;
  },
);

export const fetchSkillCandidateQualityReview = createAsyncThunk(
  'skills/fetchCandidateQualityReview',
  async (candidateId: string) => {
    const res = await fetch(`${SKILLS_API}/candidates/${candidateId}/quality-review`);
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || 'Failed to fetch skill candidate quality review');
    }
    return await res.json() as SkillCandidateQualityReview;
  },
);


export const fetchSkillCandidateResearchContract = createAsyncThunk(
  'skills/fetchCandidateResearchContract',
  async (candidateId: string) => {
    const res = await fetch(`${SKILLS_API}/candidates/${candidateId}/research-contract`);
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || 'Failed to fetch skill candidate research contract');
    }
    return await res.json() as SkillCandidateResearchContract;
  },
);


export const approveSkillCandidateResearch = createAsyncThunk(
  'skills/approveCandidateResearch',
  async ({ candidateId, approved }: { candidateId: string; approved: boolean }) => {
    const res = await fetch(`${SKILLS_API}/candidates/${candidateId}/research-approval`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ approved }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || 'Failed to update skill candidate research permission');
    }
    const data = await res.json();
    return {
      candidate: data.candidate as SkillSpecCandidate,
      researchContract: data.research_contract as SkillCandidateResearchContract | undefined,
      audit: data.audit as Record<string, any>,
    };
  },
);

export const executeSkillCandidateResearch = createAsyncThunk(
  'skills/executeCandidateResearch',
  async (candidateId: string) => {
    const res = await fetch(`${SKILLS_API}/candidates/${candidateId}/research-execute`, {
      method: 'POST',
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || 'Failed to execute skill candidate research');
    }
    const data = await res.json();
    return {
      candidate: data.candidate as SkillSpecCandidate,
      researchContract: data.research_contract as SkillCandidateResearchContract | undefined,
      evidence: Array.isArray(data.evidence) ? data.evidence as Record<string, any>[] : [],
      audit: data.audit as Record<string, any>,
    };
  },
);

export const fetchSkillCandidateImprovementProposal = createAsyncThunk(
  'skills/fetchCandidateImprovementProposal',
  async (candidateId: string) => {
    const res = await fetch(`${SKILLS_API}/candidates/${candidateId}/improvement-proposal`);
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || 'Failed to fetch skill candidate improvement proposal');
    }
    return await res.json() as SkillCandidateImprovementProposal;
  },
);

export const applySkillCandidateImprovementProposal = createAsyncThunk(
  'skills/applyCandidateImprovementProposal',
  async ({ candidateId, approved }: { candidateId: string; approved: boolean }) => {
    const res = await fetch(`${SKILLS_API}/candidates/${candidateId}/improvement-proposal/apply`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ approved }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || 'Failed to apply skill candidate improvement proposal');
    }
    const data = await res.json();
    return {
      candidate: data.candidate as SkillSpecCandidate,
      proposal: data.proposal as SkillCandidateImprovementProposal,
      audit: data.audit as Record<string, any>,
    };
  },
);

export const previewSkillImport = createAsyncThunk(
  'skills/previewImport',
  async (body: SkillImportPreviewRequest) => {
    const res = await fetch(`${SKILLS_API}/import/preview`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || 'Failed to preview skill import');
    }
    return data as SkillImportPreviewResult;
  }
);

export const createSkillCandidateFromImport = createAsyncThunk(
  'skills/createCandidateFromImport',
  async (body: SkillImportPreviewRequest) => {
    const res = await fetch(`${SKILLS_API}/import/candidates/create`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...body, create_candidate: true }),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || 'Failed to create skill candidate from import');
    }
    return {
      candidate: data.candidate as SkillSpecCandidate,
      preview: data.preview as Record<string, any>,
      policy: data.policy as Record<string, any>,
    };
  }
);

export const createSkillCandidate = createAsyncThunk(
  'skills/createCandidate',
  async (body: SkillCandidateCreateBody) => {
    const res = await fetch(`${SKILLS_API}/candidates/create`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return data.candidate as SkillSpecCandidate;
  }
);

export const approveSkillCandidate = createAsyncThunk(
  'skills/approveCandidate',
  async ({ candidateId, approved }: { candidateId: string; approved: boolean }) => {
    const res = await fetch(`${SKILLS_API}/candidates/${candidateId}/approval`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ approved }),
    });
    const data = await res.json();
    return data.candidate as SkillSpecCandidate;
  }
);

export const installSkillCandidate = createAsyncThunk(
  'skills/installCandidate',
  async (candidateId: string) => {
    const res = await fetch(`${SKILLS_API}/candidates/${candidateId}/install`, {
      method: 'POST',
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || 'Failed to install skill candidate');
    }
    const data = await res.json();
    return {
      candidate: data.candidate as SkillSpecCandidate,
      skill: data.skill as Skill,
      audit: data.audit as Record<string, any>,
    };
  }
);

export const rejectSkillCandidate = createAsyncThunk(
  'skills/rejectCandidate',
  async (candidateId: string) => {
    const res = await fetch(`${SKILLS_API}/candidates/${candidateId}/reject`, {
      method: 'POST',
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || 'Failed to reject skill candidate');
    }
    const data = await res.json();
    return data.candidate as SkillSpecCandidate;
  }
);

export const deleteSkillCandidate = createAsyncThunk(
  'skills/deleteCandidate',
  async (candidateId: string) => {
    const res = await fetch(`${SKILLS_API}/candidates/${candidateId}`, {
      method: 'DELETE',
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || 'Failed to delete skill candidate');
    }
    return candidateId;
  }
);

export const deleteSkill = createAsyncThunk('skills/delete', async (id: string) => {
  await fetch(`${SKILLS_API}/${id}`, { method: 'DELETE' });
  return id;
});

const skillsSlice = createSlice({
  name: 'skills',
  initialState,
  reducers: {},
  extraReducers: (builder) => {
    builder
      .addCase(fetchSkills.pending, (state) => { state.loading = true; })
      .addCase(fetchSkills.fulfilled, (state, action) => {
        state.loading = false;
        state.loaded = true;
        state.items = {};
        for (const s of action.payload) state.items[s.id] = s;
      })
      .addCase(fetchSkills.rejected, (state) => { state.loading = false; state.loaded = true; })
      .addCase(createSkill.fulfilled, (state, action) => { state.items[action.payload.id] = action.payload; })
      .addCase(updateSkill.fulfilled, (state, action) => { state.items[action.payload.id] = action.payload; })
      .addCase(deleteSkill.fulfilled, (state, action) => { delete state.items[action.payload]; })
      .addCase(fetchSkillCandidates.pending, (state) => { state.candidatesLoading = true; })
      .addCase(fetchSkillCandidates.fulfilled, (state, action) => {
        state.candidatesLoading = false;
        state.candidatesLoaded = true;
        state.candidates = {};
        for (const candidate of action.payload) state.candidates[candidate.candidate_id] = candidate;
      })
      .addCase(fetchSkillCandidates.rejected, (state) => {
        state.candidatesLoading = false;
        state.candidatesLoaded = true;
      })
      .addCase(fetchSkillCandidateRequirementsContract.pending, (state, action) => {
        state.candidateRequirementsContractsLoading[action.meta.arg] = true;
        state.candidateRequirementsContractsError[action.meta.arg] = null;
      })
      .addCase(fetchSkillCandidateRequirementsContract.fulfilled, (state, action) => {
        state.candidateRequirementsContractsLoading[action.payload.candidate_id] = false;
        state.candidateRequirementsContracts[action.payload.candidate_id] = action.payload;
      })
      .addCase(fetchSkillCandidateRequirementsContract.rejected, (state, action) => {
        state.candidateRequirementsContractsLoading[action.meta.arg] = false;
        state.candidateRequirementsContractsError[action.meta.arg] = action.error.message || 'Failed to fetch requirements contract';
      })
      .addCase(fetchSkillCandidateQualityReview.pending, (state, action) => {
        state.candidateQualityReviewsLoading[action.meta.arg] = true;
        state.candidateQualityReviewsError[action.meta.arg] = null;
      })
      .addCase(fetchSkillCandidateQualityReview.fulfilled, (state, action) => {
        state.candidateQualityReviewsLoading[action.payload.candidate_id] = false;
        state.candidateQualityReviews[action.payload.candidate_id] = action.payload;
      })
      .addCase(fetchSkillCandidateQualityReview.rejected, (state, action) => {
        state.candidateQualityReviewsLoading[action.meta.arg] = false;
        state.candidateQualityReviewsError[action.meta.arg] = action.error.message || 'Failed to fetch quality review';
      })

      .addCase(fetchSkillCandidateResearchContract.pending, (state, action) => {
        state.candidateResearchContractsLoading[action.meta.arg] = true;
        state.candidateResearchContractsError[action.meta.arg] = null;
      })
      .addCase(fetchSkillCandidateResearchContract.fulfilled, (state, action) => {
        state.candidateResearchContractsLoading[action.payload.candidate_id] = false;
        state.candidateResearchContracts[action.payload.candidate_id] = action.payload;
      })
      .addCase(fetchSkillCandidateResearchContract.rejected, (state, action) => {
        state.candidateResearchContractsLoading[action.meta.arg] = false;
        state.candidateResearchContractsError[action.meta.arg] = action.error.message || 'Failed to fetch research contract';
      })

      .addCase(approveSkillCandidateResearch.pending, (state, action) => {
        state.candidateResearchApprovalLoading[action.meta.arg.candidateId] = true;
        state.candidateResearchApprovalError[action.meta.arg.candidateId] = null;
      })
      .addCase(approveSkillCandidateResearch.fulfilled, (state, action) => {
        const candidateId = action.payload.candidate.candidate_id;
        state.candidateResearchApprovalLoading[candidateId] = false;
        state.candidates[candidateId] = action.payload.candidate;
        if (action.payload.researchContract) {
          state.candidateResearchContracts[candidateId] = action.payload.researchContract;
          state.candidateResearchContractsLoading[candidateId] = false;
          state.candidateResearchContractsError[candidateId] = null;
        }
      })
      .addCase(approveSkillCandidateResearch.rejected, (state, action) => {
        state.candidateResearchApprovalLoading[action.meta.arg.candidateId] = false;
        state.candidateResearchApprovalError[action.meta.arg.candidateId] = action.error.message || 'Failed to update research permission';
      })
      .addCase(executeSkillCandidateResearch.pending, (state, action) => {
        state.candidateResearchExecutionLoading[action.meta.arg] = true;
        state.candidateResearchExecutionError[action.meta.arg] = null;
      })
      .addCase(executeSkillCandidateResearch.fulfilled, (state, action) => {
        const candidateId = action.payload.candidate.candidate_id;
        state.candidateResearchExecutionLoading[candidateId] = false;
        state.candidates[candidateId] = action.payload.candidate;
        if (action.payload.researchContract) {
          state.candidateResearchContracts[candidateId] = action.payload.researchContract;
          state.candidateResearchContractsLoading[candidateId] = false;
          state.candidateResearchContractsError[candidateId] = null;
        }
        delete state.candidateImprovementProposals[candidateId];
      })
      .addCase(executeSkillCandidateResearch.rejected, (state, action) => {
        state.candidateResearchExecutionLoading[action.meta.arg] = false;
        state.candidateResearchExecutionError[action.meta.arg] = action.error.message || 'Failed to execute research';
      })
      .addCase(fetchSkillCandidateImprovementProposal.pending, (state, action) => {
        state.candidateImprovementProposalsLoading[action.meta.arg] = true;
        state.candidateImprovementProposalsError[action.meta.arg] = null;
      })
      .addCase(fetchSkillCandidateImprovementProposal.fulfilled, (state, action) => {
        state.candidateImprovementProposalsLoading[action.payload.candidate_id] = false;
        state.candidateImprovementProposals[action.payload.candidate_id] = action.payload;
      })
      .addCase(fetchSkillCandidateImprovementProposal.rejected, (state, action) => {
        state.candidateImprovementProposalsLoading[action.meta.arg] = false;
        state.candidateImprovementProposalsError[action.meta.arg] = action.error.message || 'Failed to fetch improvement proposal';
      })
      .addCase(applySkillCandidateImprovementProposal.pending, (state, action) => {
        state.candidateImprovementApplyLoading[action.meta.arg.candidateId] = true;
        state.candidateImprovementApplyError[action.meta.arg.candidateId] = null;
      })
      .addCase(applySkillCandidateImprovementProposal.fulfilled, (state, action) => {
        state.candidateImprovementApplyLoading[action.payload.candidate.candidate_id] = false;
        state.candidates[action.payload.candidate.candidate_id] = action.payload.candidate;
        state.candidateImprovementProposals[action.payload.candidate.candidate_id] = action.payload.proposal;
      })
      .addCase(applySkillCandidateImprovementProposal.rejected, (state, action) => {
        state.candidateImprovementApplyLoading[action.meta.arg.candidateId] = false;
        state.candidateImprovementApplyError[action.meta.arg.candidateId] = action.error.message || 'Failed to apply improvement proposal';
      })
      .addCase(previewSkillImport.pending, (state) => {
        state.skillImportPreviewLoading = true;
        state.skillImportPreviewError = null;
      })
      .addCase(previewSkillImport.fulfilled, (state, action) => {
        state.skillImportPreviewLoading = false;
        state.skillImportPreview = action.payload;
      })
      .addCase(previewSkillImport.rejected, (state, action) => {
        state.skillImportPreviewLoading = false;
        state.skillImportPreviewError = action.error.message || 'Failed to preview skill import';
      })
      .addCase(createSkillCandidateFromImport.pending, (state) => {
        state.skillImportCandidateCreateLoading = true;
        state.skillImportCandidateCreateError = null;
      })
      .addCase(createSkillCandidateFromImport.fulfilled, (state, action) => {
        state.skillImportCandidateCreateLoading = false;
        state.candidates[action.payload.candidate.candidate_id] = action.payload.candidate;
      })
      .addCase(createSkillCandidateFromImport.rejected, (state, action) => {
        state.skillImportCandidateCreateLoading = false;
        state.skillImportCandidateCreateError = action.error.message || 'Failed to create skill candidate from import';
      })
      .addCase(createSkillCandidate.fulfilled, (state, action) => {
        state.candidates[action.payload.candidate_id] = action.payload;
      })
      .addCase(approveSkillCandidate.fulfilled, (state, action) => {
        state.candidates[action.payload.candidate_id] = action.payload;
      })
      .addCase(installSkillCandidate.fulfilled, (state, action) => {
        state.candidates[action.payload.candidate.candidate_id] = action.payload.candidate;
        state.items[action.payload.skill.id] = action.payload.skill;
      })
      .addCase(rejectSkillCandidate.fulfilled, (state, action) => {
        state.candidates[action.payload.candidate_id] = action.payload;
      })
      .addCase(deleteSkillCandidate.fulfilled, (state, action) => {
        delete state.candidates[action.payload];
      });
  },
});

export default skillsSlice.reducer;
