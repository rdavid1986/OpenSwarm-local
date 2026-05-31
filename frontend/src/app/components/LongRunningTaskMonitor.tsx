import React, { useEffect, useState } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Chip from '@mui/material/Chip';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import Button from '@mui/material/Button';
import LinearProgress from '@mui/material/LinearProgress';
import StopCircleOutlinedIcon from '@mui/icons-material/StopCircleOutlined';
import PauseCircleOutlineIcon from '@mui/icons-material/PauseCircleOutline';
import PlayCircleOutlineIcon from '@mui/icons-material/PlayCircleOutline';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import { useClaudeTokens } from '@/shared/styles/ThemeContext';

export type TaskMonitorStatus = 'idle' | 'running' | 'waiting_approval' | 'completed' | 'error' | 'stopped' | 'loading' | 'blocked';

export interface TaskMonitorMetric {
  label: string;
  value: string | number;
  tone?: 'default' | 'info' | 'warning' | 'success' | 'error';
}

interface LongRunningTaskMonitorProps {
  title?: string;
  status: TaskMonitorStatus;
  surfaceLabel: string;
  sessionId?: string | null;
  model?: string | null;
  mode?: string | null;
  queueCount?: number;
  pendingApprovalsCount?: number;
  traceCount?: number;
  evidenceCount?: number;
  artifactCount?: number;
  latestActivity?: string | null;
  visible?: boolean;
  timerActive?: boolean;
  onStop?: () => void;
  stopLabel?: string;
  metrics?: TaskMonitorMetric[];
}

function formatElapsed(ms: number): string {
  const totalSeconds = Math.floor(Math.max(0, ms) / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes <= 0) return `${seconds}s`;
  return `${minutes}m ${seconds.toString().padStart(2, '0')}s`;
}

export default function LongRunningTaskMonitor({
  title = 'Task monitor',
  status,
  surfaceLabel,
  sessionId,
  model,
  mode,
  queueCount = 0,
  pendingApprovalsCount = 0,
  traceCount = 0,
  evidenceCount = 0,
  artifactCount = 0,
  latestActivity,
  visible = true,
  timerActive,
  onStop,
  stopLabel = 'Stop',
  metrics = [],
}: LongRunningTaskMonitorProps) {
  const c = useClaudeTokens();
  const isActive = timerActive ?? ['running', 'waiting_approval', 'loading', 'blocked'].includes(status);
  const [startedAt, setStartedAt] = useState<number | null>(isActive ? Date.now() : null);
  const [elapsedMs, setElapsedMs] = useState(0);

  useEffect(() => {
    if (!isActive) {
      setStartedAt(null);
      setElapsedMs(0);
      return undefined;
    }
    const start = Date.now();
    setStartedAt(start);
    setElapsedMs(0);
    const interval = window.setInterval(() => setElapsedMs(Date.now() - start), 1000);
    return () => window.clearInterval(interval);
  }, [isActive, sessionId, surfaceLabel]);

  if (!visible) return null;

  const statusMeta: Record<TaskMonitorStatus, { label: string; color: string; bg: string }> = {
    idle: { label: 'Idle', color: c.text.tertiary, bg: c.bg.secondary },
    running: { label: 'Running', color: c.status.info, bg: `${c.status.info}14` },
    waiting_approval: { label: 'Waiting approval', color: c.status.warning, bg: `${c.status.warning}14` },
    loading: { label: 'Loading', color: c.status.info, bg: `${c.status.info}14` },
    blocked: { label: 'Blocked', color: c.status.warning, bg: `${c.status.warning}14` },
    completed: { label: 'Completed', color: c.status.success, bg: `${c.status.success}12` },
    stopped: { label: 'Stopped', color: c.text.tertiary, bg: c.bg.secondary },
    error: { label: 'Error', color: c.status.error, bg: `${c.status.error}12` },
  };
  const meta = statusMeta[status] || statusMeta.idle;
  const metricToneColor = (tone?: TaskMonitorMetric['tone']) => {
    if (tone === 'info') return c.status.info;
    if (tone === 'warning') return c.status.warning;
    if (tone === 'success') return c.status.success;
    if (tone === 'error') return c.status.error;
    return c.text.secondary;
  };
  const builtMetrics: TaskMonitorMetric[] = [
    { label: 'Queue', value: queueCount },
    { label: 'Approvals', value: pendingApprovalsCount, tone: pendingApprovalsCount ? 'warning' : 'default' },
    { label: 'Trace', value: traceCount },
    { label: 'Evidence', value: evidenceCount },
    { label: 'Artifacts', value: artifactCount },
    ...metrics,
  ];

  return (
    <Box
      sx={{
        mx: 2,
        mb: 1,
        p: 1,
        borderRadius: `${c.radius.lg}px`,
        border: `1px solid ${c.border.subtle}`,
        bgcolor: c.bg.surface,
        boxShadow: c.shadow.sm,
      }}
    >
      {isActive && (
        <LinearProgress
          variant="indeterminate"
          sx={{
            height: 2,
            mb: 0.9,
            borderRadius: 999,
            bgcolor: c.bg.secondary,
            '& .MuiLinearProgress-bar': { bgcolor: meta.color },
          }}
        />
      )}
      <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, minWidth: 0 }}>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.6, alignItems: 'center', mb: 0.55 }}>
            <Typography sx={{ color: c.text.primary, fontSize: '0.78rem', fontWeight: 700 }}>
              {title}
            </Typography>
            <Chip size="small" label={meta.label} sx={{ height: 20, color: meta.color, bgcolor: meta.bg, fontSize: '0.66rem', fontWeight: 700 }} />
            <Chip size="small" label={surfaceLabel} sx={{ height: 20, color: c.text.secondary, bgcolor: c.bg.secondary, fontSize: '0.66rem' }} />
            {isActive && startedAt && (
              <Chip
                size="small"
                icon={<AccessTimeIcon sx={{ fontSize: '0.78rem !important' }} />}
                label={`${formatElapsed(elapsedMs)} local`}
                sx={{ height: 20, color: c.text.tertiary, bgcolor: 'transparent', border: `1px solid ${c.border.subtle}`, fontSize: '0.66rem' }}
              />
            )}
          </Box>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, alignItems: 'center', mb: latestActivity ? 0.5 : 0 }}>
            {mode && <Typography sx={{ color: c.text.tertiary, fontSize: '0.69rem' }}>mode: {mode}</Typography>}
            {model && <Typography sx={{ color: c.text.tertiary, fontSize: '0.69rem' }}>model: {model}</Typography>}
            {sessionId && <Typography sx={{ color: c.text.ghost, fontSize: '0.68rem' }}>id: {String(sessionId).slice(0, 10)}</Typography>}
          </Box>
          {latestActivity && (
            <Typography sx={{ color: c.text.secondary, fontSize: '0.72rem', lineHeight: 1.35, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {latestActivity}
            </Typography>
          )}
        </Box>
        <Box sx={{ display: 'flex', gap: 0.4, alignItems: 'center', flexShrink: 0 }}>
          <Tooltip title="Pause/resume is not wired to a real handler here.">
            <span>
              <IconButton size="small" disabled sx={{ p: 0.35 }}>
                <PauseCircleOutlineIcon sx={{ fontSize: 17 }} />
              </IconButton>
            </span>
          </Tooltip>
          <Tooltip title="Resume is only available from real approval controls when present.">
            <span>
              <IconButton size="small" disabled sx={{ p: 0.35 }}>
                <PlayCircleOutlineIcon sx={{ fontSize: 17 }} />
              </IconButton>
            </span>
          </Tooltip>
          {onStop && (
            <Tooltip title="Uses the existing stop/cancel handler for this surface.">
              <Button
                size="small"
                color="error"
                variant="outlined"
                onClick={onStop}
                startIcon={<StopCircleOutlinedIcon sx={{ fontSize: 15 }} />}
                sx={{ minHeight: 25, px: 0.8, py: 0.1, fontSize: '0.68rem', textTransform: 'none' }}
              >
                {stopLabel}
              </Button>
            </Tooltip>
          )}
        </Box>
      </Box>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 0.75 }}>
        {builtMetrics.map((metric) => (
          <Chip
            key={`${metric.label}-${metric.value}`}
            size="small"
            label={`${metric.label}: ${metric.value}`}
            sx={{ height: 19, color: metricToneColor(metric.tone), bgcolor: c.bg.secondary, fontSize: '0.64rem' }}
          />
        ))}
      </Box>
    </Box>
  );
}
