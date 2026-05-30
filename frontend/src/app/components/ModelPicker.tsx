import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Box from '@mui/material/Box';
import Collapse from '@mui/material/Collapse';
import Dialog from '@mui/material/Dialog';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import InputBase from '@mui/material/InputBase';
import ListItemText from '@mui/material/ListItemText';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import Slider from '@mui/material/Slider';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowRightIcon from '@mui/icons-material/KeyboardArrowRight';
import SearchIcon from '@mui/icons-material/Search';
import { useAppSelector } from '@/shared/hooks';
import { API_BASE } from '@/shared/config';
import { useClaudeTokens } from '@/shared/styles/ThemeContext';

interface Props {
  model: string;
  onModelChange: (model: string) => void;
  disabled?: boolean;
  compact?: boolean;
  onProviderChange?: (provider: string) => void;
}

const FALLBACK_MODELS = [
  { value: 'ollama/qwen2.5-coder:14b', label: 'Ollama Qwen 2.5 Coder 14B', context_window: 128_000, reasoning: true, billing_kind: 'free', is_free: true, context_window_source: 'estimated', reasoning_source: 'estimated', tiers_source: 'estimated', metadata_source: 'fallback (sin /api/tags)' },
  { value: 'ollama/qwen2.5-coder:32b', label: 'Ollama Qwen 2.5 Coder 32B', context_window: 128_000, reasoning: true, billing_kind: 'free', is_free: true, context_window_source: 'estimated', reasoning_source: 'estimated', tiers_source: 'estimated', metadata_source: 'fallback (sin /api/tags)' },
  { value: 'ollama/qwen3.6:latest', label: 'Ollama Qwen 3.6', context_window: 128_000, reasoning: true, billing_kind: 'free', is_free: true, context_window_source: 'estimated', reasoning_source: 'estimated', tiers_source: 'estimated', metadata_source: 'fallback (sin /api/tags)' },
  { value: 'ollama/codellama:34b', label: 'Ollama CodeLlama 34B', context_window: 16_000, reasoning: false, billing_kind: 'free', is_free: true, context_window_source: 'estimated', reasoning_source: 'estimated', tiers_source: 'estimated', metadata_source: 'fallback (sin /api/tags)' },
];

const PROVIDER_COLORS: Record<string, string> = {
  anthropic: '#E8927A',
  openai: '#74AA9C',
  google: '#4285F4',
  gemini: '#4285F4',
  xai: '#8B949E',
  meta: '#0866FF',
  deepseek: '#4D6BFE',
  mistral: '#FF7000',
  qwen: '#A974FF',
  cohere: '#FF7759',
  ollama: '#22c55e',
  openrouter: '#64748B',
};

const LS_RECENT_MODELS = 'openswarm.picker.recentModels';
const LS_RECENT_SEARCHES = 'openswarm.picker.recentSearches';
const LS_FILTERS_EXPANDED = 'openswarm.picker.filtersExpanded';
const LS_COLLAPSED_GROUPS = 'openswarm.picker.collapsedGroups';
const RECENT_MODELS_MAX = 3;
const RECENT_SEARCHES_MAX = 4;
const OR_AUTO_COLLAPSE_THRESHOLD = 12;
const CTX_STEPS = [0, 32_000, 128_000, 200_000, 500_000, 1_000_000];
const CTX_LABELS = ['Any', '32K+', '128K+', '200K+', '500K+', '1M+'];
const COST_STEPS = [Infinity, 50, 15, 5, 1, 0];
const COST_LABELS = ['Any', '≤$50/M', '≤$15/M', '≤$5/M', '≤$1/M', 'Free only'];

function readLS<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function writeLS(key: string, value: unknown) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* ignore */ }
}

type Tier = 1 | 2 | 3 | 4 | 5;
const clampTier = (n: number): Tier => Math.max(1, Math.min(5, n)) as Tier;

function costBucket(out: number): Tier {
  if (out < 0.5) return 1;
  if (out < 2) return 2;
  if (out < 7) return 3;
  if (out < 25) return 4;
  return 5;
}

function tierIntelligence(opt: any): Tier {
  let tier: number = costBucket(opt.output_cost_per_1m ?? 0);
  if (opt.reasoning) tier += 1;
  return clampTier(tier);
}

function tierSpeed(opt: any): Tier {
  let tier: number = 6 - costBucket(opt.output_cost_per_1m ?? 0);
  if (opt.reasoning) tier -= 1;
  const lower = String(opt.label || '').toLowerCase();
  if (/\b(mini|lite|flash|haiku|nano|small|fast|turbo|micro|tiny)\b/.test(lower)) tier += 1;
  if (/\b(opus|ultra|max|xlarge|titan)\b/.test(lower)) tier -= 1;
  return clampTier(tier);
}

function tierCost(opt: any): Tier {
  return costBucket(opt.output_cost_per_1m ?? 0);
}

function modelVersion(label: string): number {
  const matches = String(label).matchAll(/(\d+(?:\.\d+)?)/g);
  let bestVersion = 0;
  for (const m of matches) {
    const v = parseFloat(m[1]);
    if (v >= 0.5 && v < 30 && v > bestVersion) bestVersion = v;
  }
  return bestVersion;
}

function modelFamilyKey(label: string): string {
  return String(label)
    .toLowerCase()
    .replace(/\b\d+(?:\.\d+)?\b/g, '')
    .replace(/\(api key\)/gi, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function sortModelsForPicker<T extends { label: string }>(models: T[]): T[] {
  const intelOf = (opt: any): number => {
    if (Array.isArray(opt.tiers) && opt.tiers.length === 3) return opt.tiers[0];
    return tierIntelligence(opt);
  };
  return [...models].sort((a: any, b: any) => {
    const intelA = intelOf(a);
    const intelB = intelOf(b);
    if (intelA !== intelB) return intelB - intelA;
    const famA = modelFamilyKey(a.label);
    const famB = modelFamilyKey(b.label);
    if (famA !== famB) return famA.localeCompare(famB);
    const verA = modelVersion(a.label);
    const verB = modelVersion(b.label);
    if (verA !== verB) return verB - verA;
    return a.label.localeCompare(b.label);
  });
}

function formatTokenCount(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function sourceLabel(source?: string | null): string {
  if (source === 'estimated') return 'Estimated';
  if (source === 'measured') return 'Measured';
  if (source === 'declared') return 'Declared';
  if (source === 'reported') return 'Reported';
  if (source === 'inferred') return 'Inferred';
  if (source === 'not_reported') return 'Not reported';
  if (source === 'ollama_native_option') return 'Native option';
  return 'No data';
}

function formatBytes(bytes?: number | null): string {
  if (!bytes || !Number.isFinite(bytes)) return 'No data';
  const gib = bytes / (1024 ** 3);
  return `${gib.toFixed(gib >= 10 ? 1 : 2)} GiB`;
}

function formatDate(value?: string | null): string {
  if (!value) return 'No data';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function shortDigest(value?: string | null): string {
  if (!value) return 'No data';
  return value.length > 18 ? `${value.slice(0, 12)}…${value.slice(-6)}` : value;
}

function metadataCompleteness(opt: any): number {
  const fields = ['local_model_name', 'family', 'families', 'parameter_size', 'quantization_level', 'format', 'size_bytes', 'modified_at', 'digest'];
  const present = fields.filter((key) => {
    const value = opt[key];
    return Array.isArray(value) ? value.length > 0 : value !== undefined && value !== null && value !== '';
  }).length;
  return Math.round((present / fields.length) * 5);
}

function modelCapabilityChips(opt: any): string[] {
  const sourceOf = (key: string) => opt.capability_source?.[key] || 'unknown';
  const mk = (label: string, key: string) => `${label}${sourceOf(key) === 'inferred' ? '*' : ''}`;
  return [
    opt.supports_thinking && mk('thinking', 'thinking'),
    opt.supports_tools && mk('tools', 'tools'),
    opt.supports_vision && mk('vision', 'vision'),
    opt.supports_embedding && mk('embed', 'embedding'),
    opt.supports_json && mk('json', 'json'),
    opt.running && 'running',
    opt.loaded && !opt.running && 'loaded',
    opt.context_window ? `ctx ${formatTokenCount(Number(opt.context_window))}` : '',
  ].filter(Boolean).slice(0, 7) as string[];
}

const ModelPicker: React.FC<Props> = ({ model, onModelChange, disabled = false, compact = false, onProviderChange }) => {
  const c = useClaudeTokens();
  const modelsByProvider = useAppSelector((state) => state.models.byProvider);
  const modelsLoaded = useAppSelector((state) => state.models.loaded);
  const connectionMode = useAppSelector((state) => state.settings.data.connection_mode);
  const [modelAnchor, setModelAnchor] = useState<HTMLElement | null>(null);
  const [modelSearch, setModelSearch] = useState('');
  const modelSearchRef = useRef<HTMLInputElement | null>(null);
  const [recentModels, setRecentModels] = useState<string[]>(
    () => readLS<string[]>(LS_RECENT_MODELS, []).slice(0, RECENT_MODELS_MAX),
  );
  const [recentSearches, setRecentSearches] = useState<string[]>(() => readLS<string[]>(LS_RECENT_SEARCHES, []));
  const [capFilters, setCapFilters] = useState({ reasoning: false, subscription: false, apiKey: false });
  const [ctxIdx, setCtxIdx] = useState(0);
  const [costIdx, setCostIdx] = useState(0);
  const [filtersExpanded, setFiltersExpanded] = useState<boolean>(() => readLS<boolean>(LS_FILTERS_EXPANDED, false));
  const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>(
    () => readLS<Record<string, boolean>>(LS_COLLAPSED_GROUPS, {}),
  );
  const [compareMode, setCompareMode] = useState(false);
  const [compareValues, setCompareValues] = useState<string[]>([]);
  const [compareOpen, setCompareOpen] = useState(false);

  useEffect(() => {
    if (modelAnchor) {
      const t = setTimeout(() => modelSearchRef.current?.focus(), 30);
      return () => clearTimeout(t);
    }
    setModelSearch('');
  }, [modelAnchor]);

  const allModelOptions = useMemo(() => {
    if (!modelsLoaded || Object.keys(modelsByProvider).length === 0) {
      const key = 'Ollama Local';
      return { flat: FALLBACK_MODELS.map((m) => ({ ...m, provider: key })), grouped: { [key]: FALLBACK_MODELS } };
    }
    const flat: Array<any> = [];
    const grouped: Record<string, any[]> = {};
    for (const [prov, models] of Object.entries(modelsByProvider)) {
      const enriched = (models as any[]).map((m: any) => ({
        value: m.value,
        label: m.label,
        context_window: m.context_window ?? 200_000,
        estimated_context_window: m.estimated_context_window ?? null,
        estimated_context_source: m.estimated_context_source ?? null,
        configured_context_window: m.configured_context_window ?? null,
        configured_context_source: m.configured_context_source ?? null,
        declared_context_window: m.declared_context_window ?? null,
        declared_context_source: m.declared_context_source ?? null,
        loaded_context_window: m.loaded_context_window ?? null,
        loaded_context_source: m.loaded_context_source ?? null,
        reasoning: !!m.reasoning,
        context_window_source: m.context_window_source ?? 'unknown',
        reasoning_source: m.reasoning_source ?? 'unknown',
        tiers_source: m.tiers_source ?? 'unknown',
        input_cost_per_1m: m.input_cost_per_1m ?? 0,
        output_cost_per_1m: m.output_cost_per_1m ?? 0,
        is_free: !!m.is_free,
        max_completion_tokens: m.max_completion_tokens ?? null,
        tiers: Array.isArray(m.tiers) && m.tiers.length === 3 ? m.tiers : undefined,
        billing_kind: m.billing_kind,
        metadata_source: m.metadata_source,
        name: m.name,
        model: m.model,
        local_model_name: m.local_model_name,
        modified_at: m.modified_at,
        size_bytes: m.size_bytes,
        digest: m.digest,
        format: m.format,
        family: m.family,
        families: m.families,
        parameter_size: m.parameter_size,
        quantization_level: m.quantization_level,
        local_metadata: m.local_metadata,
        model_metadata: m.model_metadata,
        availability: m.availability,
        availability_source: m.availability_source,
        supports_thinking: !!m.supports_thinking,
        supports_tools: !!m.supports_tools,
        supports_vision: !!m.supports_vision,
        supports_embedding: !!m.supports_embedding,
        supports_structured_output: !!m.supports_structured_output,
        supports_json: !!m.supports_json,
        supports_keep_alive: !!m.supports_keep_alive,
        capability_source: m.capability_source,
        loaded: !!m.loaded,
        running: !!m.running,
        expires_at: m.expires_at,
        reasoning_effort: m.reasoning_effort,
        runtime_metrics: m.runtime_metrics,
        eval_results: m.eval_results,
      }));
      grouped[prov] = sortModelsForPicker(enriched);
      for (const m of enriched) flat.push({ ...m, provider: prov });
    }
    return { flat, grouped };
  }, [connectionMode, modelsByProvider, modelsLoaded]);

  const pushRecentModel = useCallback((value: string) => {
    setRecentModels((prev) => {
      const next = [value, ...prev.filter((v) => v !== value)].slice(0, RECENT_MODELS_MAX);
      writeLS(LS_RECENT_MODELS, next);
      return next;
    });
  }, []);

  const pushRecentSearch = useCallback((q: string) => {
    const trimmed = q.trim();
    if (!trimmed) return;
    setRecentSearches((prev) => {
      const next = [trimmed, ...prev.filter((s) => s !== trimmed)].slice(0, RECENT_SEARCHES_MAX);
      writeLS(LS_RECENT_SEARCHES, next);
      return next;
    });
  }, []);

  const toggleFilters = useCallback(() => {
    setFiltersExpanded((prev) => {
      writeLS(LS_FILTERS_EXPANDED, !prev);
      return !prev;
    });
  }, []);

  const toggleGroupCollapse = useCallback((prov: string, currentlyCollapsed: boolean) => {
    setCollapsedGroups((prev) => {
      const next = { ...prev, [prov]: !currentlyCollapsed };
      writeLS(LS_COLLAPSED_GROUPS, next);
      return next;
    });
  }, []);

  const anyFilterActive = capFilters.reasoning || capFilters.subscription || capFilters.apiKey || ctxIdx > 0 || costIdx > 0;

  const filteredModelGroups = useMemo(() => {
    const q = modelSearch.trim().toLowerCase();
    const minCtx = CTX_STEPS[ctxIdx] || 0;
    const maxCost = COST_STEPS[costIdx];
    const filterFn = (m: any): boolean => {
      if (capFilters.reasoning && !m.reasoning) return false;
      if (capFilters.subscription || capFilters.apiKey) {
        const okSub = capFilters.subscription && m.billing_kind === 'subscription';
        const okApi = capFilters.apiKey && m.billing_kind === 'api_key';
        if (!okSub && !okApi) return false;
      }
      if (minCtx > 0 && (m.context_window ?? 0) < minCtx) return false;
      if (maxCost !== Infinity) {
        if (maxCost === 0) {
          if (m.billing_kind !== 'free' && m.billing_kind !== 'subscription') return false;
        } else if ((m.billing_kind === 'paid' || m.billing_kind === 'api_key') && (m.output_cost_per_1m ?? 0) > maxCost) {
          return false;
        }
      }
      return true;
    };
    if (!q && !anyFilterActive) return allModelOptions.grouped;
    const out: Record<string, Array<any>> = {};
    for (const [prov, models] of Object.entries(allModelOptions.grouped)) {
      const provLower = prov.toLowerCase();
      const matches = (models as any[]).filter((m) => {
        const qMatch = !q || m.label.toLowerCase().includes(q) || m.value.toLowerCase().includes(q) || provLower.includes(q);
        return qMatch && filterFn(m);
      });
      if (matches.length) out[prov] = matches;
    }
    return out;
  }, [allModelOptions.grouped, anyFilterActive, capFilters, costIdx, ctxIdx, modelSearch]);

  const pickerSummary = useMemo(() => {
    let total = 0; let free = 0; let reasoning = 0; let subscription = 0; let apiKey = 0; let paid = 0; let longContext = 0;
    for (const ms of Object.values(filteredModelGroups)) {
      for (const m of ms as any[]) {
        total += 1;
        if (m.reasoning) reasoning += 1;
        if ((m.context_window ?? 0) >= 1_000_000) longContext += 1;
        if (m.billing_kind === 'free') free += 1;
        else if (m.billing_kind === 'subscription') subscription += 1;
        else if (m.billing_kind === 'api_key') apiKey += 1;
        else if (m.billing_kind === 'paid') paid += 1;
      }
    }
    return { total, free, reasoning, subscription, apiKey, paid, longContext };
  }, [filteredModelGroups]);

  const recentMaterialised = useMemo(() => {
    const flatByValue = new Map(allModelOptions.flat.map((m) => [m.value, m]));
    return recentModels.map((v) => flatByValue.get(v)).filter(Boolean) as typeof allModelOptions.flat;
  }, [allModelOptions.flat, recentModels]);

  const compareOptions = useMemo(() => {
    const flatByValue = new Map(allModelOptions.flat.map((m) => [m.value, m]));
    return compareValues.map((v) => flatByValue.get(v)).filter(Boolean) as typeof allModelOptions.flat;
  }, [allModelOptions.flat, compareValues]);

  const compareModelCount = Math.max(2, Math.min(4, compareOptions.length || 2));
  const compareCardWidth = 350;
  const compareDialogWidth = Math.min(1580, compareModelCount * compareCardWidth + 96);

  const showRecents = !modelSearch.trim()
    && !capFilters.reasoning && !capFilters.subscription && !capFilters.apiKey
    && ctxIdx === 0 && costIdx === 0
    && recentMaterialised.length > 0;

  const selectedLabel = allModelOptions.flat.find((m) => m.value === model)?.label || model;
  const [probeResult, setProbeResult] = useState<{ value: string; ok: boolean; error?: string; latency_ms?: number } | null>(null);

  const toggleCompareValue = useCallback((value: string) => {
    setCompareValues((prev) => {
      if (prev.includes(value)) return prev.filter((v) => v !== value);
      if (prev.length >= 4) return prev;
      return [...prev, value];
    });
  }, []);

  useEffect(() => {
    if (!model) return;
    let cancelled = false;
    const t = setTimeout(async () => {
      try {
        const res = await fetch(`${API_BASE}/agents/probe-model`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ model }),
        });
        if (cancelled) return;
        const data = await res.json();
        setProbeResult({ value: model, ok: !!data.ok, error: data.error, latency_ms: data.latency_ms });
      } catch {
        // Non-blocking: send will surface real provider errors.
      }
    }, 350);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [model]);

  const contextDisplayRows = (m: any) => {
    const formatContext = (value: unknown) => {
      const numeric = Number(value || 0);
      return numeric > 0 ? numeric.toLocaleString() : 'No data';
    };

    return [
      {
        label: 'Configured context',
        value: formatContext(m.configured_context_window),
        source: m.configured_context_source || 'No data',
        visible: Boolean(m.configured_context_window || m.configured_context_source),
      },
      {
        label: 'Declared context',
        value: formatContext(m.declared_context_window),
        source: m.declared_context_source || 'No data',
        visible: Boolean(m.declared_context_window || m.declared_context_source),
      },
      {
        label: 'Loaded context',
        value: formatContext(m.loaded_context_window),
        source: m.loaded_context_source || 'No data',
        visible: Boolean(m.loaded_context_window || m.loaded_context_source),
      },
      {
        label: 'Estimated context',
        value: formatContext(m.estimated_context_window || (m.context_window_source === 'estimated' ? m.context_window : null)),
        source: m.estimated_context_source || (m.context_window_source === 'estimated' ? 'OpenSwarm estimate' : 'No data'),
        visible: Boolean(m.estimated_context_window || m.context_window_source === 'estimated'),
      },
    ].filter((row) => row.visible);
  };

  const primaryContextLabel = (m: any) => {
    if (m.configured_context_window) return 'Configured context';
    if (m.declared_context_window) return 'Declared context';
    if (m.loaded_context_window) return 'Loaded context';
    if (m.context_window_source === 'estimated') return 'Estimated context';
    return 'Context';
  };

  const buildModelTooltip = useCallback((opt: any): React.ReactNode => {
    const [intel, speed, cost] = (Array.isArray(opt.tiers) && opt.tiers.length === 3)
      ? opt.tiers
      : [tierIntelligence(opt), tierSpeed(opt), tierCost(opt)];

    const billingKind: 'paid' | 'subscription' | 'free' =
      opt.billing_kind || (opt.is_free ? 'free' : 'paid');

    const Bars = ({ filled, palette }: { filled: number; palette: string[] }) => {
      const TOTAL_CELLS = 20;
      const filledCells = Math.max(0, Math.min(TOTAL_CELLS, Math.round((filled / 5) * TOTAL_CELLS)));

      return (
        <Box sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.75 }}>
          <Box sx={{ display: 'inline-flex', alignItems: 'center' }}>
            {Array.from({ length: TOTAL_CELLS }, (_, i) => {
              const on = i < filledCells;
              const colorIdx = on
                ? Math.min(
                    palette.length - 1,
                    Math.floor((i / Math.max(TOTAL_CELLS - 1, 1)) * (palette.length - 1)),
                  )
                : 0;
              const temperature = on ? 0.55 + ((i + 1) / TOTAL_CELLS) * 0.45 : 0.28;

              return (
                <Box
                  key={i}
                  sx={{
                    width: 5,
                    height: 5,
                    ml: i > 0 && i % 4 === 0 ? '4px' : '1px',
                    bgcolor: on ? palette[colorIdx] : c.border.subtle,
                    opacity: temperature,
                    boxShadow: on
                      ? `0 0 ${2 + Math.round(((i + 1) / TOTAL_CELLS) * 5)}px ${palette[colorIdx]}66`
                      : 'none',
                    transformOrigin: 'center',
                    animation: on
                      ? `pixelPop 0.58s cubic-bezier(0.22, 1, 0.36, 1) ${i * 0.045}s both, barHeatSweep 2.35s linear ${i * 0.075}s infinite`
                      : 'none',
                    '@keyframes pixelPop': {
                      '0%': { transform: 'scale(0)', opacity: 0 },
                      '60%': { transform: 'scale(1.2)', opacity: 1 },
                      '100%': { transform: 'scale(1)', opacity: temperature },
                    },
                    '@keyframes barHeatSweep': {
                      '0%': {
                        filter: 'brightness(1)',
                        transform: 'scale(1)',
                      },
                      '10%': {
                        filter: 'brightness(1.65)',
                        transform: 'scale(1.16)',
                      },
                      '20%': {
                        filter: 'brightness(1.08)',
                        transform: 'scale(1)',
                      },
                      '100%': {
                        filter: 'brightness(1)',
                        transform: 'scale(1)',
                      },
                    },
                  }}
                />
              );
            })}
          </Box>
          <Box
            component="span"
            sx={{
              minWidth: 18,
              color: c.text.ghost,
              fontSize: '0.68rem',
              fontVariantNumeric: 'tabular-nums',
              fontWeight: 700,
              lineHeight: 1,
            }}
          >
            {filledCells}
          </Box>
        </Box>
      );
    };

    const INTEL_PALETTE = ['#6D5BBE', '#8870D5', '#A78BFA', '#BFA3FF', '#D5BFFF'];
    const SPEED_PALETTE = ['#2DBFAA', '#42D6BF', '#5EEAD4', '#7FF1DF', '#A3F7E9'];
    const COST_PALETTE = ['#C7752E', '#DD8A3D', '#F59E0B', '#FAB23C', '#FCC773'];

    const capabilities = [
      ...modelCapabilityChips(opt),
      billingKind === 'free' && 'Free tier',
      billingKind === 'subscription' && 'Subscription',
      (opt.context_window ?? 0) >= 1_000_000 && '1M+ context',
    ].filter(Boolean).join(' ? ');

    const capabilitySources = opt.capability_source
      ? Object.entries(opt.capability_source).slice(0, 5).map(([k, v]) => `${k}: ${sourceLabel(String(v))}`).join(' ? ')
      : '';

    return (
      <Box sx={{ fontSize: '0.74rem', lineHeight: 1.55, minWidth: 256 }}>
        <Box
          sx={{
            fontWeight: 600,
            fontSize: '0.85rem',
            mb: 0.85,
            color: c.text.primary,
            letterSpacing: '-0.01em',
            pb: 0.6,
            borderBottom: `1px solid ${c.border.subtle}`,
          }}
        >
          {opt.label}
        </Box>

        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: 'auto 1fr',
            columnGap: 1.75,
            rowGap: 0.5,
            alignItems: 'center',
            color: c.text.muted,
          }}
        >
          <span>Intelligence</span>
          <Bars filled={intel} palette={INTEL_PALETTE} />

          <span>Speed</span>
          <Bars filled={speed} palette={SPEED_PALETTE} />

          {billingKind === 'subscription' ? null : (
            <>
              <span>Cost</span>
              {billingKind === 'free' ? (
                <Box component="span" sx={{ color: '#10b981', fontWeight: 600 }}>
                  Free
                </Box>
              ) : (
                <Bars filled={cost} palette={COST_PALETTE} />
              )}
            </>
          )}

          {contextDisplayRows(opt).map((row) => (
            <React.Fragment key={row.label}>
              <span>{row.label}</span>
              <span style={{ fontVariantNumeric: 'tabular-nums', color: c.text.secondary }}>
                {row.value}
              </span>
            </React.Fragment>
          ))}

          {billingKind === 'paid' && (opt.input_cost_per_1m || opt.output_cost_per_1m) ? (
            <>
              <span>Pricing</span>
              <span style={{ fontVariantNumeric: 'tabular-nums', color: c.text.secondary }}>
                ${opt.input_cost_per_1m?.toFixed(2)}/M in · ${opt.output_cost_per_1m?.toFixed(2)}/M out
              </span>
            </>
          ) : null}

          {capabilities && (
            <>
              <span>Capabilities</span>
              <span style={{ color: c.text.secondary }}>{capabilities}</span>
            </>
          )}
          {capabilitySources && (
            <>
              <span>Sources</span>
              <span style={{ color: c.text.secondary }}>{capabilitySources}</span>
            </>
          )}
        </Box>
      </Box>
    );
  }, [c]);

  const tooltipSlotProps = useMemo(() => ({
    tooltip: {
      sx: {
        bgcolor: c.bg.elevated,
        color: c.text.primary,
        border: `1px solid ${c.border.subtle}`,
        borderRadius: `${c.radius.md}px`,
        boxShadow: '0 12px 32px rgba(0, 0, 0, 0.32)',
        padding: '12px 14px',
        maxWidth: 340,
        fontSize: '0.78rem',
        fontFamily: c.font.sans,
      },
    },
    arrow: {
      sx: {
        color: c.bg.elevated,
        '&:before': { border: `1px solid ${c.border.subtle}` },
      },
    },
  }), [c]);

  const chooseModel = useCallback((value: string, providerName?: string) => {
    onModelChange(value);
    pushRecentModel(value);
    if (modelSearch.trim()) pushRecentSearch(modelSearch);
    if (onProviderChange && providerName) {
      const provLower = providerName.toLowerCase();
      const providerMap: Record<string, string> = {
        anthropic: 'anthropic',
        'openswarm pro': 'anthropic',
        openai: 'openai',
        google: 'gemini',
      };
      onProviderChange(providerMap[provLower] || (provLower.startsWith('openrouter') ? 'openrouter' : provLower));
    }
    setModelAnchor(null);
  }, [modelSearch, onModelChange, onProviderChange, pushRecentModel, pushRecentSearch]);

  const highlightMatch = useCallback((text: string): React.ReactNode => {
    const q = modelSearch.trim();
    if (!q) return text;
    const idx = text.toLowerCase().indexOf(q.toLowerCase());
    if (idx < 0) return text;
    return (
      <>
        {text.slice(0, idx)}
        <Box component="span" sx={{ fontWeight: 700, color: c.text.primary }}>
          {text.slice(idx, idx + q.length)}
        </Box>
        {text.slice(idx + q.length)}
      </>
    );
  }, [c.text.primary, modelSearch]);

  const compareMetricTiers = (m: any): [number, number, number] => (
    Array.isArray(m.tiers) && m.tiers.length === 3
      ? m.tiers
      : [tierIntelligence(m), tierSpeed(m), tierCost(m)]
  );

  const compareContextScore = (m: any): number => {
    const context = Number(m.context_window || 0);
    if (context >= 1_000_000) return 5;
    if (context >= 256_000) return 4;
    if (context >= 128_000) return 3;
    if (context >= 32_000) return 2;
    if (context > 0) return 1;
    return 0;
  };

  const compareCapabilityValue = (m: any, capability: 'tools' | 'multimodal' | 'image' | 'video') => {
    if (capability === 'tools' && m.supports_tools) return { label: sourceLabel(m.capability_source?.tools) };
    if (capability === 'multimodal' && m.supports_vision) return { label: sourceLabel(m.capability_source?.vision) };
    if (capability === 'image') return { label: 'None' };
    if (capability === 'video') return { label: 'None' };
    return { label: 'No measured data' };
  };

  const renderCompareBars = (filled: number, palette: string[], label: string) => {
    const TOTAL_CELLS = 20;
    const filledCells = Math.max(0, Math.min(TOTAL_CELLS, Math.round((filled / 5) * TOTAL_CELLS)));

    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, minWidth: 116 }}>
        <Box sx={{ display: 'inline-flex', alignItems: 'center' }}>
          {Array.from({ length: TOTAL_CELLS }, (_, i) => {
            const on = i < filledCells;
            const colorIdx = on
              ? Math.min(
                  palette.length - 1,
                  Math.floor((i / Math.max(TOTAL_CELLS - 1, 1)) * (palette.length - 1)),
                )
              : 0;
            const temperature = on ? 0.55 + ((i + 1) / TOTAL_CELLS) * 0.45 : 0.28;

            return (
              <Box
                key={i}
                sx={{
                  width: 4,
                  height: 4,
                  ml: i > 0 && i % 4 === 0 ? '4px' : '1px',
                  bgcolor: on ? palette[colorIdx] : c.border.subtle,
                  opacity: temperature,
                  boxShadow: on ? `0 0 ${2 + Math.round(((i + 1) / TOTAL_CELLS) * 4)}px ${palette[colorIdx]}55` : 'none',
                }}
              />
            );
          })}
        </Box>
        <Box component="span" sx={{ minWidth: 18, color: c.text.ghost, fontSize: '0.66rem', fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>
          {filledCells}
        </Box>
        <Box component="span" sx={{ color: c.text.tertiary, fontSize: '0.64rem', whiteSpace: 'nowrap' }}>
          {label}
        </Box>
      </Box>
    );
  };

  const renderCapabilityText = (value: { label: string }) => (
    <Box
      component="span"
      sx={{
        color: value.label === 'No measured data' || value.label === 'None' ? c.text.ghost : c.text.secondary,
        fontSize: '0.68rem',
        fontWeight: 700,
        lineHeight: 1.15,
      }}
    >
      {value.label}
    </Box>
  );

  const renderModelComparisonHeader = (m: any) => {
    const [intel, speed] = compareMetricTiers(m);
    const contextValue = Number(m.context_window || 0);
    const tools = compareCapabilityValue(m, 'tools');
    const multimodal = compareCapabilityValue(m, 'multimodal');
    const image = compareCapabilityValue(m, 'image');
    const video = compareCapabilityValue(m, 'video');
    const INTEL_PALETTE = ['#6D5BBE', '#8870D5', '#A78BFA', '#BFA3FF', '#D5BFFF'];
    const SPEED_PALETTE = ['#2DBFAA', '#42D6BF', '#5EEAD4', '#7FF1DF', '#A3F7E9'];

    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.45, minWidth: 230 }}>
        <Box sx={{ color: c.text.primary, fontWeight: 800, fontSize: '0.78rem', lineHeight: 1.2 }}>
          {m.label}
        </Box>
        <Box sx={{ display: 'grid', gridTemplateColumns: '92px 1fr', gap: 0.35, alignItems: 'center' }}>
          <Box sx={{ color: c.text.tertiary, fontSize: '0.65rem', fontWeight: 700 }}>
            {m.tiers_source === 'estimated' ? 'Estimated intelligence' : 'Intelligence'}
          </Box>
          {renderCompareBars(intel, INTEL_PALETTE, sourceLabel(m.tiers_source))}
          <Box sx={{ color: c.text.tertiary, fontSize: '0.65rem', fontWeight: 700 }}>
            {m.tiers_source === 'estimated' ? 'Estimated speed' : 'Speed'}
          </Box>
          {renderCompareBars(speed, SPEED_PALETTE, sourceLabel(m.tiers_source))}
          <Box sx={{ color: c.text.tertiary, fontSize: '0.65rem', fontWeight: 700 }}>
            {primaryContextLabel(m)}
          </Box>
          <Box component="span" sx={{ color: c.text.secondary, fontSize: '0.68rem', fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>
            {contextValue > 0 ? contextValue.toLocaleString() : 'None'}
          </Box>
          <Box sx={{ color: c.text.tertiary, fontSize: '0.65rem', fontWeight: 700 }}>Tool use</Box>
          {renderCapabilityText(tools)}
          <Box sx={{ color: c.text.tertiary, fontSize: '0.65rem', fontWeight: 700 }}>Multimodal</Box>
          {renderCapabilityText(multimodal)}
          <Box sx={{ color: c.text.tertiary, fontSize: '0.65rem', fontWeight: 700 }}>Image generation</Box>
          {renderCapabilityText(image)}
          <Box sx={{ color: c.text.tertiary, fontSize: '0.65rem', fontWeight: 700 }}>Video generation</Box>
          {renderCapabilityText(video)}
        </Box>
      </Box>
    );
  };

  const compareColumns = [
    ['model', (m: any) => m.local_model_name || m.name || m.label],
    ['provider', (m: any) => m.provider || 'No data'],
    ['family', (m: any) => m.family || 'No data'],
    ['parameters', (m: any) => m.parameter_size || 'No data'],
    ['quantization', (m: any) => m.quantization_level || 'No data'],
    ['format', (m: any) => m.format || 'No data'],
    ['size', (m: any) => formatBytes(m.size_bytes) || 'No data'],
    ['modified', (m: any) => formatDate(m.modified_at)],
    ['cost', (m: any) => m.billing_kind === 'free' ? 'Free / Local' : (m.billing_kind || 'No data')],
    ['availability', (m: any) => m.availability === 'available' ? 'Available' : 'No data'],
    ['configured/context', (m: any) => m.configured_context_window ? `${Number(m.configured_context_window).toLocaleString()} (${m.configured_context_source || 'No source'})` : 'No data'],
    ['declared/context', (m: any) => m.declared_context_window ? `${Number(m.declared_context_window).toLocaleString()} (${m.declared_context_source || 'No source'})` : 'No data'],
    ['loaded/context', (m: any) => m.loaded_context_window ? `${Number(m.loaded_context_window).toLocaleString()} (${m.loaded_context_source || 'No source'})` : 'No data'],
    ['estimated/context', (m: any) => m.estimated_context_window ? `${Number(m.estimated_context_window).toLocaleString()} (${m.estimated_context_source || 'No source'})` : 'No data'],
    ['reasoning/source', (m: any) => `${m.reasoning ? 'Yes' : 'No'} (${sourceLabel(m.reasoning_source)})`],
    ['tool use', (m: any) => m.supports_tools ? `Yes (${sourceLabel(m.capability_source?.tools)})` : 'No data'],
    ['vision', (m: any) => m.supports_vision ? `Yes (${sourceLabel(m.capability_source?.vision)})` : 'No data'],
    ['embeddings', (m: any) => m.supports_embedding ? `Yes (${sourceLabel(m.capability_source?.embedding)})` : 'No data'],
    ['json', (m: any) => m.supports_json ? `Yes (${sourceLabel(m.capability_source?.json)})` : 'No data'],
    ['residency', (m: any) => m.running ? `Running${m.expires_at ? ` until ${formatDate(m.expires_at)}` : ''}` : (m.loaded ? 'Loaded' : 'No data')],
    ['runtime metrics', (m: any) => m.runtime_metrics ? 'Available' : 'No data'],
    ['eval results', (m: any) => m.eval_results ? 'Available' : 'No data'],
  ] as const;

  const compareFieldLabel = (key: string): string => {
    const labels: Record<string, string> = {
      provider: 'Provider',
      family: 'Family',
      parameters: 'Parameters',
      quantization: 'Quantization',
      format: 'Format',
      size: 'Disk size',
      modified: 'Modified',
      cost: 'Cost',
      availability: 'Availability',
      'configured/context': 'Configured context',
      'declared/context': 'Declared context',
      'loaded/context': 'Loaded context',
      'estimated/context': 'Estimated context',
      'reasoning/source': 'Reasoning',
      'tool use': 'Tool use',
      vision: 'Vision',
      embeddings: 'Embeddings',
      json: 'JSON',
      residency: 'Residency',
      'runtime metrics': 'Runtime metrics',
      'eval results': 'Eval results',
    };
    return labels[key] || key;
  };

  const compareCardColumns = compareColumns.filter(([key]: any) => key !== 'model');

  const renderModelComparisonCards = () => (
    <Box
      sx={{
        display: 'grid',
        gridTemplateColumns: `repeat(${compareOptions.length}, ${compareCardWidth}px)`,
        gap: 1.5,
        alignItems: 'stretch',
        width: 'max-content',
      }}
    >
      {compareOptions.map((opt: any) => (
        <Box
          key={opt.value}
          sx={{
            width: `${compareCardWidth}px`,
            border: `1px solid ${c.border.subtle}`,
            borderRadius: '16px',
            bgcolor: 'rgba(255,255,255,0.02)',
            overflow: 'hidden',
            boxShadow: '0 10px 30px rgba(0,0,0,0.14)',
          }}
        >
          <Box
            sx={{
              px: 1.5,
              py: 1.35,
              borderBottom: `1px solid ${c.border.subtle}`,
              background: 'linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01))',
            }}
          >
            {renderModelComparisonHeader(opt)}
          </Box>

          <Box sx={{ px: 1.5, py: 1.2, display: 'flex', flexDirection: 'column', gap: 1.15 }}>
            <Box
              sx={{
                color: c.text.ghost,
                fontSize: '0.64rem',
                fontWeight: 800,
                letterSpacing: '0.08em',
                textTransform: 'uppercase',
              }}
            >
              Real metadata
            </Box>

            <Box
              sx={{
                display: 'grid',
                gridTemplateColumns: '120px 1fr',
                columnGap: 1.15,
                rowGap: 0.72,
                alignItems: 'start',
              }}
            >
              {compareCardColumns.map(([key, getValue]: any) => (
                <React.Fragment key={`${opt.value}-${key}`}>
                  <Box
                    sx={{
                      color: c.text.tertiary,
                      fontSize: '0.68rem',
                      fontWeight: 700,
                      lineHeight: 1.25,
                    }}
                  >
                    {compareFieldLabel(key)}
                  </Box>
                  <Box
                    sx={{
                      color: c.text.secondary,
                      fontSize: '0.73rem',
                      lineHeight: 1.3,
                      wordBreak: 'break-word',
                    }}
                  >
                    {getValue(opt)}
                  </Box>
                </React.Fragment>
              ))}
            </Box>
          </Box>
        </Box>
      ))}
    </Box>
  );

  return (
    <>
      <Box
        onClick={(e) => !disabled && setModelAnchor(e.currentTarget)}
        sx={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 0.25,
          px: 0.75,
          py: 0.25,
          maxWidth: compact ? 220 : undefined,
          borderRadius: '6px',
          cursor: disabled ? 'default' : 'pointer',
          userSelect: 'none',
          color: disabled ? c.text.ghost : c.text.muted,
          '&:hover': disabled ? undefined : { bgcolor: 'rgba(0,0,0,0.04)' },
          transition: 'background 0.15s',
        }}
      >
        <Typography sx={{ fontSize: compact ? '0.76rem' : '0.82rem', fontWeight: 500, color: 'inherit', lineHeight: 1 }} noWrap>
          {selectedLabel}
        </Typography>
        <KeyboardArrowDownIcon sx={{ fontSize: 14, color: 'inherit', opacity: 0.7 }} />
      </Box>

      <Menu
        anchorEl={modelAnchor}
        open={Boolean(modelAnchor)}
        onClose={() => setModelAnchor(null)}
        anchorOrigin={{ vertical: 'top', horizontal: 'left' }}
        transformOrigin={{ vertical: 'bottom', horizontal: 'left' }}
        slotProps={{
          paper: {
            sx: {
              width: 380,
              maxHeight: 560,
              bgcolor: c.bg.surface,
              border: `1px solid ${c.border.subtle}`,
              boxShadow: c.shadow.lg,
              overflow: 'auto',
            },
          },
        }}
        MenuListProps={{
          autoFocusItem: false,
          onKeyDown: (e: React.KeyboardEvent) => {
            if (compareMode && e.key === 'Enter' && compareOptions.length >= 2) {
              e.preventDefault();
              setCompareOpen(true);
            }
          },
        }}
        disableAutoFocusItem
      >
        <Box onClick={(e) => e.stopPropagation()} sx={{ position: 'sticky', top: 0, zIndex: 2, bgcolor: c.bg.surface, borderBottom: `1px solid ${c.border.subtle}` }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, px: 1.25, py: 1 }}>
            <SearchIcon sx={{ fontSize: 16, color: c.text.ghost }} />
            <InputBase
              inputRef={modelSearchRef}
              value={modelSearch}
              onChange={(e) => setModelSearch(e.target.value)}
              placeholder="Search models..."
              sx={{ flex: 1, fontSize: '0.82rem', color: c.text.primary }}
            />
            <Box
              onClick={() => setCompareMode((prev) => !prev)}
              sx={{
                px: 0.75,
                py: 0.25,
                borderRadius: 999,
                border: `1px solid ${compareMode ? c.accent.primary : c.border.subtle}`,
                bgcolor: compareMode ? `${c.accent.primary}16` : 'transparent',
                color: compareMode ? c.accent.primary : c.text.tertiary,
                fontSize: '0.66rem',
                fontWeight: 800,
                cursor: 'pointer',
              }}
            >
              {compareMode ? `Model Compare ${compareValues.length}` : 'Model Compare'}
            </Box>
          </Box>
          {!modelSearch.trim() && recentSearches.length > 0 && (
            <Box sx={{ display: 'flex', gap: 0.5, px: 1.25, pb: 0.75, flexWrap: 'wrap' }}>
              {recentSearches.slice(0, RECENT_SEARCHES_MAX).map((q) => (
                <Box
                  key={q}
                  onClick={() => setModelSearch(q)}
                  sx={{ px: 0.75, py: 0.25, borderRadius: 999, border: `1px solid ${c.border.subtle}`, color: c.text.tertiary, fontSize: '0.66rem', cursor: 'pointer' }}
                >
                  {q}
                </Box>
              ))}
            </Box>
          )}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, px: 1.25, pb: 0.75, flexWrap: 'wrap' }}>
            {([
              ['Reasoning', 'reasoning'],
              ['Subscription', 'subscription'],
              ['API key', 'apiKey'],
            ] as const).map(([label, key]) => {
              const active = capFilters[key];
              return (
                <Box
                  key={key}
                  onClick={() => setCapFilters((prev) => ({ ...prev, [key]: !prev[key] }))}
                  sx={{
                    cursor: 'pointer',
                    px: 0.75,
                    py: 0.25,
                    borderRadius: 999,
                    border: `1px solid ${active ? c.accent.primary : c.border.subtle}`,
                    bgcolor: active ? `${c.accent.primary}12` : 'transparent',
                    color: active ? c.accent.primary : c.text.tertiary,
                    fontSize: '0.66rem',
                    fontWeight: 600,
                  }}
                >
                  {label}
                </Box>
              );
            })}
            <Box onClick={toggleFilters} sx={{ ml: 'auto', cursor: 'pointer', color: anyFilterActive ? c.accent.primary : c.text.tertiary, fontSize: '0.66rem', fontWeight: 650 }}>
              Filters {filtersExpanded ? '−' : '+'}
            </Box>
            {anyFilterActive && (
              <Box
                onClick={() => {
                  setCapFilters({ reasoning: false, subscription: false, apiKey: false });
                  setCtxIdx(0);
                  setCostIdx(0);
                }}
                sx={{ cursor: 'pointer', color: c.text.ghost, fontSize: '0.66rem', fontWeight: 600 }}
              >
                Reset
              </Box>
            )}
          </Box>
          <Collapse in={filtersExpanded} timeout={180} unmountOnExit>
            <Box sx={{ px: 1.5, pb: 0.75, display: 'flex', flexDirection: 'column', gap: 0.25 }}>
              {([
                { label: 'Min context', idx: ctxIdx, set: setCtxIdx, max: CTX_STEPS.length - 1, valueLabel: CTX_LABELS[ctxIdx] },
                { label: 'Max cost', idx: costIdx, set: setCostIdx, max: COST_STEPS.length - 1, valueLabel: COST_LABELS[costIdx] },
              ] as const).map((row) => (
                <Box key={row.label} sx={{ display: 'grid', gridTemplateColumns: '78px 1fr 64px', alignItems: 'center', gap: 0.75, height: 24 }}>
                  <Box sx={{ color: c.text.tertiary, fontSize: '0.65rem', fontWeight: 500 }}>{row.label}</Box>
                  <Slider
                    size="small"
                    value={row.idx}
                    onChange={(_, v) => row.set(v as number)}
                    step={1}
                    min={0}
                    max={row.max}
                    marks
                    sx={{
                      color: c.accent.primary,
                      height: 3,
                      py: 1,
                      '& .MuiSlider-thumb': { width: 10, height: 10, '&:before': { boxShadow: 'none' } },
                      '& .MuiSlider-mark': { width: 2, height: 2, borderRadius: '50%', bgcolor: c.text.ghost, opacity: 0.6 },
                      '& .MuiSlider-markActive': { opacity: 0 },
                    }}
                  />
                  <Box sx={{ color: row.idx > 0 ? c.accent.primary : c.text.ghost, fontSize: '0.65rem', fontWeight: 600, textAlign: 'right' }}>
                    {row.valueLabel}
                  </Box>
                </Box>
              ))}
            </Box>
          </Collapse>
        </Box>

        {probeResult && probeResult.value === model && !probeResult.ok && (
          <Tooltip title={probeResult.error || 'health check failed'} placement="bottom-start" enterDelay={400}>
            <Box
              onClick={(e) => e.stopPropagation()}
              sx={{
                mx: 1, my: 0.5,
                px: 1, height: 26,
                display: 'flex', alignItems: 'center', gap: 0.5,
                borderRadius: '6px',
                bgcolor: 'rgba(239, 68, 68, 0.08)',
                color: '#ef4444',
                fontSize: '0.72rem', fontWeight: 500,
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                opacity: 0.85,
              }}
            >
              ? {probeResult.error || 'this model failed its health check'}
            </Box>
          </Tooltip>
        )}

        {showRecents && (
          <>
            <MenuItem onClick={(e) => { e.stopPropagation(); toggleGroupCollapse('Recent', !!collapsedGroups.Recent); }} sx={{ py: 0.75, px: 1.5 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, width: '100%' }}>
                <KeyboardArrowRightIcon sx={{ fontSize: 14, color: c.text.tertiary, transform: collapsedGroups.Recent ? 'none' : 'rotate(90deg)' }} />
                <AccessTimeIcon sx={{ fontSize: 12, color: c.text.tertiary }} />
                <Typography sx={{ fontSize: '0.7rem', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: c.text.tertiary, flex: 1 }}>
                  Recent
                </Typography>
                <Typography sx={{ fontSize: '0.65rem', color: c.text.ghost, fontWeight: 500 }}>{recentMaterialised.length}</Typography>
              </Box>
            </MenuItem>
            <Collapse in={!collapsedGroups.Recent} timeout={180} unmountOnExit>
              {recentMaterialised.map((opt: any) => (
                <Tooltip key={`recent-${opt.value}`} title={buildModelTooltip(opt)} placement="right" enterDelay={300} slotProps={tooltipSlotProps}>
                  <MenuItem selected={model === opt.value} onClick={() => chooseModel(opt.value, opt.provider)}>
                    <ListItemText primary={opt.label} slotProps={{ primary: { sx: { fontSize: '0.8rem', color: model === opt.value ? c.text.primary : c.text.muted } } }} />
                    {modelCapabilityChips(opt).slice(0, 3).map((chip) => (
                      <Box key={chip} sx={{ ml: 0.45, px: 0.5, py: 0.12, borderRadius: 999, border: `1px solid ${c.border.subtle}`, color: c.text.tertiary, fontSize: '0.56rem', fontWeight: 800 }}>
                        {chip}
                      </Box>
                    ))}
                    {compareMode && (
                      <Box
                        onClick={(e) => { e.stopPropagation(); toggleCompareValue(opt.value); }}
                        sx={{
                          ml: 1,
                          px: 0.65,
                          py: 0.15,
                          borderRadius: 999,
                          border: `1px solid ${compareValues.includes(opt.value) ? c.accent.primary : c.border.subtle}`,
                          color: compareValues.includes(opt.value) ? c.accent.primary : c.text.ghost,
                          fontSize: '0.62rem',
                          fontWeight: 800,
                          minWidth: 42,
                          textAlign: 'center',
                        }}
                      >
                        {compareValues.includes(opt.value) ? 'Added' : 'Add'}
                      </Box>
                    )}
                  </MenuItem>
                </Tooltip>
              ))}
            </Collapse>
          </>
        )}

        {Object.keys(filteredModelGroups).length === 0 && (
          <Box sx={{ px: 2, py: 1.5, fontSize: '0.8rem', color: c.text.ghost, textAlign: 'center', fontStyle: 'italic' }}>
            {modelSearch.trim() ? <>No models match "{modelSearch.trim()}".</> : <>No models match the current filters.</>}
          </Box>
        )}

        {Object.entries(filteredModelGroups).map(([prov, models]) => {
          const isOR = prov.startsWith('OpenRouter');
          const ms = models as any[];
          const searchActive = modelSearch.trim().length > 0;
          const userToggle = collapsedGroups[prov];
          const autoCollapse = isOR && !searchActive && ms.length > OR_AUTO_COLLAPSE_THRESHOLD;
          const collapsed = userToggle !== undefined ? userToggle : autoCollapse;
          const brandKey = isOR ? 'openrouter' : prov.toLowerCase().split(/\s+/)[0];
          const brandColor = PROVIDER_COLORS[brandKey] ?? c.text.tertiary;

          return [
            <MenuItem key={`header-${prov}`} onClick={(e) => { e.stopPropagation(); toggleGroupCollapse(prov, collapsed); }} sx={{ py: 0.75, px: 1.5 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, width: '100%' }}>
                <KeyboardArrowRightIcon sx={{ fontSize: 14, color: c.text.tertiary, transform: collapsed ? 'none' : 'rotate(90deg)' }} />
                <Box sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: brandColor, boxShadow: `0 0 6px ${brandColor}80`, flexShrink: 0 }} />
                <Typography sx={{ color: brandColor, fontSize: '0.7rem', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', flex: 1 }}>
                  {prov}
                </Typography>
                <Typography sx={{ fontSize: '0.65rem', color: c.text.ghost, fontWeight: 500 }}>{ms.length}</Typography>
              </Box>
            </MenuItem>,
            <Collapse key={`coll-${prov}`} in={!collapsed} timeout={180} unmountOnExit>
              {ms.map((opt: any) => {
                let displayLabel = opt.label;
                if (isOR && displayLabel.includes(': ')) {
                  const groupVendor = prov.replace(/^OpenRouter\s*[·•]\s*/i, '').toLowerCase();
                  const colonIdx = displayLabel.indexOf(': ');
                  const labelPrefix = displayLabel.slice(0, colonIdx).toLowerCase();
                  if (labelPrefix === groupVendor) displayLabel = displayLabel.slice(colonIdx + 2);
                }
                return (
                  <Tooltip key={opt.value} title={buildModelTooltip(opt)} placement="right" enterDelay={300} slotProps={tooltipSlotProps}>
                    <MenuItem selected={model === opt.value} onClick={() => chooseModel(opt.value, prov)}>
                      <ListItemText primary={highlightMatch(displayLabel)} slotProps={{ primary: { sx: { fontSize: '0.8rem', color: model === opt.value ? c.text.primary : c.text.muted } } }} />
                      {modelCapabilityChips(opt).slice(0, 3).map((chip) => (
                        <Box key={chip} sx={{ ml: 0.45, px: 0.5, py: 0.12, borderRadius: 999, border: `1px solid ${c.border.subtle}`, color: c.text.tertiary, fontSize: '0.56rem', fontWeight: 800 }}>
                          {chip}
                        </Box>
                      ))}
                      {compareMode && (
                        <Box
                          onClick={(e) => { e.stopPropagation(); toggleCompareValue(opt.value); }}
                          sx={{
                            ml: 1,
                            px: 0.65,
                            py: 0.15,
                            borderRadius: 999,
                            border: `1px solid ${compareValues.includes(opt.value) ? c.accent.primary : c.border.subtle}`,
                            bgcolor: compareValues.includes(opt.value) ? `${c.accent.primary}14` : 'transparent',
                            color: compareValues.includes(opt.value) ? c.accent.primary : c.text.ghost,
                            fontSize: '0.62rem',
                            fontWeight: 800,
                          }}
                        >
                          {compareValues.includes(opt.value) ? 'Added' : 'Add'}
                        </Box>
                      )}
                    </MenuItem>
                  </Tooltip>
                );
              })}
            </Collapse>,
          ];



        }).flat()}

        <Box
          onClick={(e) => e.stopPropagation()}
          sx={{
            position: 'sticky',
            bottom: 0,
            bgcolor: c.bg.surface,
            borderTop: `1px solid ${c.border.subtle}`,
            px: 1.25,
            py: 0.5,
            fontSize: '0.65rem',
            color: c.text.ghost,
            display: 'flex',
            justifyContent: 'space-between',
            gap: 1,
          }}
        >
          <Box component="span" sx={{ flexShrink: 0, pointerEvents: 'none' }}>
            Type to search · Esc to close
          </Box>

          <Box sx={{ ml: 'auto', display: 'flex', alignItems: 'center', gap: 1.25 }}>
            <Tooltip
              title={`${pickerSummary.free} Free · ${pickerSummary.subscription} Subscription · ${pickerSummary.apiKey} API key · ${pickerSummary.reasoning} Reasoning · ${pickerSummary.longContext} 1M+ context`}
              placement="top-end"
              enterDelay={300}
              slotProps={tooltipSlotProps}
            >
              <Box component="span" sx={{ cursor: 'help', fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>
                {pickerSummary.total} model{pickerSummary.total === 1 ? '' : 's'}
              </Box>
            </Tooltip>

            {compareMode && (
              <Box
                component="span"
                onClick={() => compareOptions.length >= 2 && setCompareOpen(true)}
                sx={{
                  cursor: compareOptions.length >= 2 ? 'pointer' : 'default',
                  color: compareOptions.length >= 2 ? c.accent.primary : c.text.ghost,
                  fontWeight: 800,
                  whiteSpace: 'nowrap',
                  minWidth: 76,
                  textAlign: 'right',
                }}
              >
                Compare {compareOptions.length || 0}
              </Box>
            )}
          </Box>
        </Box>
      </Menu>

      <Dialog
        open={compareOpen}
        onClose={() => setCompareOpen(false)}
        maxWidth={false}
        PaperProps={{
          sx: {
            width: `min(${compareDialogWidth}px, 96vw)`,
            maxWidth: '96vw',
            bgcolor: c.bg.surface,
            color: c.text.primary,
            border: `1px solid ${c.border.subtle}`,
          },
        }}
      >
        <DialogTitle
          sx={{
            minHeight: 48,
            px: 2,
            py: 0,
            display: 'flex',
            alignItems: 'center',
            fontSize: '0.95rem',
            fontWeight: 800,
            borderBottom: `1px solid ${c.border.subtle}`,
          }}
        >
          Model Comparison
        </DialogTitle>
        <DialogContent sx={{ p: 0 }}>
          <Box sx={{ p: 1.5 }}>
            {compareOptions.length < 2 ? (
              <Box sx={{ p: 2, color: c.text.muted, fontSize: '0.82rem' }}>
                Select 2 to 4 models with Model Compare.
              </Box>
            ) : (
              <Box sx={{ overflowX: 'auto', overflowY: 'hidden', display: 'flex', justifyContent: 'center' }}>
                {renderModelComparisonCards()}
              </Box>
            )}
          </Box>
          <Box
            sx={{
              minHeight: 48,
              px: 2,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              borderTop: `1px solid ${c.border.subtle}`,
              color: c.text.ghost,
              fontSize: '0.72rem',
              fontWeight: 600,
            }}
          >
            <Box component="span">Model Comparison</Box>
            <Box component="span">{compareOptions.length} selected</Box>
          </Box>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default ModelPicker;
