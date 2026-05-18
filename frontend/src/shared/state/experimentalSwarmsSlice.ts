import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import { API_BASE } from '@/shared/config';

const SWARMS_API = `${API_BASE}/swarms`;

export interface ExperimentalSwarmState {
  selectedSwarmId: string | null;
  swarm: any | null;
  events: any[];
  artifacts: any[];
  messages: any[];
  approvals: any[];
  pendingCount: number;
  loading: boolean;
  actionLoading: boolean;
  error: string | null;
}

const initialState: ExperimentalSwarmState = {
  selectedSwarmId: null,
  swarm: null,
  events: [],
  artifacts: [],
  messages: [],
  approvals: [],
  pendingCount: 0,
  loading: false,
  actionLoading: false,
  error: null,
};

async function readJson(res: Response): Promise<any> {
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Request failed: ${res.status}`);
  return data;
}


export const createExperimentalSwarm = createAsyncThunk(
  'experimentalSwarms/create',
  async ({ userPrompt, dashboardId }: { userPrompt: string; dashboardId?: string }) => {
    const res = await fetch(`${SWARMS_API}/create`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_prompt: userPrompt, dashboard_id: dashboardId }),
    });
    return await readJson(res);
  },
);

export const fetchExperimentalSwarm = createAsyncThunk(
  'experimentalSwarms/fetch',
  async (swarmId: string) => {
    const [swarm, events, artifacts, messages, approvals] = await Promise.all([
      fetch(`${SWARMS_API}/${swarmId}`).then(readJson),
      fetch(`${SWARMS_API}/${swarmId}/events`).then(readJson),
      fetch(`${SWARMS_API}/${swarmId}/artifacts`).then(readJson),
      fetch(`${SWARMS_API}/${swarmId}/messages`).then(readJson),
      fetch(`${SWARMS_API}/${swarmId}/experimental/approvals`).then(readJson),
    ]);

    return { swarm, events, artifacts, messages, approvals };
  },
);

export const runExperimentalDag = createAsyncThunk(
  'experimentalSwarms/runDag',
  async ({ swarmId, workspacePath }: { swarmId: string; workspacePath?: string }) => {
    const res = await fetch(`${SWARMS_API}/${swarmId}/experimental/run-dag-dependencies`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ workspace_path: workspacePath }),
    });
    return await readJson(res);
  },
);

export const chatExperimentalSwarm = createAsyncThunk(
  'experimentalSwarms/chat',
  async ({ swarmId, message }: { swarmId: string; message: string }) => {
    const res = await fetch(`${SWARMS_API}/${swarmId}/experimental/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
    });
    return await readJson(res);
  },
);

export const allowExperimentalApproval = createAsyncThunk(
  'experimentalSwarms/allowApproval',
  async ({ swarmId, approvalId }: { swarmId: string; approvalId: string }) => {
    const res = await fetch(`${SWARMS_API}/${swarmId}/experimental/approvals/${approvalId}/allow`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: 'approved from experimental UI' }),
    });
    return await readJson(res);
  },
);

export const denyExperimentalApproval = createAsyncThunk(
  'experimentalSwarms/denyApproval',
  async ({ swarmId, approvalId }: { swarmId: string; approvalId: string }) => {
    const res = await fetch(`${SWARMS_API}/${swarmId}/experimental/approvals/${approvalId}/deny`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: 'denied from experimental UI' }),
    });
    return await readJson(res);
  },
);

export const resumeExperimentalApproval = createAsyncThunk(
  'experimentalSwarms/resumeApproval',
  async ({ swarmId, approvalId }: { swarmId: string; approvalId: string }) => {
    const res = await fetch(`${SWARMS_API}/${swarmId}/experimental/approvals/${approvalId}/resume`, {
      method: 'POST',
    });
    return await readJson(res);
  },
);

const experimentalSwarmsSlice = createSlice({
  name: 'experimentalSwarms',
  initialState,
  reducers: {
    selectExperimentalSwarm(state, action: PayloadAction<string | null>) {
      state.selectedSwarmId = action.payload;
    },
    clearExperimentalSwarmError(state) {
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(createExperimentalSwarm.pending, (state) => {
        state.actionLoading = true;
        state.error = null;
      })
      .addCase(createExperimentalSwarm.fulfilled, (state, action) => {
        state.actionLoading = false;
        state.selectedSwarmId = action.payload.id;
        state.swarm = action.payload;
        state.events = [];
        state.artifacts = [];
        state.messages = [];
        state.approvals = [];
        state.pendingCount = 0;
      })
      .addCase(createExperimentalSwarm.rejected, (state, action) => {
        state.actionLoading = false;
        state.error = action.error.message || 'Failed to create experimental swarm';
      })
      .addCase(fetchExperimentalSwarm.pending, (state, action) => {
        state.loading = true;
        state.error = null;
        state.selectedSwarmId = action.meta.arg;
      })
      .addCase(fetchExperimentalSwarm.fulfilled, (state, action) => {
        state.loading = false;
        state.swarm = action.payload.swarm;
        state.events = action.payload.events.events || [];
        state.artifacts = action.payload.artifacts.artifacts || [];
        state.messages = action.payload.messages.messages || [];
        state.approvals = action.payload.approvals.approvals || [];
        state.pendingCount = action.payload.approvals.pending_count || 0;
      })
      .addCase(chatExperimentalSwarm.fulfilled, (state, action) => {
        state.swarm = action.payload;
        state.events = action.payload.events || [];
        state.artifacts = action.payload.artifacts || [];
        state.messages = action.payload.messages || [];
        state.approvals = action.payload.experimental_approvals || [];
        state.pendingCount = (action.payload.experimental_approvals || []).filter((approval: any) => approval.status === 'pending').length;
      })
      .addCase(fetchExperimentalSwarm.rejected, (state, action) => {
        state.loading = false;
        state.error = action.error.message || 'Failed to fetch experimental swarm';
      })
      .addMatcher(
        (action) =>
          action.type.startsWith('experimentalSwarms/') &&
          action.type.endsWith('/pending') &&
          action.type !== fetchExperimentalSwarm.pending.type,
        (state) => {
          state.actionLoading = true;
          state.error = null;
        },
      )
      .addMatcher(
        (action) =>
          action.type.startsWith('experimentalSwarms/') &&
          action.type.endsWith('/fulfilled') &&
          action.type !== fetchExperimentalSwarm.fulfilled.type,
        (state) => {
          state.actionLoading = false;
        },
      )
      .addMatcher(
        (action) =>
          action.type.startsWith('experimentalSwarms/') &&
          action.type.endsWith('/rejected') &&
          action.type !== fetchExperimentalSwarm.rejected.type,
        (state, action: any) => {
          state.actionLoading = false;
          state.error = action.error?.message || 'Experimental swarm action failed';
        },
      );
  },
});

export const { selectExperimentalSwarm, clearExperimentalSwarmError } = experimentalSwarmsSlice.actions;

export default experimentalSwarmsSlice.reducer;
