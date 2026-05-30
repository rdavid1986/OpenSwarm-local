import React, { useMemo, useState } from 'react';
import Box from '@mui/material/Box';
import Collapse from '@mui/material/Collapse';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import HourglassEmptyIcon from '@mui/icons-material/HourglassEmpty';
import PauseCircleOutlineIcon from '@mui/icons-material/PauseCircleOutline';
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import AccountTreeOutlinedIcon from '@mui/icons-material/AccountTreeOutlined';
import MemoryOutlinedIcon from '@mui/icons-material/MemoryOutlined';
import ExtensionOutlinedIcon from '@mui/icons-material/ExtensionOutlined';
import TuneOutlinedIcon from '@mui/icons-material/TuneOutlined';
import AdsClickOutlinedIcon from '@mui/icons-material/AdsClickOutlined';
import FactCheckOutlinedIcon from '@mui/icons-material/FactCheckOutlined';
import TimelineOutlinedIcon from '@mui/icons-material/TimelineOutlined';
import SpeedOutlinedIcon from '@mui/icons-material/SpeedOutlined';
import CallSplitOutlinedIcon from '@mui/icons-material/CallSplitOutlined';
import VerifiedOutlinedIcon from '@mui/icons-material/VerifiedOutlined';
import LanguageIcon from '@mui/icons-material/Language';
import SettingsSuggestOutlinedIcon from '@mui/icons-material/SettingsSuggestOutlined';
import SmartToyOutlinedIcon from '@mui/icons-material/SmartToyOutlined';
import PsychologyOutlinedIcon from '@mui/icons-material/PsychologyOutlined';
import BuildOutlinedIcon from '@mui/icons-material/BuildOutlined';
import InsertDriveFileOutlinedIcon from '@mui/icons-material/InsertDriveFileOutlined';
import LayersOutlinedIcon from '@mui/icons-material/LayersOutlined';
import HubOutlinedIcon from '@mui/icons-material/HubOutlined';
import RuleOutlinedIcon from '@mui/icons-material/RuleOutlined';
import OutputOutlinedIcon from '@mui/icons-material/OutputOutlined';

import { useClaudeTokens } from '@/shared/styles/ThemeContext';
import { buildCardVisualTokens } from './cardVisualTokens';

export type ProcessTraceStatus =
  | 'planned'
  | 'running'
  | 'completed'
  | 'failed'
  | 'blocked'
  | 'skipped'
  | 'cancelled'
  | 'warning';

export type ProcessTraceItem = {
  trace_kind?: string;
  trace_version?: string;
  trace_id?: string;
  kind?: string;
  subsystem?: string;
  title?: string;
  summary?: string;
  status?: ProcessTraceStatus | string;
  started_at?: string | null;
  finished_at?: string | null;
  duration_ms?: number | null;
  icon_id?: string;
  badge?: string;
  details?: Record<string, unknown>;
  evidence_refs?: unknown[];
  artifact_refs?: unknown[];
  related_task_id?: string;
  related_agent_id?: string;
  related_miniagent_id?: string;
  related_skill_id?: string;
  related_action_id?: string;
  created_at?: string;
  visible_to_user?: boolean;
  internal_only?: boolean;
  metadata?: Record<string, unknown>;
};

type ProcessTraceDropdownProps = {
  item: ProcessTraceItem;
  defaultExpanded?: boolean;
  compact?: boolean;
  showRawDetails?: boolean;
  bare?: boolean;
};

const STATUS_LABELS: Record<string, string> = {
  planned: 'Ready',
  running: 'Running',
  completed: 'Completed',
  failed: 'Failed',
  blocked: 'Blocked',
  skipped: 'Skipped',
  cancelled: 'Cancelled',
  warning: 'Warning',
};

const SUBSYSTEM_INITIALS: Record<string, string> = {
  SwarmCore: 'SW',
  ReasoningCore: 'RS',
  ToolCore: 'TL',
  FileCore: 'FL',
  ContextCore: 'CX',
  MemoryCore: 'ME',
  SkillCore: 'SK',
  ModeCore: 'MO',
  ActionCore: 'AC',
  EvidenceCore: 'EV',
  TraceCore: 'TR',
  MetricCore: 'MT',
  HandoffCore: 'HF',
  MiniAgentCore: 'MA',
  ValidationCore: 'VA',
  OutputCore: 'OU',
  ReviewCore: 'RV',
  BrowserCore: 'BR',
  ConfigCore: 'CF',
  ModelCore: 'MD',
};

function formatDurationMs(durationMs?: number | null): string | null {
  if (durationMs == null || Number.isNaN(durationMs)) return null;
  const safeMs = Math.max(0, Math.round(durationMs));
  const seconds = safeMs / 1000;
  if (seconds < 60) return `${seconds.toFixed(2)}s`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds - minutes * 60;
  if (minutes < 60) return `${minutes}m ${remainingSeconds.toFixed(2)}s`;
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return remainingMinutes > 0 ? `${hours}h ${remainingMinutes}m` : `${hours}h`;
}

function normalizeStatus(status?: string): ProcessTraceStatus {
  const normalized = String(status || '').toLowerCase().replace(/[\s-]+/g, '_');
  if (normalized === 'idle' || normalized === 'ready' || normalized === 'queued' || normalized === 'pending') return 'planned';
  if (normalized === 'error') return 'failed';
  if (normalized === 'waiting_approval' || normalized === 'requires_approval') return 'blocked';
  if (['planned', 'running', 'completed', 'failed', 'blocked', 'skipped', 'cancelled', 'warning'].includes(normalized)) {
    return normalized as ProcessTraceStatus;
  }
  return 'planned';
}

const REDACTED_TRACE_VALUE = '[redacted]';
const MAX_TRACE_TEXT_LENGTH = 600;

const SENSITIVE_TRACE_KEYS = new Set([
  'api_key',
  'apikey',
  'authorization',
  'bearer',
  'chain_of_thought',
  'content',
  'credential',
  'credentials',
  'cot',
  'full_prompt',
  'full_response',
  'hidden_reasoning',
  'message',
  'password',
  'private_key',
  'private_reasoning',
  'prompt',
  'raw_prompt',
  'raw_response',
  'response',
  'secret',
  'system_prompt',
  'user_prompt',
]);

function normalizeTraceKey(value: string): string {
  return String(value || '').trim().toLowerCase().replace(/[\s.-]+/g, '_');
}

function isSensitiveTraceKey(key: string): boolean {
  const normalized = normalizeTraceKey(key);
  return SENSITIVE_TRACE_KEYS.has(normalized)
    || normalized.endsWith('_secret')
    || normalized.endsWith('_password')
    || normalized.endsWith('_api_key')
    || normalized.endsWith('_private_key')
    || normalized.endsWith('_access_token')
    || normalized.endsWith('_refresh_token');
}

function redactTraceText(value: string): string {
  const clean = String(value || '')
    .replace(/(authorization\s*[:=]\s*bearer\s+)[^\s,;]+/gi, `$1${REDACTED_TRACE_VALUE}`)
    .replace(/((?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret)\s*[:=]\s*)[^\s,;]+/gi, `$1${REDACTED_TRACE_VALUE}`)
    .replace(/(chain[_ -]?of[_ -]?thought|private[_ -]?reasoning|hidden[_ -]?reasoning)\s*[:=]\s*[^\n]+/gi, `$1: ${REDACTED_TRACE_VALUE}`);

  return clean.length > MAX_TRACE_TEXT_LENGTH
    ? `${clean.slice(0, MAX_TRACE_TEXT_LENGTH).trimEnd()}…`
    : clean;
}

function sanitizeTraceValue(value: unknown, depth = 0): unknown {
  if (value == null) return value;
  if (typeof value === 'string') return redactTraceText(value);
  if (typeof value === 'number' || typeof value === 'boolean') return value;
  if (depth >= 3) return '[object redacted]';

  if (Array.isArray(value)) {
    return value.slice(0, 20).map((item) => sanitizeTraceValue(item, depth + 1));
  }

  if (typeof value === 'object') {
    const output: Record<string, unknown> = {};
    Object.entries(value as Record<string, unknown>).forEach(([key, item]) => {
      output[key] = isSensitiveTraceKey(key) ? REDACTED_TRACE_VALUE : sanitizeTraceValue(item, depth + 1);
    });
    return output;
  }

  return String(value);
}

function stringifyDetail(value: unknown): string {
  const sanitized = sanitizeTraceValue(value);
  if (sanitized == null) return '';
  if (typeof sanitized === 'string') return sanitized;
  if (typeof sanitized === 'number' || typeof sanitized === 'boolean') return String(sanitized);
  try {
    return JSON.stringify(sanitized, null, 2);
  } catch {
    return REDACTED_TRACE_VALUE;
  }
}

function StatusIcon({ status, color }: { status: ProcessTraceStatus; color: string }) {
  const sx = { fontSize: 19, color, flexShrink: 0 };
  if (status === 'completed') return null;
  if (status === 'failed') return <ErrorOutlineIcon sx={sx} />;
  if (status === 'blocked' || status === 'warning') return <WarningAmberIcon sx={sx} />;
  if (status === 'running') {
    return (
      <HourglassEmptyIcon
        sx={{
          ...sx,
          animation: 'processTraceHourglassClockwise 1.1s linear infinite',
          '@keyframes processTraceHourglassClockwise': {
            '0%': { transform: 'rotate(0deg)' },
            '100%': { transform: 'rotate(360deg)' },
          },
        }}
      />
    );
  }
  if (status === 'cancelled' || status === 'skipped') return <PauseCircleOutlineIcon sx={sx} />;
  return <RadioButtonUncheckedIcon sx={sx} />;
}

function normalizeIconKey(value?: string): string {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/_/g, '-');
}

function SubsystemIcon({
  iconId,
  subsystem,
  label,
  color,
}: {
  iconId?: string;
  subsystem?: string;
  label: string;
  color: string;
}) {
  const sx = { fontSize: 18, color };
  const iconKey = normalizeIconKey(iconId || subsystem);

  if (iconKey === 'swarm-core' || iconKey === 'swarmcore') return <AccountTreeOutlinedIcon sx={sx} />;
  if (iconKey === 'reasoning-core' || iconKey === 'reasoningcore') return <PsychologyOutlinedIcon sx={sx} />;
  if (iconKey === 'tool-core' || iconKey === 'toolcore') return <BuildOutlinedIcon sx={sx} />;
  if (iconKey === 'file-core' || iconKey === 'filecore') return <InsertDriveFileOutlinedIcon sx={sx} />;
  if (iconKey === 'context-core' || iconKey === 'contextcore') return <LayersOutlinedIcon sx={sx} />;
  if (iconKey === 'memory-core' || iconKey === 'memorycore') return <MemoryOutlinedIcon sx={sx} />;
  if (iconKey === 'skill-core' || iconKey === 'skillcore') return <ExtensionOutlinedIcon sx={sx} />;
  if (iconKey === 'mode-core' || iconKey === 'modecore') return <TuneOutlinedIcon sx={sx} />;
  if (iconKey === 'action-core' || iconKey === 'actioncore') return <AdsClickOutlinedIcon sx={sx} />;
  if (iconKey === 'evidence-core' || iconKey === 'evidencecore') return <FactCheckOutlinedIcon sx={sx} />;
  if (iconKey === 'trace-core' || iconKey === 'tracecore') return <TimelineOutlinedIcon sx={sx} />;
  if (iconKey === 'metric-core' || iconKey === 'metriccore') return <SpeedOutlinedIcon sx={sx} />;
  if (iconKey === 'handoff-core' || iconKey === 'handoffcore') return <CallSplitOutlinedIcon sx={sx} />;
  if (iconKey === 'miniagent-core' || iconKey === 'miniagentcore') return <HubOutlinedIcon sx={sx} />;
  if (iconKey === 'validation-core' || iconKey === 'validationcore') return <RuleOutlinedIcon sx={sx} />;
  if (iconKey === 'output-core' || iconKey === 'outputcore') return <OutputOutlinedIcon sx={sx} />;
  if (iconKey === 'review-core' || iconKey === 'reviewcore') return <VerifiedOutlinedIcon sx={sx} />;
  if (iconKey === 'browser-core' || iconKey === 'browsercore') return <LanguageIcon sx={sx} />;
  if (iconKey === 'config-core' || iconKey === 'configcore') return <SettingsSuggestOutlinedIcon sx={sx} />;
  if (iconKey === 'model-core' || iconKey === 'modelcore') return <SmartToyOutlinedIcon sx={sx} />;

  return (
    <Typography
      component="span"
      sx={{
        color,
        fontFamily: 'inherit',
        fontSize: '0.58rem',
        fontWeight: 800,
        letterSpacing: '-0.03em',
        lineHeight: 1,
      }}
    >
      {label}
    </Typography>
  );
}

export const ProcessTraceDropdown: React.FC<ProcessTraceDropdownProps> = ({
  item,
  defaultExpanded = false,
  compact = false,
  showRawDetails = false,
  bare = false,
}) => {
  const c = useClaudeTokens();
  const cardTokens = buildCardVisualTokens(c);
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [debugExpanded, setDebugExpanded] = useState(showRawDetails);

  const shouldHideTraceItem = item.internal_only || item.visible_to_user === false;

  const status = normalizeStatus(item.status);
  const durationLabel = formatDurationMs(item.duration_ms);
  const subsystem = redactTraceText(item.subsystem || 'TraceCore');
  const iconId = redactTraceText(item.icon_id || subsystem);
  const iconLabel = SUBSYSTEM_INITIALS[subsystem] || subsystem.slice(0, 2).toUpperCase() || 'TR';
  const title = redactTraceText(item.title || item.kind || 'Process trace');
  const summary = redactTraceText(item.summary || 'No process summary recorded.');
  const badge = redactTraceText(item.badge || STATUS_LABELS[status] || status);
  const evidenceCount = Array.isArray(item.evidence_refs) ? item.evidence_refs.length : 0;
  const artifactCount = Array.isArray(item.artifact_refs) ? item.artifact_refs.length : 0;
  const hasDebugDetails = Boolean(item.details && Object.keys(item.details).length > 0);
  const isDebugJsonTrace = item.kind === 'debug' || item.metadata?.display_mode === 'debug_json';
  const sanitizedDebugDetails = useMemo(
    () => (hasDebugDetails ? sanitizeTraceValue(item.details) : null),
    [hasDebugDetails, item.details],
  );

  const statusColor = useMemo(() => {
    if (status === 'completed') return c.status.success;
    if (status === 'failed') return c.status.error;
    if (status === 'blocked' || status === 'warning') return c.status.warning;
    if (status === 'running') return c.accent.primary;
    return c.text.tertiary;
  }, [c, status]);

  const detailRows = useMemo(() => {
    const rows: Array<[string, unknown]> = [];
    const showInternalRefs = item.metadata?.show_internal_refs === true;
    if (showInternalRefs && item.related_task_id) rows.push(['Task', redactTraceText(item.related_task_id)]);
    if (showInternalRefs && item.related_agent_id) rows.push(['Agent', redactTraceText(item.related_agent_id)]);
    if (showInternalRefs && item.related_miniagent_id) rows.push(['MiniAgent', redactTraceText(item.related_miniagent_id)]);
    if (item.related_skill_id) rows.push(['Skill', redactTraceText(item.related_skill_id)]);
    if (item.related_action_id) rows.push(['Action', redactTraceText(item.related_action_id)]);
    if (item.started_at) rows.push(['Started', item.started_at]);
    if (item.finished_at) rows.push(['Finished', item.finished_at]);
    if (durationLabel && !isDebugJsonTrace) rows.push(['Duration', durationLabel]);
    if (evidenceCount > 0) rows.push(['Evidence refs', evidenceCount]);
    if (artifactCount > 0) rows.push(['Artifact refs', artifactCount]);
    return rows;
  }, [item, durationLabel, evidenceCount, artifactCount, isDebugJsonTrace]);

  if (shouldHideTraceItem) {
    return null;
  }

  return (
    <Box
      sx={{
        bgcolor: bare ? 'transparent' : cardTokens.trace.background,
        border: bare ? 'none' : `1px solid ${status === 'running' ? cardTokens.trace.runningBorder : cardTokens.trace.border}`,
        borderRadius: cardTokens.trace.radius,
        overflow: 'hidden',
        transition: 'border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease',
        boxShadow: bare ? 'none' : (status === 'running' ? cardTokens.trace.runningShadow : cardTokens.trace.shadow),
        outline: bare ? 'none' : (status === 'running' ? `1px solid ${c.accent.primary}10` : 'none'),
      }}
    >
      <Box
        onClick={() => setExpanded((value) => !value)}
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 0.75,
          px: compact ? cardTokens.trace.compactPx : cardTokens.trace.px,
          py: compact ? cardTokens.trace.compactPy : cardTokens.trace.py,
          cursor: 'pointer',
          userSelect: 'none',
          '&:hover': { bgcolor: bare ? 'transparent' : cardTokens.trace.headerHoverBackground },
          transition: 'background 0.15s ease',
        }}
      >
        <Tooltip title={subsystem} arrow>
          <Box
            sx={{
              width: 18,
              height: 18,
              borderRadius: '50%',
              display: 'grid',
              placeItems: 'center',
              flexShrink: 0,
              bgcolor: `${statusColor}18`,
              border: `1px solid ${statusColor}45`,
              color: statusColor,
            }}
          >
            <SubsystemIcon iconId={iconId} subsystem={subsystem} label={iconLabel} color={statusColor} />
          </Box>
        </Tooltip>

        <StatusIcon status={status} color={statusColor} />

        <Box sx={{ minWidth: 0, flex: 1 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, minWidth: 0 }}>
            <Typography
              noWrap
              sx={{
                color: c.text.primary,
                fontSize: compact ? '0.76rem' : '0.82rem',
                fontWeight: 700,
                minWidth: 0,
              }}
            >
              {title}
            </Typography>
            <Typography
              noWrap
              sx={{
                color: statusColor,
                fontSize: '0.64rem',
                fontWeight: 700,
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
                flexShrink: 0,
              }}
            >
              {badge}
            </Typography>
          </Box>
          {!compact && (
            <Typography
              noWrap
              sx={{
                color: c.text.tertiary,
                fontSize: '0.72rem',
                mt: 0.15,
              }}
            >
              {summary}
            </Typography>
          )}
        </Box>

        {durationLabel && (
          <Typography
            sx={{
              color: c.text.tertiary,
              fontSize: '0.66rem',
              fontFamily: c.font.mono,
              flexShrink: 0,
            }}
          >
            {durationLabel}
          </Typography>
        )}

        <IconButton size="small" sx={{ color: c.text.tertiary, p: 0.2, flexShrink: 0 }}>
          <ExpandMoreIcon
            sx={{
              fontSize: 11.2,
              transform: expanded ? 'rotate(0deg)' : 'rotate(-90deg)',
              transition: 'transform 0.2s ease',
            }}
          />
        </IconButton>
      </Box>

      <Collapse in={expanded} timeout={180}>
        <Box
          sx={{
            borderTop: `1px solid ${cardTokens.trace.border}`,
            px: compact ? cardTokens.trace.compactPx : cardTokens.trace.px,
            py: cardTokens.trace.panelPadding,
            bgcolor: cardTokens.trace.expandedBackground,
          }}
        >
          {!isDebugJsonTrace && (
            <Typography
              sx={{
                color: c.text.secondary,
                fontSize: '0.76rem',
                lineHeight: 1.55,
                mb: detailRows.length > 0 ? 1 : 0,
                whiteSpace: 'pre-wrap',
                overflowWrap: 'anywhere',
              }}
            >
              {summary}
            </Typography>
          )}

          {isDebugJsonTrace && hasDebugDetails && (
            <Typography
              component="pre"
              sx={{
                m: 0,
                p: 0.75,
                border: `1px solid ${cardTokens.trace.border}`,
                borderRadius: cardTokens.trace.nestedRadius,
                bgcolor: cardTokens.trace.nestedBackground,
                color: c.text.tertiary,
                fontSize: '0.68rem',
                fontFamily: c.font.mono,
                whiteSpace: 'pre-wrap',
                overflowWrap: 'anywhere',
                maxHeight: 260,
                overflow: 'auto',
              }}
            >
              {stringifyDetail(sanitizedDebugDetails)}
            </Typography>
          )}

          {!isDebugJsonTrace && detailRows.length > 0 && (
            <Box sx={{ display: 'grid', gap: 0.45 }}>
              {detailRows.map(([label, value]) => (
                <Box
                  key={label}
                  sx={{
                    display: 'grid',
                    gridTemplateColumns: '92px minmax(0, 1fr)',
                    gap: 1,
                    alignItems: 'start',
                  }}
                >
                  <Typography sx={{ color: c.text.ghost, fontSize: '0.68rem', fontWeight: 700 }}>
                    {label}
                  </Typography>
                  <Typography
                    component="pre"
                    sx={{
                      m: 0,
                      color: c.text.tertiary,
                      fontSize: '0.68rem',
                      fontFamily: typeof value === 'object' ? c.font.mono : c.font.sans,
                      whiteSpace: typeof value === 'object' ? 'pre-wrap' : 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      overflowWrap: 'anywhere',
                    }}
                  >
                    {stringifyDetail(value)}
                  </Typography>
                </Box>
              ))}
            </Box>
          )}

          {!isDebugJsonTrace && hasDebugDetails && (
            <Box sx={{ mt: detailRows.length > 0 ? 0.9 : 0 }}>
              <Box
                component="button"
                type="button"
                onClick={(event) => {
                  event.stopPropagation();
                  setDebugExpanded((value) => !value);
                }}
                sx={{
                  width: '100%',
                  border: bare ? 'none' : `1px solid ${cardTokens.trace.border}`,
                  borderRadius: cardTokens.trace.nestedRadius,
                  bgcolor: bare ? 'transparent' : cardTokens.trace.background,
                  color: c.text.tertiary,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 1,
                  px: 0.75,
                  py: 0.55,
                  fontFamily: c.font.sans,
                  fontSize: '0.68rem',
                  fontWeight: 700,
                  textAlign: 'left',
                  '&:hover': { bgcolor: cardTokens.trace.headerHoverBackground },
          transition: 'background 0.15s ease',
                }}
              >
                <span>Debug data · redacted JSON</span>
                <ExpandMoreIcon
                  sx={{
                    fontSize: 10.4,
                    transform: debugExpanded ? 'rotate(0deg)' : 'rotate(-90deg)',
                    transition: 'transform 0.2s ease',
                    color: c.text.ghost,
                  }}
                />
              </Box>

              <Collapse in={debugExpanded} timeout={160}>
                <Typography
                  component="pre"
                  sx={{
                    mt: 0.65,
                    mb: 0,
                    p: 0.75,
                    border: bare ? 'none' : `1px solid ${cardTokens.trace.border}`,
                    borderRadius: cardTokens.trace.nestedRadius,
                    bgcolor: bare ? 'transparent' : cardTokens.trace.nestedBackground,
                    color: c.text.tertiary,
                    fontSize: '0.66rem',
                    fontFamily: c.font.mono,
                    whiteSpace: 'pre-wrap',
                    overflowWrap: 'anywhere',
                    maxHeight: 220,
                    overflow: 'auto',
                  }}
                >
                  {stringifyDetail(sanitizedDebugDetails)}
                </Typography>
              </Collapse>
            </Box>
          )}
        </Box>
      </Collapse>
    </Box>
  );
};

export type ProcessTraceTurnDropdownProps = {
  title: string;
  status?: ProcessTraceStatus | string;
  duration_ms?: number | null;
  items: ProcessTraceItem[];
  defaultExpanded?: boolean;
  compact?: boolean;
  bare?: boolean;
};

export const ProcessTraceTurnDropdown: React.FC<ProcessTraceTurnDropdownProps> = ({
  title,
  status = 'completed',
  duration_ms = null,
  items,
  defaultExpanded,
  compact = true,
  bare = false,
}) => {
  const c = useClaudeTokens();
  const cardTokens = buildCardVisualTokens(c);
  const normalizedStatus = normalizeStatus(status);
  const durationLabel = formatDurationMs(duration_ms);
  const [expanded, setExpanded] = useState(defaultExpanded ?? normalizedStatus === 'running');

  const visibleItems = useMemo(
    () => items.filter((item) => !item.internal_only && item.visible_to_user !== false),
    [items],
  );

  const statusColor = useMemo(() => {
    if (normalizedStatus === 'completed') return c.status.success;
    if (normalizedStatus === 'failed') return c.status.error;
    if (normalizedStatus === 'blocked' || normalizedStatus === 'warning') return c.status.warning;
    if (normalizedStatus === 'running') return c.accent.primary;
    return c.text.tertiary;
  }, [c, normalizedStatus]);

  if (visibleItems.length === 0) return null;

  const headerTitle = durationLabel
    ? `${redactTraceText(title)} durante ${durationLabel}`
    : redactTraceText(title);

  return (
    <Box
      sx={{
        bgcolor: bare ? 'transparent' : cardTokens.trace.turnBackground,
        border: bare ? 'none' : `1px solid ${normalizedStatus === 'running' ? cardTokens.trace.runningBorder : cardTokens.trace.border}`,
        borderRadius: cardTokens.trace.turnRadius,
        overflow: 'hidden',
        boxShadow: bare ? 'none' : (normalizedStatus === 'running' ? cardTokens.trace.runningTurnShadow : cardTokens.trace.turnShadow),
        outline: bare ? 'none' : (normalizedStatus === 'running' ? `1px solid ${c.accent.primary}10` : 'none'),
      }}
    >
      <Box
        onClick={() => setExpanded((value) => !value)}
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 0.75,
          px: compact ? cardTokens.trace.compactPx : cardTokens.trace.px,
          py: compact ? cardTokens.trace.turnCompactPy : cardTokens.trace.py,
          cursor: 'pointer',
          userSelect: 'none',
          '&:hover': { bgcolor: bare ? 'transparent' : cardTokens.trace.headerHoverBackground },
          transition: 'background 0.15s ease',
        }}
      >
        <Tooltip title="Turn work trace" arrow>
          <Box
            sx={{
              width: 18,
              height: 18,
              borderRadius: '50%',
              display: 'grid',
              placeItems: 'center',
              flexShrink: 0,
              bgcolor: `${statusColor}18`,
              border: `1px solid ${statusColor}45`,
            }}
          >
            <TimelineOutlinedIcon sx={{ fontSize: 10.8, color: statusColor }} />
          </Box>
        </Tooltip>

        <StatusIcon status={normalizedStatus} color={statusColor} />

        <Typography
          noWrap
          sx={{
            color: c.text.primary,
            fontSize: compact ? '0.78rem' : '0.84rem',
            fontWeight: 700,
            minWidth: 0,
            flex: 1,
          }}
        >
          {headerTitle}
        </Typography>

        <Typography
          noWrap
          sx={{
            color: c.text.tertiary,
            fontSize: '0.66rem',
            fontWeight: 650,
            flexShrink: 0,
          }}
        >
          {visibleItems.length} paso{visibleItems.length === 1 ? '' : 's'}
        </Typography>

        <IconButton size="small" sx={{ color: c.text.tertiary, p: 0.2, flexShrink: 0 }}>
          <ExpandMoreIcon
            sx={{
              fontSize: 11.2,
              transform: expanded ? 'rotate(0deg)' : 'rotate(-90deg)',
              transition: 'transform 0.2s ease',
            }}
          />
        </IconButton>
      </Box>

      <Collapse in={expanded} timeout={180}>
        <Box sx={{ borderTop: bare ? 'none' : `1px solid ${cardTokens.trace.border}`, p: compact ? cardTokens.trace.compactPanelPadding : cardTokens.trace.panelPadding, bgcolor: bare ? 'transparent' : cardTokens.trace.background }}>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: cardTokens.trace.itemGap }}>
            {visibleItems.map((item) => (
              <ProcessTraceDropdown
                key={item.trace_id || `${item.kind}-${item.title}`}
                item={item}
                compact
                defaultExpanded={item.status === 'running' || item.status === 'blocked'}
                bare={bare}
              />
            ))}
          </Box>
        </Box>
      </Collapse>
    </Box>
  );
};

export default ProcessTraceDropdown;
