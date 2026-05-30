import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import { API_BASE } from '@/shared/config';

const AGENTS_API = `${API_BASE}/agents`;

export interface ModelOption {
  value: string;
  label: string;
  version?: string;
  context_window: number;
  reasoning?: boolean;
  context_window_source?: 'estimated' | 'measured' | 'declared' | 'configured' | 'loaded' | 'unknown';
  estimated_context_window?: number | null;
  estimated_context_source?: string | null;
  configured_context_window?: number | null;
  configured_context_source?: string | null;
  declared_context_window?: number | null;
  declared_context_source?: string | null;
  loaded_context_window?: number | null;
  loaded_context_source?: string | null;
  reasoning_source?: 'estimated' | 'measured' | 'declared' | 'reported' | 'inferred' | 'not_reported' | 'unknown';
  tiers_source?: 'estimated' | 'measured' | 'declared' | 'unknown';
  // Optional picker-UX fields from list_models.
  input_cost_per_1m?: number;
  output_cost_per_1m?: number;
  is_free?: boolean;
  max_completion_tokens?: number | null;
  tiers?: [number, number, number];  // (intelligence, speed, cost), 1-5.
  billing_kind?: 'paid' | 'subscription' | 'free' | 'api_key';
  provider?: string;
  metadata_source?: string;
  name?: string | null;
  model?: string | null;
  local_model_name?: string | null;
  modified_at?: string | null;
  size_bytes?: number | null;
  digest?: string | null;
  format?: string | null;
  family?: string | null;
  families?: string[] | null;
  parameter_size?: string | null;
  quantization_level?: string | null;
  local_metadata?: Record<string, any> | null;
  model_metadata?: Record<string, any> | null;
  availability?: 'available' | 'unknown' | string;
  availability_source?: string | null;
  supports_thinking?: boolean;
  supports_tools?: boolean;
  supports_vision?: boolean;
  supports_embedding?: boolean;
  supports_structured_output?: boolean;
  supports_json?: boolean;
  supports_keep_alive?: boolean;
  capability_source?: Record<string, string> | null;
  loaded?: boolean;
  running?: boolean;
  expires_at?: string | null;
  reasoning_effort?: Record<string, any> | null;
  runtime_metrics?: Record<string, any> | null;
  eval_results?: Record<string, any> | null;
}

interface ModelsState {
  byProvider: Record<string, ModelOption[]>;
  loaded: boolean;
}

const initialState: ModelsState = {
  byProvider: {},
  loaded: false,
};

export const fetchModels = createAsyncThunk('models/fetchModels', async () => {
  const res = await fetch(`${AGENTS_API}/models`, {
    headers: { 'x-api-key': 'local-dev-token' },
  });
  if (!res.ok) throw new Error('Failed to fetch models');
  const data = await res.json();
  // DEBUG LOCAL OLLAMA
  console.log('[OpenSwarm models response]', data);
  // API returns { models: { provider: [...] } }
  const models = data.models || data;
  console.log('[OpenSwarm models parsed]', models);
  return models as Record<string, ModelOption[]>;
});

const modelsSlice = createSlice({
  name: 'models',
  initialState,
  reducers: {},
  extraReducers: (builder) => {
    builder
      .addCase(fetchModels.fulfilled, (state, action) => {
        state.byProvider = action.payload;
        state.loaded = true;
      })
      .addCase(fetchModels.rejected, (state) => {
        // Mark as loaded even on failure so we fall back to hardcoded options
        state.loaded = true;
      });
  },
});

export default modelsSlice.reducer;
