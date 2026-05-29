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
}

export type SkillCandidateCreateBody = Partial<Omit<SkillSpecCandidate, 'skill_spec'>> & {
  skill_spec: Partial<SkillSpec> & Pick<SkillSpec, 'name'>;
};

interface SkillsState {
  items: Record<string, Skill>;
  loading: boolean;
  loaded: boolean;
  candidates: Record<string, SkillSpecCandidate>;
  candidatesLoading: boolean;
  candidatesLoaded: boolean;
}

const initialState: SkillsState = {
  items: {},
  loading: false,
  loaded: false,
  candidates: {},
  candidatesLoading: false,
  candidatesLoaded: false,
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
