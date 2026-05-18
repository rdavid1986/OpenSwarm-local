import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import { API_BASE } from '@/shared/config';

const AGENTS_API = `${API_BASE}/agents`;

export interface PersistentPlanSummary {
  id: string;
  title: string;
  status: string;
  created_at?: string;
  updated_at?: string;
  path?: string;
  mode_label?: string;
  display_label?: string;
  technical_id?: string;
  dashboard_id?: string | null;
}

export interface PersistentPlanDetail {
  ok: boolean;
  plan_id: string;
  path?: string;
  plan?: {
    id: string;
    title: string;
    created_at?: string;
    updated_at?: string;
    session_id?: string | null;
    last_execution_session_id?: string | null;
    dashboard_id?: string | null;
    source_mode?: string;
    status?: string;
    current_phase_index?: number;
    completed_phase_indexes?: number[];
    failed_phase_indexes?: number[];
    last_error?: string | null;
    phases?: Array<{
      title?: string;
      name?: string;
      description?: string;
      content?: string;
      status?: string;
      [key: string]: any;
    }>;
    content?: string;
  };
}

export interface ExecutePlanPayload {
  sessionId: string;
  planId: string;
}

interface PlansState {
  items: Record<string, PersistentPlanSummary>;
  selectedPlanId: string | null;
  selectedPlanDetail: PersistentPlanDetail | null;
  loading: boolean;
  detailLoading: boolean;
  executing: boolean;
  error: string | null;
}

const initialState: PlansState = {
  items: {},
  selectedPlanId: null,
  selectedPlanDetail: null,
  loading: false,
  detailLoading: false,
  executing: false,
  error: null,
};

export const fetchPlans = createAsyncThunk(
  'plans/fetchPlans',
  async ({ dashboardId }: { dashboardId?: string } = {}) => {
    const qs = dashboardId ? `?dashboard_id=${encodeURIComponent(dashboardId)}` : '';
    const res = await fetch(`${AGENTS_API}/plans${qs}`);
    if (!res.ok) throw new Error(`Failed to fetch plans: ${res.status}`);
    const data = await res.json();
    return data.plans as PersistentPlanSummary[];
  },
);

export const fetchPlanDetail = createAsyncThunk('plans/fetchPlanDetail', async (planId: string) => {
  const res = await fetch(`${AGENTS_API}/plans/${planId}`);
  if (!res.ok) throw new Error(`Failed to fetch plan detail: ${res.status}`);
  return (await res.json()) as PersistentPlanDetail;
});

export const executePlan = createAsyncThunk('plans/executePlan', async ({ sessionId, planId }: ExecutePlanPayload) => {
  const res = await fetch(`${AGENTS_API}/sessions/${sessionId}/execute-plan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ plan_id: planId }),
  });
  if (!res.ok) throw new Error(`Failed to execute plan: ${res.status}`);
  return await res.json();
});

const plansSlice = createSlice({
  name: 'plans',
  initialState,
  reducers: {
    selectPlan(state, action: PayloadAction<string | null>) {
      state.selectedPlanId = action.payload;
      if (!action.payload) {
        state.selectedPlanDetail = null;
      }
    },
    clearPlansError(state) {
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchPlans.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchPlans.fulfilled, (state, action) => {
        state.loading = false;
        state.items = {};
        for (const plan of action.payload) {
          state.items[plan.id] = plan;
        }
      })
      .addCase(fetchPlans.rejected, (state, action) => {
        state.loading = false;
        state.error = action.error.message || 'Failed to fetch plans';
      })
      .addCase(fetchPlanDetail.pending, (state) => {
        state.detailLoading = true;
        state.error = null;
      })
      .addCase(fetchPlanDetail.fulfilled, (state, action) => {
        state.detailLoading = false;
        state.selectedPlanId = action.payload.plan_id;
        state.selectedPlanDetail = action.payload;
      })
      .addCase(fetchPlanDetail.rejected, (state, action) => {
        state.detailLoading = false;
        state.error = action.error.message || 'Failed to fetch plan detail';
      })
      .addCase(executePlan.pending, (state) => {
        state.executing = true;
        state.error = null;
      })
      .addCase(executePlan.fulfilled, (state) => {
        state.executing = false;
      })
      .addCase(executePlan.rejected, (state, action) => {
        state.executing = false;
        state.error = action.error.message || 'Failed to execute plan';
      });
  },
});

export const { selectPlan, clearPlansError } = plansSlice.actions;

export default plansSlice.reducer;
