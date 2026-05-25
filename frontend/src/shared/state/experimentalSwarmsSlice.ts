import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import { API_BASE } from '@/shared/config';
import type { SwarmMode } from './dashboardLayoutSlice';

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
  async ({ userPrompt, dashboardId, intent, swarmMode, swarmModel }: {
    userPrompt: string;
    dashboardId?: string;
    intent?: 'chat' | 'task';
    swarmMode?: SwarmMode;
    swarmModel?: string | null;
  }) => {
    const res = await fetch(`${SWARMS_API}/create`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_prompt: userPrompt,
        dashboard_id: dashboardId,
        intent,
        swarm_mode: swarmMode,
        swarm_model: swarmModel,
      }),
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

export const startExperimentalImplementation = createAsyncThunk(
  'experimentalSwarms/startImplementation',
  async ({ swarmId, workspacePath }: { swarmId: string; workspacePath?: string }) => {
    const res = await fetch(`${SWARMS_API}/${swarmId}/experimental/start-implementation`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ workspace_path: workspacePath }),
    });
    return await readJson(res);
  },
);

export const createOutputBridgeFromSwarm = createAsyncThunk(
  'experimentalSwarms/createOutputBridge',
  async ({ swarmId, name, description }: { swarmId: string; name?: string; description?: string }) => {
    const res = await fetch(`${SWARMS_API}/${swarmId}/experimental/output-bridge/create`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        approve: true,
        name,
        description,
      }),
    });
    return await readJson(res);
  },
);

export const chatExperimentalSwarm = createAsyncThunk(
  'experimentalSwarms/chat',
  async ({ swarmId, message, swarmMode, model }: {
    swarmId: string;
    message: string;
    swarmMode?: SwarmMode;
    model?: string | null;
  }) => {
    const body: Record<string, any> = { message, swarm_mode: swarmMode };
    if (model) body.model = model;
    const res = await fetch(`${SWARMS_API}/${swarmId}/experimental/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
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

export const updateOrchestrationNodePosition = createAsyncThunk(
  'experimentalSwarms/updateOrchestrationNodePosition',
  async ({ swarmId, nodeId, x, y, expanded }: { swarmId: string; nodeId: string; x?: number; y?: number; expanded?: boolean }) => {
    const res = await fetch(`${SWARMS_API}/${swarmId}/orchestration-canvas/nodes/position`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ node_id: nodeId, x, y, expanded }),
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
    clearExperimentalSwarm(state) {
      state.selectedSwarmId = null;
      state.swarm = null;
      state.events = [];
      state.artifacts = [];
      state.messages = [];
      state.approvals = [];
      state.pendingCount = 0;
      state.loading = false;
      state.actionLoading = false;
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
        if (state.selectedSwarmId !== action.meta.arg) return;
        state.loading = false;
        state.swarm = action.payload.swarm;
        state.events = action.payload.events.events || [];
        state.artifacts = action.payload.artifacts.artifacts || [];
        state.messages = action.payload.messages.messages || [];
        state.approvals = action.payload.approvals.approvals || [];
        state.pendingCount = action.payload.approvals.pending_count || 0;
      })
      .addCase(chatExperimentalSwarm.fulfilled, (state, action) => {
        if (action.meta.arg.swarmId && state.selectedSwarmId && state.selectedSwarmId !== action.meta.arg.swarmId) return;
        state.selectedSwarmId = action.meta.arg.swarmId;
        state.swarm = action.payload;
        state.events = action.payload.events || [];
        state.artifacts = action.payload.artifacts || [];
        state.messages = action.payload.messages || [];
        state.approvals = action.payload.experimental_approvals || [];
        state.pendingCount = (action.payload.experimental_approvals || []).filter((approval: any) => approval.status === 'pending').length;
      })
      .addCase(startExperimentalImplementation.fulfilled, (state, action) => {
        const payload = action.payload || {};
        state.actionLoading = false;
        state.error = null;

        if (!state.swarm) {
          state.swarm = payload;
          return;
        }

        state.swarm = {
          ...state.swarm,
          ...(payload.id ? payload : {}),
          implementation: payload.implementation ?? state.swarm.implementation,
          final_result: payload.final_result ?? state.swarm.final_result,
          final_evidence: payload.final_evidence ?? state.swarm.final_evidence,
          orchestration_canvas_state: payload.orchestration_canvas_state ?? state.swarm.orchestration_canvas_state,
        };
        if (Array.isArray(payload.messages)) {
          state.messages = payload.messages;
        }
        if (Array.isArray(payload.artifacts)) {
          state.artifacts = payload.artifacts;
        }
      })
      .addCase(updateOrchestrationNodePosition.fulfilled, (state, action) => {
        state.swarm = action.payload;
        state.error = null;
      })
      .addCase(fetchExperimentalSwarm.rejected, (state, action) => {
        if (state.selectedSwarmId !== action.meta.arg) return;
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

export const { selectExperimentalSwarm, clearExperimentalSwarmError, clearExperimentalSwarm } = experimentalSwarmsSlice.actions;

export default experimentalSwarmsSlice.reducer;
