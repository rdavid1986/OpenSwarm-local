import React, { useMemo, useState } from 'react';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Collapse from '@mui/material/Collapse';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import DevicesOutlinedIcon from '@mui/icons-material/DevicesOutlined';
import type { TaskMonitorStatus } from '@/app/components/LongRunningTaskMonitor';
import { useClaudeTokens } from '@/shared/styles/ThemeContext';

export interface RemoteTaskStateSnapshot {
  surfaceLabel: string;
  taskId?: string | null;
  status?: TaskMonitorStatus | string | null;
  host?: string | null;
  provider?: string | null;
  model?: string | null;
  mode?: string | null;
  approvalsCount?: number;
  outputRefs?: string[];
  screenshotRefs?: string[];
  terminalRefs?: string[];
  testRefs?: string[];
  diffRefs?: string[];
  evidenceRefs?: string[];
  progressLabel?: string | null;
  connectionState?: 'live' | 'reconnecting' | 'offline' | 'local_only' | string | null;
}

interface Props {
  snapshot: RemoteTaskStateSnapshot;
  compact?: boolean;
  title?: string;
}

function safe(value: unknown, fallback = ''): string {
  const raw = String(value ?? fallback).trim();
  if (!raw) return fallback;
  if (/token|secret|password|cookie|bearer|private[_-]?key/i.test(raw)) return '[redacted]';
  return raw.length > 100 ? `${raw.slice(0, 97)}…` : raw;
}

const RemoteTaskStateContractPanel: React.FC<Props> = ({ snapshot, compact = false, title = 'Portable task state' }) => {
  const c = useClaudeTokens();
  const [open, setOpen] = useState(false);

  const rows = useMemo(() => {
    const base = [
      `surface:${safe(snapshot.surfaceLabel)}`,
      snapshot.taskId ? `task:${safe(snapshot.taskId)}` : 'task:not persisted',
      snapshot.status ? `status:${safe(snapshot.status)}` : 'status:not provided',
      snapshot.host ? `host:${safe(snapshot.host)}` : 'host:local',
      snapshot.provider ? `provider:${safe(snapshot.provider)}` : '',
      snapshot.model ? `model:${safe(snapshot.model)}` : '',
      snapshot.mode ? `mode:${safe(snapshot.mode)}` : '',
      typeof snapshot.approvalsCount === 'number' ? `approvals:${snapshot.approvalsCount}` : '',
      snapshot.connectionState ? `connection:${safe(snapshot.connectionState)}` : 'connection:local_visible',
      snapshot.progressLabel ? `progress:${safe(snapshot.progressLabel)}` : 'progress:real-state-only',
    ].filter(Boolean);

    const refs = [
      ...(snapshot.outputRefs || []).map((ref) => `output:${safe(ref)}`),
      ...(snapshot.screenshotRefs || []).map((ref) => `screenshot:${safe(ref)}`),
      ...(snapshot.terminalRefs || []).map((ref) => `terminal:${safe(ref)}`),
      ...(snapshot.testRefs || []).map((ref) => `test:${safe(ref)}`),
      ...(snapshot.diffRefs || []).map((ref) => `diff:${safe(ref)}`),
      ...(snapshot.evidenceRefs || []).map((ref) => `evidence:${safe(ref)}`),
    ];

    const contract = ['serializable:prepared', 'mobile_ui:not implemented', 'remote execution:not implemented', 'no fake progress'];

    return [
      { label: 'State', values: base, tone: c.status.info },
      ...(refs.length ? [{ label: 'Refs', values: refs, tone: c.status.success }] : []),
      { label: 'Contract', values: contract, tone: c.text.tertiary },
    ];
  }, [c, snapshot]);

  const total = rows.reduce((sum, row) => sum + row.values.length, 0);
  if (!total) return null;

  return (
    <Box sx={{ mx: compact ? 0 : 1.5, mb: compact ? 0.5 : 0.75, border: `1px solid ${c.border.subtle}`, borderRadius: 1.5, bgcolor: `${c.bg.secondary}66`, overflow: 'hidden' }}>
      <Box onClick={() => setOpen((value) => !value)} sx={{ display: 'flex', alignItems: 'center', gap: 0.75, px: 1, py: 0.55, cursor: 'pointer' }}>
        <DevicesOutlinedIcon sx={{ fontSize: 14, color: c.text.tertiary }} />
        <Typography sx={{ fontSize: '0.68rem', color: c.text.secondary, fontWeight: 700, flex: 1 }}>
          {title} · {total} fields
        </Typography>
        <Tooltip title={open ? 'Hide portable task state' : 'Show portable task state'}>
          <IconButton size="small" sx={{ width: 20, height: 20, color: c.text.tertiary }}>
            <ExpandMoreIcon sx={{ fontSize: 16, transform: open ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 120ms ease' }} />
          </IconButton>
        </Tooltip>
      </Box>
      <Collapse in={open}>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.55, px: 1, pb: 0.85 }}>
          {rows.map((row) => (
            <Box key={row.label} sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexWrap: 'wrap' }}>
              <Typography sx={{ fontSize: '0.61rem', color: c.text.ghost, fontWeight: 800, textTransform: 'uppercase', minWidth: 72 }}>
                {row.label}
              </Typography>
              {row.values.slice(0, 10).map((value, idx) => (
                <Chip
                  key={`${row.label}-${value}-${idx}`}
                  label={value}
                  size="small"
                  sx={{ height: 20, maxWidth: 220, fontSize: '0.61rem', color: row.tone, bgcolor: `${row.tone}12`, '& .MuiChip-label': { overflow: 'hidden', textOverflow: 'ellipsis' } }}
                />
              ))}
              {row.values.length > 10 && <Typography sx={{ fontSize: '0.62rem', color: c.text.ghost }}>+{row.values.length - 10}</Typography>}
            </Box>
          ))}
        </Box>
      </Collapse>
    </Box>
  );
};

export default RemoteTaskStateContractPanel;
