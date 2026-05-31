import React, { useMemo, useState } from 'react';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Collapse from '@mui/material/Collapse';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import FactCheckOutlinedIcon from '@mui/icons-material/FactCheckOutlined';
import InsertDriveFileOutlinedIcon from '@mui/icons-material/InsertDriveFileOutlined';
import PublicOutlinedIcon from '@mui/icons-material/PublicOutlined';
import BuildOutlinedIcon from '@mui/icons-material/BuildOutlined';
import TerminalOutlinedIcon from '@mui/icons-material/TerminalOutlined';
import { useClaudeTokens } from '@/shared/styles/ThemeContext';

export interface SourceEvidenceRef {
  id: string;
  type: 'file' | 'folder' | 'output' | 'candidate' | 'tool' | 'terminal' | 'test' | 'browser' | 'web' | 'memory' | 'skill' | 'evidence' | 'unknown';
  label: string;
  status?: string;
  url?: string;
  metadata?: Record<string, unknown>;
}

function asArray(value: any): any[] {
  if (!value) return [];
  return Array.isArray(value) ? value : [value];
}

function shortLabel(value: any, fallback: string): string {
  const raw = String(value || fallback || '').trim();
  if (!raw) return fallback;
  return raw.length > 96 ? `${raw.slice(0, 93)}…` : raw;
}

function inferType(item: any): SourceEvidenceRef['type'] {
  const raw = String(item?.type || item?.kind || item?.source_type || item?.subsystem || '').toLowerCase();
  if (raw.includes('web') || raw.includes('url')) return 'web';
  if (raw.includes('file')) return 'file';
  if (raw.includes('folder') || raw.includes('directory')) return 'folder';
  if (raw.includes('terminal') || raw.includes('shell')) return 'terminal';
  if (raw.includes('test')) return 'test';
  if (raw.includes('browser')) return 'browser';
  if (raw.includes('tool')) return 'tool';
  if (raw.includes('skill')) return 'skill';
  if (raw.includes('memory')) return 'memory';
  if (raw.includes('candidate')) return 'candidate';
  if (raw.includes('output')) return 'output';
  if (raw.includes('evidence')) return 'evidence';
  return 'unknown';
}

function normalizeRef(item: any, idx: number, fallbackType?: SourceEvidenceRef['type']): SourceEvidenceRef | null {
  if (item == null) return null;
  if (typeof item === 'string') {
    return { id: item, type: fallbackType || 'evidence', label: shortLabel(item, `Evidence ${idx + 1}`) };
  }
  if (typeof item !== 'object') return null;
  const type = fallbackType || inferType(item);
  const id = String(item.id || item.evidence_id || item.ref_id || item.source_id || item.url || item.path || item.title || `${type}-${idx}`);
  const label = shortLabel(item.label || item.title || item.name || item.url || item.path || item.summary || id, `Evidence ${idx + 1}`);
  const url = typeof item.url === 'string' ? item.url : undefined;
  const status = typeof item.status === 'string' ? item.status : undefined;
  return { id, type, label, url, status, metadata: item };
}

export function extractSourceEvidenceRefs(message: any): SourceEvidenceRef[] {
  const refs: SourceEvidenceRef[] = [];
  const pushMany = (items: any[], type?: SourceEvidenceRef['type']) => {
    for (const item of items) {
      const ref = normalizeRef(item, refs.length, type);
      if (ref && !refs.some((r) => r.id === ref.id && r.type === ref.type)) refs.push(ref);
    }
  };

  pushMany(asArray(message?.sources));
  pushMany(asArray(message?.citations), 'web');
  pushMany(asArray(message?.source_refs));
  pushMany(asArray(message?.file_refs), 'file');
  pushMany(asArray(message?.browser_refs), 'browser');
  pushMany(asArray(message?.output_refs), 'output');
  pushMany(asArray(message?.tool_refs), 'tool');
  pushMany(asArray(message?.evidence_refs || message?.evidenceRefs), 'evidence');
  pushMany(asArray(message?.validation_refs || message?.validationRefs), 'test');

  const trace = message?.process_trace_turn || message?.process_trace_turn_container || message?.trace_turn || message?.turnTrace;
  const items = asArray(trace?.items || message?.traceItems || message?.process_trace_items);
  for (const item of items) {
    pushMany(asArray(item?.evidence_refs || item?.evidenceRefs), 'evidence');
    pushMany(asArray(item?.source_refs || item?.sources), undefined);
    const details = item?.details || {};
    pushMany(asArray(details?.evidence_refs || details?.evidenceRefs), 'evidence');
    pushMany(asArray(details?.source_refs || details?.sources), undefined);
    if (item?.subsystem === 'ToolCore' || String(item?.kind || '').toLowerCase() === 'tool') {
      const ref = normalizeRef({ id: item.trace_id || item.id, label: item.title || item.summary, type: 'tool', status: item.status }, refs.length, 'tool');
      if (ref && ref.id !== 'undefined' && !refs.some((r) => r.id === ref.id && r.type === ref.type)) refs.push(ref);
    }
  }

  return refs;
}

function iconForType(type: SourceEvidenceRef['type']) {
  const sx = { fontSize: 13 };
  if (type === 'web') return <PublicOutlinedIcon sx={sx} />;
  if (type === 'file' || type === 'folder') return <InsertDriveFileOutlinedIcon sx={sx} />;
  if (type === 'terminal' || type === 'test') return <TerminalOutlinedIcon sx={sx} />;
  if (type === 'tool') return <BuildOutlinedIcon sx={sx} />;
  return <FactCheckOutlinedIcon sx={sx} />;
}

const SourceEvidencePanel: React.FC<{ message: any; compact?: boolean }> = ({ message, compact = false }) => {
  const c = useClaudeTokens();
  const [open, setOpen] = useState(false);
  const refs = useMemo(() => extractSourceEvidenceRefs(message), [message]);
  if (refs.length === 0) return null;

  return (
    <Box sx={{ mt: compact ? 0.6 : 0.8, pt: 0.6, borderTop: `1px solid ${c.border.subtle}` }}>
      <Box onClick={() => setOpen((v) => !v)} sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.45, cursor: 'pointer' }}>
        <FactCheckOutlinedIcon sx={{ fontSize: 14, color: c.status.success }} />
        <Typography sx={{ fontSize: '0.68rem', color: c.text.muted, fontWeight: 650 }}>
          Sources / Evidence · {refs.length}
        </Typography>
        <ExpandMoreIcon sx={{ fontSize: 14, color: c.text.tertiary, transform: open ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 120ms ease' }} />
      </Box>
      <Collapse in={open}>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.45, mt: 0.55 }}>
          {refs.slice(0, 12).map((ref, idx) => (
            <Tooltip key={`${ref.type}-${ref.id}-${idx}`} title={ref.url || ref.id} arrow>
              <Chip
                size="small"
                icon={iconForType(ref.type) as React.ReactElement}
                label={`${ref.type}:${ref.label}${ref.status ? ` · ${ref.status}` : ''}`}
                sx={{ height: 22, maxWidth: 260, fontSize: '0.65rem', color: c.status.success, bgcolor: `${c.status.success}12`, '& .MuiChip-icon': { color: c.status.success }, '& .MuiChip-label': { overflow: 'hidden', textOverflow: 'ellipsis' } }}
              />
            </Tooltip>
          ))}
          {refs.length > 12 && <Typography sx={{ color: c.text.ghost, fontSize: '0.66rem' }}>+{refs.length - 12}</Typography>}
        </Box>
      </Collapse>
    </Box>
  );
};

export default SourceEvidencePanel;
