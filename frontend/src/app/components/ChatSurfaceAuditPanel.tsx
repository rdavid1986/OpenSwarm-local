import React, { useMemo, useState } from 'react';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Collapse from '@mui/material/Collapse';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import FactCheckOutlinedIcon from '@mui/icons-material/FactCheckOutlined';
import { useClaudeTokens } from '@/shared/styles/ThemeContext';

export interface ChatSurfaceAuditSnapshot {
  surfaceLabel: string;
  actions: string[];
  disabledActions?: string[];
  contextCount?: number;
  traceCount?: number;
  evidenceCount?: number;
  queueCount?: number;
  monitorVisible?: boolean;
  accessibilityNotes?: string[];
  densityNotes?: string[];
  performanceNotes?: string[];
}

interface Props {
  snapshot: ChatSurfaceAuditSnapshot;
  compact?: boolean;
  title?: string;
}

function short(value: unknown, fallback = ''): string {
  const raw = String(value ?? fallback).trim();
  if (!raw) return fallback;
  return raw.length > 110 ? `${raw.slice(0, 107)}…` : raw;
}

const ChatSurfaceAuditPanel: React.FC<Props> = ({ snapshot, compact = false, title = 'Unified surface audit' }) => {
  const c = useClaudeTokens();
  const [open, setOpen] = useState(false);

  const rows = useMemo(() => {
    const rowsOut: Array<{ label: string; values: string[]; tone: string }> = [
      {
        label: 'Surface',
        values: [
          `surface:${short(snapshot.surfaceLabel)}`,
          `context:${snapshot.contextCount || 0}`,
          `trace:${snapshot.traceCount || 0}`,
          `evidence:${snapshot.evidenceCount || 0}`,
          `queue:${snapshot.queueCount || 0}`,
          snapshot.monitorVisible ? 'monitor:visible' : 'monitor:hidden_when_idle',
        ],
        tone: c.status.info,
      },
    ];

    if (snapshot.actions.length) {
      rowsOut.push({ label: 'Actions', values: snapshot.actions.map(short), tone: c.status.success });
    }
    if (snapshot.disabledActions?.length) {
      rowsOut.push({ label: 'Prepared', values: snapshot.disabledActions.map(short), tone: c.text.tertiary });
    }
    if (snapshot.accessibilityNotes?.length) {
      rowsOut.push({ label: 'Accessibility', values: snapshot.accessibilityNotes.map(short), tone: c.accent.primary });
    }
    if (snapshot.densityNotes?.length) {
      rowsOut.push({ label: 'Density', values: snapshot.densityNotes.map(short), tone: c.status.info });
    }
    if (snapshot.performanceNotes?.length) {
      rowsOut.push({ label: 'Performance', values: snapshot.performanceNotes.map(short), tone: c.status.warning });
    }

    return rowsOut;
  }, [c, snapshot]);

  const total = rows.reduce((sum, row) => sum + row.values.length, 0);
  if (!total) return null;

  return (
    <Box sx={{ mx: compact ? 0 : 1.5, mb: compact ? 0.5 : 0.75, border: `1px solid ${c.border.subtle}`, borderRadius: 1.5, bgcolor: `${c.bg.secondary}60`, overflow: 'hidden' }}>
      <Box
        role="button"
        aria-expanded={open}
        aria-label={`${title} for ${snapshot.surfaceLabel}`}
        onClick={() => setOpen((value) => !value)}
        sx={{ display: 'flex', alignItems: 'center', gap: 0.75, px: 1, py: 0.55, cursor: 'pointer' }}
      >
        <FactCheckOutlinedIcon sx={{ fontSize: 14, color: c.text.tertiary }} />
        <Typography sx={{ fontSize: '0.68rem', color: c.text.secondary, fontWeight: 700, flex: 1 }}>
          {title} · {snapshot.surfaceLabel} · {total}
        </Typography>
        <Tooltip title={open ? 'Hide surface audit' : 'Show surface audit'}>
          <IconButton size="small" aria-label={open ? 'Hide surface audit' : 'Show surface audit'} sx={{ width: 20, height: 20, color: c.text.tertiary }}>
            <ExpandMoreIcon sx={{ fontSize: 16, transform: open ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 120ms ease' }} />
          </IconButton>
        </Tooltip>
      </Box>
      <Collapse in={open}>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.55, px: 1, pb: 0.85 }}>
          {rows.map((row) => (
            <Box key={row.label} sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexWrap: 'wrap' }}>
              <Typography sx={{ fontSize: '0.61rem', color: c.text.ghost, fontWeight: 800, textTransform: 'uppercase', minWidth: 92 }}>
                {row.label}
              </Typography>
              {row.values.slice(0, 10).map((value, idx) => (
                <Chip
                  key={`${row.label}-${value}-${idx}`}
                  label={value}
                  size="small"
                  sx={{ height: 20, maxWidth: 230, fontSize: '0.61rem', color: row.tone, bgcolor: `${row.tone}12`, '& .MuiChip-label': { overflow: 'hidden', textOverflow: 'ellipsis' } }}
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

export default ChatSurfaceAuditPanel;
