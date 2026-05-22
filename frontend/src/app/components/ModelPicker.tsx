import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Box from '@mui/material/Box';
import Collapse from '@mui/material/Collapse';
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
  { value: 'sonnet', label: 'Claude Sonnet 4.6', context_window: 1_000_000, reasoning: true },
  { value: 'opus', label: 'Claude Opus 4.6', context_window: 1_000_000, reasoning: true },
  { value: 'haiku', label: 'Claude Haiku 4.5', context_window: 200_000, reasoning: true },
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

  useEffect(() => {
    if (modelAnchor) {
      const t = setTimeout(() => modelSearchRef.current?.focus(), 30);
      return () => clearTimeout(t);
    }
    setModelSearch('');
  }, [modelAnchor]);

  const allModelOptions = useMemo(() => {
    if (!modelsLoaded || Object.keys(modelsByProvider).length === 0) {
      const key = connectionMode === 'openswarm-pro' ? 'OpenSwarm Pro' : 'Anthropic';
      return { flat: FALLBACK_MODELS.map((m) => ({ ...m, provider: key })), grouped: { [key]: FALLBACK_MODELS } };
    }
    const flat: Array<any> = [];
    const grouped: Record<string, any[]> = {};
    for (const [prov, models] of Object.entries(modelsByProvider)) {
      const enriched = (models as any[]).map((m: any) => ({
        value: m.value,
        label: m.label,
        context_window: m.context_window ?? 200_000,
        reasoning: !!m.reasoning,
        input_cost_per_1m: m.input_cost_per_1m ?? 0,
        output_cost_per_1m: m.output_cost_per_1m ?? 0,
        is_free: !!m.is_free,
        max_completion_tokens: m.max_completion_tokens ?? null,
        tiers: Array.isArray(m.tiers) && m.tiers.length === 3 ? m.tiers : undefined,
        billing_kind: m.billing_kind,
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

  const showRecents = !modelSearch.trim()
    && !capFilters.reasoning && !capFilters.subscription && !capFilters.apiKey
    && ctxIdx === 0 && costIdx === 0
    && recentMaterialised.length > 0;

  const selectedLabel = allModelOptions.flat.find((m) => m.value === model)?.label || model;
  const [probeResult, setProbeResult] = useState<{ value: string; ok: boolean; error?: string; latency_ms?: number } | null>(null);

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

  const buildModelTooltip = useCallback((opt: any): React.ReactNode => {
    const [intel, speed, cost] = (Array.isArray(opt.tiers) && opt.tiers.length === 3)
      ? opt.tiers
      : [tierIntelligence(opt), tierSpeed(opt), tierCost(opt)];

    const billingKind: 'paid' | 'subscription' | 'free' =
      opt.billing_kind || (opt.is_free ? 'free' : 'paid');

    const Bars = ({ filled, palette }: { filled: number; palette: string[] }) => {
      const TOTAL_CELLS = 15;
      const filledCells = Math.round((filled / 5) * TOTAL_CELLS);

      return (
        <Box sx={{ display: 'inline-flex', gap: '1px', alignItems: 'center' }}>
          {Array.from({ length: TOTAL_CELLS }, (_, i) => {
            const on = i < filledCells;
            const colorIdx = on
              ? Math.min(
                  palette.length - 1,
                  Math.floor((i / Math.max(filledCells - 1, 1)) * (palette.length - 1)),
                )
              : 0;

            return (
              <Box
                key={i}
                sx={{
                  width: 5,
                  height: 5,
                  bgcolor: on ? palette[colorIdx] : c.border.subtle,
                  opacity: on ? 1 : 0.3,
                  transformOrigin: 'center',
                  animation: on
                    ? `pixelPop 0.22s cubic-bezier(0.34, 1.56, 0.64, 1) ${i * 0.018}s both`
                    : 'none',
                  '@keyframes pixelPop': {
                    '0%': { transform: 'scale(0)', opacity: 0 },
                    '60%': { transform: 'scale(1.2)', opacity: 1 },
                    '100%': { transform: 'scale(1)', opacity: 1 },
                  },
                }}
              />
            );
          })}
        </Box>
      );
    };

    const INTEL_PALETTE = ['#6D5BBE', '#8870D5', '#A78BFA', '#BFA3FF', '#D5BFFF'];
    const SPEED_PALETTE = ['#2DBFAA', '#42D6BF', '#5EEAD4', '#7FF1DF', '#A3F7E9'];
    const COST_PALETTE = ['#C7752E', '#DD8A3D', '#F59E0B', '#FAB23C', '#FCC773'];

    const capabilities = [
      opt.reasoning && 'Reasoning',
      'Tools',
      billingKind === 'free' && 'Free tier',
      billingKind === 'subscription' && 'Subscription',
      (opt.context_window ?? 0) >= 1_000_000 && '1M+ context',
    ].filter(Boolean).join(' · ');

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

          <span>Context</span>
          <span style={{ fontVariantNumeric: 'tabular-nums', color: c.text.secondary }}>
            {(opt.context_window ?? 0).toLocaleString()}
          </span>

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
        MenuListProps={{ autoFocusItem: false }}
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
        </Box>
      </Menu>
    </>
  );
};

export default ModelPicker;
