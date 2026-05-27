import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import { API_BASE } from '@/shared/config';

const TOOLS_API = `${API_BASE}/tools`;

export interface ToolDefinition {
  id: string;
  name: string;
  description: string;
  command: string;
  mcp_config: Record<string, any>;
  credentials: Record<string, string>;
  auth_type: string;
  auth_status: string;
  oauth_tokens: Record<string, any>;
  tool_permissions: Record<string, any>;
  connected_account_email?: string;
  enabled?: boolean;
}

export interface McpPersistedSettingsSnapshot {
  contract_kind: 'mcp_persisted_settings_snapshot';
  tool_id?: string | null;
  name?: string | null;
  server_name?: string | null;
  description?: string | null;
  enabled: boolean;
  auth_type: string;
  auth_status: string;
  connected_account_email?: string | null;
  transport: string;
  command?: string | null;
  args: any[];
  url_configured: boolean;
  env_keys: string[];
  header_keys: string[];
  sanitized_mcp_config: Record<string, any>;
  tool_permissions: Record<string, string>;
  permission_count: number;
  sandbox_decision?: string | null;
  sandbox_reasons: any[];
  secrets_persisted: false;
  activation_scope: 'session_only';
  activation_gate: string;
  executed: false;
  execution_result: null;
}

export interface McpSettingsStoreSnapshot {
  contract_kind: 'mcp_settings_store_snapshot';
  tools: McpPersistedSettingsSnapshot[];
  tool_count: number;
  enabled_count: number;
  configured_count: number;
  secrets_persisted: false;
  activation_scope: 'session_only';
  activation_gate: string;
  executed: false;
  execution_result: null;
}

export interface BuiltinTool {
  name: string;
  display_name?: string;
  description: string;
  category: string;
  deferred: boolean;
}

interface ToolsState {
  items: Record<string, ToolDefinition>;
  builtinTools: BuiltinTool[];
  builtinPermissions: Record<string, string>;
  loading: boolean;
  loaded: boolean;
  builtinLoaded: boolean;
  mcpSettingsSnapshot: McpSettingsStoreSnapshot | null;
  mcpSettingsSnapshotLoading: boolean;
}

const initialState: ToolsState = { items: {}, builtinTools: [], builtinPermissions: {}, loading: false, loaded: false, builtinLoaded: false, mcpSettingsSnapshot: null, mcpSettingsSnapshotLoading: false };

export const fetchTools = createAsyncThunk(
  'tools/fetch',
  async () => {
    const res = await fetch(`${TOOLS_API}/list`);
    const data = await res.json();
    return data.tools as ToolDefinition[];
  },
  { condition: (_, { getState }) => !(getState() as { tools: ToolsState }).tools.loading },
);

export const fetchMcpSettingsSnapshot = createAsyncThunk(
  'tools/fetchMcpSettingsSnapshot',
  async () => {
    const res = await fetch(`${TOOLS_API}/mcp/settings-snapshot`);
    const data = await res.json();
    return data as McpSettingsStoreSnapshot;
  }
);

export const fetchBuiltinTools = createAsyncThunk(
  'tools/fetchBuiltin',
  async () => {
    const res = await fetch(`${TOOLS_API}/builtin`);
    const data = await res.json();
    return data.tools as BuiltinTool[];
  },
  { condition: (_, { getState }) => !(getState() as { tools: ToolsState }).tools.builtinLoaded },
);

export const createTool = createAsyncThunk(
  'tools/create',
  async (body: Partial<Omit<ToolDefinition, 'id'>> & { name: string }) => {
    const res = await fetch(`${TOOLS_API}/create`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return data.tool as ToolDefinition;
  }
);

export const updateTool = createAsyncThunk(
  'tools/update',
  async ({ id, ...updates }: Partial<ToolDefinition> & { id: string }) => {
    const res = await fetch(`${TOOLS_API}/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates),
    });
    const data = await res.json();
    return data.tool as ToolDefinition;
  }
);

export const deleteTool = createAsyncThunk('tools/delete', async (id: string) => {
  await fetch(`${TOOLS_API}/${id}`, { method: 'DELETE' });
  return id;
});

export const startOAuth = createAsyncThunk(
  'tools/startOAuth',
  async (toolId: string) => {
    const res = await fetch(`${TOOLS_API}/${toolId}/oauth/start`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to start OAuth');
    const data = await res.json();
    return data as { auth_url: string };
  }
);

export const startDeviceCodeLogin = createAsyncThunk(
  'tools/startDeviceCodeLogin',
  async (toolId: string) => {
    const res = await fetch(`${TOOLS_API}/${toolId}/m365/device-login`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to start device code login');
    return await res.json();
  }
);

export const pollDeviceCodeStatus = createAsyncThunk(
  'tools/pollDeviceCodeStatus',
  async (toolId: string) => {
    const res = await fetch(`${TOOLS_API}/${toolId}/m365/device-login/status`);
    return await res.json();
  }
);

export const disconnectM365 = createAsyncThunk(
  'tools/disconnectM365',
  async (toolId: string) => {
    const res = await fetch(`${TOOLS_API}/${toolId}/m365/disconnect`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to disconnect M365');
    const data = await res.json();
    return data.tool as ToolDefinition;
  }
);

export const disconnectOAuth = createAsyncThunk(
  'tools/disconnectOAuth',
  async (toolId: string) => {
    const res = await fetch(`${TOOLS_API}/${toolId}/oauth/disconnect`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to disconnect OAuth');
    const data = await res.json();
    return data.tool as ToolDefinition;
  }
);

export const fetchToolStatus = createAsyncThunk(
  'tools/fetchStatus',
  async (toolId: string) => {
    const res = await fetch(`${TOOLS_API}/${toolId}`);
    const data = await res.json();
    return data as ToolDefinition;
  }
);

export const discoverTools = createAsyncThunk(
  'tools/discover',
  async (toolId: string) => {
    const res = await fetch(`${TOOLS_API}/${toolId}/discover`, { method: 'POST' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Discovery failed' }));
      throw new Error(err.detail || 'Discovery failed');
    }
    const data = await res.json();
    return data.tool as ToolDefinition;
  }
);

export const fetchBuiltinPermissions = createAsyncThunk('tools/fetchBuiltinPermissions', async () => {
  const res = await fetch(`${TOOLS_API}/builtin/permissions`);
  const data = await res.json();
  return data.permissions as Record<string, string>;
});

export const updateBuiltinPermissions = createAsyncThunk(
  'tools/updateBuiltinPermissions',
  async (permissions: Record<string, string>) => {
    const res = await fetch(`${TOOLS_API}/builtin/permissions`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ permissions }),
    });
    const data = await res.json();
    return data.permissions as Record<string, string>;
  }
);

const toolsSlice = createSlice({
  name: 'tools',
  initialState,
  reducers: {},
  extraReducers: (builder) => {
    builder
      .addCase(fetchTools.pending, (state) => { state.loading = true; })
      .addCase(fetchTools.fulfilled, (state, action) => {
        state.loading = false;
        state.loaded = true;
        state.items = {};
        for (const t of action.payload) state.items[t.id] = t;
      })
      .addCase(fetchTools.rejected, (state) => { state.loading = false; state.loaded = true; })
      .addCase(fetchMcpSettingsSnapshot.pending, (state) => { state.mcpSettingsSnapshotLoading = true; })
      .addCase(fetchMcpSettingsSnapshot.fulfilled, (state, action) => {
        state.mcpSettingsSnapshotLoading = false;
        state.mcpSettingsSnapshot = action.payload;
      })
      .addCase(fetchMcpSettingsSnapshot.rejected, (state) => { state.mcpSettingsSnapshotLoading = false; })
      .addCase(fetchBuiltinTools.fulfilled, (state, action) => { state.builtinTools = action.payload; state.builtinLoaded = true; })
      .addCase(createTool.fulfilled, (state, action) => { state.items[action.payload.id] = action.payload; })
      .addCase(updateTool.fulfilled, (state, action) => { state.items[action.payload.id] = action.payload; })
      .addCase(deleteTool.fulfilled, (state, action) => { delete state.items[action.payload]; })
      .addCase(disconnectOAuth.fulfilled, (state, action) => { state.items[action.payload.id] = action.payload; })
      .addCase(fetchToolStatus.fulfilled, (state, action) => { state.items[action.payload.id] = action.payload; })
      .addCase(discoverTools.fulfilled, (state, action) => { state.items[action.payload.id] = action.payload; })
      .addCase(fetchBuiltinPermissions.fulfilled, (state, action) => { state.builtinPermissions = action.payload; })
      .addCase(updateBuiltinPermissions.fulfilled, (state, action) => { state.builtinPermissions = action.payload; });
  },
});

export default toolsSlice.reducer;
