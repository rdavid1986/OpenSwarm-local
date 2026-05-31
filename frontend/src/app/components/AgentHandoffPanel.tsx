import React, { useMemo, useState } from 'react';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Collapse from '@mui/material/Collapse';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import CallSplitOutlinedIcon from '@mui/icons-material/CallSplitOutlined';
import { useClaudeTokens } from '@/shared/styles/ThemeContext';

interface Props {
  processTraceItems?: unknown[];
  title?: string;
  compact?: boolean;
}

function safe(value: unknown, fallback = ''): string {
  const raw = String(value ?? fallback).trim();
  if (!raw) return fallback;
  if (/token|secret|password|cookie|bearer|private[_-]?key/i.test(raw)) return '[redacted]';
  return raw.length > 120 ? `${raw.slice(0, 117)}…` : raw;
}

const AgentHandoffPanel: React.FC<Props> = ({ processTraceItems = [], title = 'Agent handoffs', compact = false }) => {
  const c = useClaudeTokens();
  const [open, setOpen] = useState(false);

  const handoffs = useMemo(() => {
    return (processTraceItems || [])
      .map((raw) => raw as any)
      .filter((item) => {
        const joined = `${item?.subsystem || ''} ${item?.kind || ''} ${item?.title || ''}`.toLowerCase();
        return joined.includes('handoff');
      })
      .map((item, idx) => ({
        id: safe(item.trace_id || item.id || `handoff-${idx}`),
        title: safe(item.title || 'Handoff'),
        summary: safe(item.summary || item.details?.handoff || item.details?.reason || 'Context handoff recorded.'),
        status: safe(item.status || 'recorded'),
        receiver: safe(item.related_agent_id || item.related_miniagent_id || item.details?.receiver || item.details?.target || 'receiver not provided'),
        evidenceCount: Array.isArray(item.evidence_refs) ? item.evidence_refs.length : 0,
      }));
  }, [processTraceItems]);

  if (!handoffs.length) return null;

  return (
    <Box sx={{ mx: compact ? 0 : 1.5, mb: compact ? 0.5 : 0.75, border: `1px solid ${c.border.subtle}`, borderRadius: 1.5, bgcolor: `${c.bg.secondary}66`, overflow: 'hidden' }}>
      <Box onClick={() => setOpen((value) => !value)} sx={{ display: 'flex', alignItems: 'center', gap: 0.75, px: 1, py: 0.55, cursor: 'pointer' }}>
        <CallSplitOutlinedIcon sx={{ fontSize: 14, color: c.text.tertiary }} />
        <Typography sx={{ fontSize: '0.68rem', color: c.text.secondary, fontWeight: 700, flex: 1 }}>
          {title} · {handoffs.length}
        </Typography>
        <Tooltip title={open ? 'Hide handoffs' : 'Show handoffs'}>
          <IconButton size="small" sx={{ width: 20, height: 20, color: c.text.tertiary }}>
            <ExpandMoreIcon sx={{ fontSize: 16, transform: open ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 120ms ease' }} />
          </IconButton>
        </Tooltip>
      </Box>
      <Collapse in={open}>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.55, px: 1, pb: 0.85 }}>
          {handoffs.slice(0, 8).map((handoff) => (
            <Box key={handoff.id} sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexWrap: 'wrap' }}>
              <Typography sx={{ fontSize: '0.61rem', color: c.text.ghost, fontWeight: 800, textTransform: 'uppercase', minWidth: 76 }}>
                Handoff
              </Typography>
              <Chip size="small" label={handoff.title} sx={{ height: 20, maxWidth: 190, fontSize: '0.61rem', color: c.status.info, bgcolor: `${c.status.info}12`, '& .MuiChip-label': { overflow: 'hidden', textOverflow: 'ellipsis' } }} />
              <Chip size="small" label={`to:${handoff.receiver}`} sx={{ height: 20, maxWidth: 180, fontSize: '0.61rem', color: c.accent.primary, bgcolor: `${c.accent.primary}12`, '& .MuiChip-label': { overflow: 'hidden', textOverflow: 'ellipsis' } }} />
              <Chip size="small" label={handoff.status} sx={{ height: 20, fontSize: '0.61rem', color: c.status.success, bgcolor: `${c.status.success}12` }} />
              {handoff.evidenceCount > 0 && <Chip size="small" label={`evidence:${handoff.evidenceCount}`} sx={{ height: 20, fontSize: '0.61rem', color: c.status.success, bgcolor: `${c.status.success}12` }} />}
              <Typography sx={{ fontSize: '0.64rem', color: c.text.secondary, flexBasis: '100%', pl: 10.5 }}>
                {handoff.summary}
              </Typography>
            </Box>
          ))}
          {handoffs.length > 8 && <Typography sx={{ fontSize: '0.62rem', color: c.text.ghost }}>+{handoffs.length - 8} more handoffs</Typography>}
        </Box>
      </Collapse>
    </Box>
  );
};

export default AgentHandoffPanel;
