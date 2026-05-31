import React, { useMemo, useState } from 'react';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Collapse from '@mui/material/Collapse';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import MemoryOutlinedIcon from '@mui/icons-material/MemoryOutlined';
import type { UnifiedComposerState } from '@/shared/types/unifiedComposer';
import { useClaudeTokens } from '@/shared/styles/ThemeContext';

interface Props {
  state?: UnifiedComposerState | null;
  processTraceItems?: unknown[];
  title?: string;
  compact?: boolean;
}

function safeLabel(value: unknown, fallback = 'memory'): string {
  const raw = String(value ?? fallback).trim();
  if (!raw) return fallback;
  if (/token|secret|password|cookie|bearer|private[_-]?key/i.test(raw)) return '[redacted]';
  return raw.length > 100 ? `${raw.slice(0, 97)}…` : raw;
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : value ? [value] : [];
}

const ProjectMemoryContextPanel: React.FC<Props> = ({
  state,
  processTraceItems = [],
  title = 'Project memory',
  compact = false,
}) => {
  const c = useClaudeTokens();
  const [open, setOpen] = useState(false);

  const rows = useMemo(() => {
    const memoryRefs = (state?.context_refs || [])
      .filter((ref) => ref.kind === 'memory')
      .map((ref) => `${safeLabel(ref.label)} · ${safeLabel(ref.source)}`);

    const projectScope = (state?.research_sources || [])
      .filter((src) => src.kind === 'current_project' && (src.state === 'selected' || src.state === 'requires_approval'))
      .map((src) => `${safeLabel(src.label)} · ${src.state}`);

    const traceMemory = (processTraceItems || [])
      .filter((raw) => {
        const item = raw as any;
        const joined = `${item?.subsystem || ''} ${item?.kind || ''} ${item?.title || ''}`.toLowerCase();
        return joined.includes('memory') || joined.includes('context');
      })
      .map((raw) => {
        const item = raw as any;
        return safeLabel(item?.summary || item?.title || item?.trace_id, 'memory trace');
      });

    const evidenceMemory = (processTraceItems || [])
      .flatMap((raw) => {
        const item = raw as any;
        return [
          ...asArray(item?.evidence_refs),
          ...asArray(item?.details?.evidence_refs),
        ];
      })
      .map((ref) => safeLabel(ref, 'evidence'));

    const rowsOut: Array<{ label: string; values: string[]; tone: string }> = [];
    if (memoryRefs.length) rowsOut.push({ label: 'Memory refs', values: memoryRefs, tone: c.status.info });
    if (projectScope.length) rowsOut.push({ label: 'Project scope', values: projectScope, tone: c.accent.primary });
    if (traceMemory.length) rowsOut.push({ label: 'Used in trace', values: traceMemory, tone: c.status.success });
    if (evidenceMemory.length) rowsOut.push({ label: 'Evidence refs', values: evidenceMemory, tone: c.status.success });

    if (!rowsOut.length && state) {
      rowsOut.push({
        label: 'Status',
        values: ['No explicit memory refs selected for this request', 'project memory actions are read-only/prepared here'],
        tone: c.text.tertiary,
      });
    }

    return rowsOut;
  }, [c, processTraceItems, state]);

  if (!rows.length) return null;

  const count = rows.reduce((sum, row) => sum + row.values.length, 0);

  return (
    <Box sx={{ mx: compact ? 0 : 1.5, mb: compact ? 0.5 : 0.75, border: `1px solid ${c.border.subtle}`, borderRadius: 1.5, bgcolor: `${c.bg.secondary}66`, overflow: 'hidden' }}>
      <Box onClick={() => setOpen((value) => !value)} sx={{ display: 'flex', alignItems: 'center', gap: 0.75, px: 1, py: 0.55, cursor: 'pointer' }}>
        <MemoryOutlinedIcon sx={{ fontSize: 14, color: c.text.tertiary }} />
        <Typography sx={{ fontSize: '0.68rem', color: c.text.secondary, fontWeight: 700, flex: 1 }}>
          {title} · {count} item{count === 1 ? '' : 's'}
        </Typography>
        <Tooltip title={open ? 'Hide project memory context' : 'Show project memory context'}>
          <IconButton size="small" sx={{ width: 20, height: 20, color: c.text.tertiary }}>
            <ExpandMoreIcon sx={{ fontSize: 16, transform: open ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 120ms ease' }} />
          </IconButton>
        </Tooltip>
      </Box>
      <Collapse in={open}>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.55, px: 1, pb: 0.85 }}>
          {rows.map((row) => (
            <Box key={row.label} sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexWrap: 'wrap' }}>
              <Typography sx={{ fontSize: '0.61rem', color: c.text.ghost, fontWeight: 800, textTransform: 'uppercase', minWidth: 86 }}>
                {row.label}
              </Typography>
              {row.values.slice(0, 8).map((value, idx) => (
                <Chip
                  key={`${row.label}-${value}-${idx}`}
                  label={value}
                  size="small"
                  sx={{ height: 20, maxWidth: 220, fontSize: '0.61rem', color: row.tone, bgcolor: `${row.tone}12`, '& .MuiChip-label': { overflow: 'hidden', textOverflow: 'ellipsis' } }}
                />
              ))}
              {row.values.length > 8 && <Typography sx={{ fontSize: '0.62rem', color: c.text.ghost }}>+{row.values.length - 8}</Typography>}
            </Box>
          ))}
        </Box>
      </Collapse>
    </Box>
  );
};

export default ProjectMemoryContextPanel;
