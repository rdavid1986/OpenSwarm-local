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

import { useClaudeTokens } from '@/shared/styles/ThemeContext';

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
};

const STATUS_LABELS: Record<string, string> = {
  planned: 'Planned',
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
  MemoryCore: 'ME',
  SkillCore: 'SK',
  ModeCore: 'MO',
  ActionCore: 'AC',
  EvidenceCore: 'EV',
  TraceCore: 'TR',
  MetricCore: 'MT',
  HandoffCore: 'HF',
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
  const normalized = String(status || '').toLowerCase();
  if (['planned', 'running', 'completed', 'failed', 'blocked', 'skipped', 'cancelled', 'warning'].includes(normalized)) {
    return normalized as ProcessTraceStatus;
  }
  return 'planned';
}

function stringifyDetail(value: unknown): string {
  if (value == null) return '';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function StatusIcon({ status, color }: { status: ProcessTraceStatus; color: string }) {
  const sx = { fontSize: 15, color, flexShrink: 0 };
  if (status === 'completed') return <CheckCircleOutlineIcon sx={sx} />;
  if (status === 'failed') return <ErrorOutlineIcon sx={sx} />;
  if (status === 'blocked' || status === 'warning') return <WarningAmberIcon sx={sx} />;
  if (status === 'running') return <HourglassEmptyIcon sx={sx} />;
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
  const sx = { fontSize: 14, color };
  const iconKey = normalizeIconKey(iconId || subsystem);

  if (iconKey === 'swarm-core' || iconKey === 'swarmcore') return <AccountTreeOutlinedIcon sx={sx} />;
  if (iconKey === 'memory-core' || iconKey === 'memorycore') return <MemoryOutlinedIcon sx={sx} />;
  if (iconKey === 'skill-core' || iconKey === 'skillcore') return <ExtensionOutlinedIcon sx={sx} />;
  if (iconKey === 'mode-core' || iconKey === 'modecore') return <TuneOutlinedIcon sx={sx} />;
  if (iconKey === 'action-core' || iconKey === 'actioncore') return <AdsClickOutlinedIcon sx={sx} />;
  if (iconKey === 'evidence-core' || iconKey === 'evidencecore') return <FactCheckOutlinedIcon sx={sx} />;
  if (iconKey === 'trace-core' || iconKey === 'tracecore') return <TimelineOutlinedIcon sx={sx} />;
  if (iconKey === 'metric-core' || iconKey === 'metriccore') return <SpeedOutlinedIcon sx={sx} />;
  if (iconKey === 'handoff-core' || iconKey === 'handoffcore') return <CallSplitOutlinedIcon sx={sx} />;
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
}) => {
  const c = useClaudeTokens();
  const [expanded, setExpanded] = useState(defaultExpanded);

  const status = normalizeStatus(item.status);
  const durationLabel = formatDurationMs(item.duration_ms);
  const subsystem = item.subsystem || 'TraceCore';
  const iconId = item.icon_id || subsystem;
  const iconLabel = SUBSYSTEM_INITIALS[subsystem] || subsystem.slice(0, 2).toUpperCase() || 'TR';
  const title = item.title || item.kind || 'Process trace';
  const summary = item.summary || 'No process summary recorded.';
  const badge = item.badge || STATUS_LABELS[status] || status;
  const evidenceCount = Array.isArray(item.evidence_refs) ? item.evidence_refs.length : 0;
  const artifactCount = Array.isArray(item.artifact_refs) ? item.artifact_refs.length : 0;

  const statusColor = useMemo(() => {
    if (status === 'completed') return c.status.success;
    if (status === 'failed') return c.status.error;
    if (status === 'blocked' || status === 'warning') return c.status.warning;
    if (status === 'running') return c.accent.primary;
    return c.text.tertiary;
  }, [c, status]);

  const detailRows = useMemo(() => {
    const rows: Array<[string, unknown]> = [];
    if (item.related_task_id) rows.push(['Task', item.related_task_id]);
    if (item.related_agent_id) rows.push(['Agent', item.related_agent_id]);
    if (item.related_miniagent_id) rows.push(['MiniAgent', item.related_miniagent_id]);
    if (item.related_skill_id) rows.push(['Skill', item.related_skill_id]);
    if (item.related_action_id) rows.push(['Action', item.related_action_id]);
    if (item.started_at) rows.push(['Started', item.started_at]);
    if (item.finished_at) rows.push(['Finished', item.finished_at]);
    if (durationLabel) rows.push(['Duration', durationLabel]);
    if (evidenceCount > 0) rows.push(['Evidence refs', evidenceCount]);
    if (artifactCount > 0) rows.push(['Artifact refs', artifactCount]);
    if (showRawDetails && item.details && Object.keys(item.details).length > 0) rows.push(['Details', item.details]);
    return rows;
  }, [item, durationLabel, evidenceCount, artifactCount, showRawDetails]);

  return (
    <Box
      sx={{
        bgcolor: c.bg.elevated,
        border: `1px solid ${status === 'running' ? `${c.accent.primary}80` : c.border.subtle}`,
        borderRadius: `${c.radius.md}px`,
        overflow: 'hidden',
        transition: 'border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease',
        boxShadow: status === 'running' ? `0 0 0 1px ${c.accent.primary}25, 0 0 18px ${c.accent.primary}18` : 'none',
      }}
    >
      <Box
        onClick={() => setExpanded((value) => !value)}
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 0.75,
          px: compact ? 1 : 1.25,
          py: compact ? 0.65 : 0.85,
          cursor: 'pointer',
          userSelect: 'none',
          '&:hover': { bgcolor: c.bg.secondary },
        }}
      >
        <Tooltip title={subsystem} arrow>
          <Box
            sx={{
              width: 24,
              height: 24,
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
              fontSize: 18,
              transform: expanded ? 'rotate(0deg)' : 'rotate(-90deg)',
              transition: 'transform 0.2s ease',
            }}
          />
        </IconButton>
      </Box>

      <Collapse in={expanded} timeout={180}>
        <Box
          sx={{
            borderTop: `1px solid ${c.border.subtle}`,
            px: compact ? 1 : 1.25,
            py: 1,
            bgcolor: c.bg.surface,
          }}
        >
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

          {detailRows.length > 0 && (
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
        </Box>
      </Collapse>
    </Box>
  );
};

export default ProcessTraceDropdown;
