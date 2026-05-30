import React, { useMemo, useState } from 'react';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Collapse from '@mui/material/Collapse';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import type { UnifiedComposerState } from '@/shared/types/unifiedComposer';
import { useClaudeTokens } from '@/shared/styles/ThemeContext';

interface Props {
  state: UnifiedComposerState;
  compact?: boolean;
}

const ComposerContextPreview: React.FC<Props> = ({ state, compact = false }) => {
  const c = useClaudeTokens();
  const [open, setOpen] = useState(false);
  const sections = useMemo(() => {
    const rows: Array<{ label: string; values: string[]; color?: string }> = [];
    const context = state.context_refs.filter((ref) => !ref.disabled_reason);
    const disabled = [
      ...state.disabled_reasons.map((r) => r.message),
      ...state.context_refs.map((r) => r.disabled_reason?.message).filter(Boolean) as string[],
      state.voice.disabled_reason?.message,
      ...(state.warnings || []),
    ].filter(Boolean) as string[];
    if (context.length) rows.push({ label: 'Context', values: context.map((r) => `${r.kind}:${r.label}`), color: c.accent.primary });
    if (state.attachment_refs.length) rows.push({ label: 'Files', values: state.attachment_refs.map((r) => r.label), color: c.status.success });
    if (state.selected_ui_elements.length) rows.push({ label: 'UI', values: state.selected_ui_elements.map((r) => r.label), color: '#3b82f6' });
    if (state.tools_selected.length) rows.push({ label: 'Tools', values: state.tools_selected.map((r) => r.label), color: c.status.info });
    if (disabled.length) rows.push({ label: 'Disabled', values: disabled, color: c.text.tertiary });
    return rows;
  }, [c, state]);

  const totalRefs = state.context_refs.length + state.attachment_refs.length + state.selected_ui_elements.length + state.tools_selected.length;
  if (!totalRefs && !state.disabled_reasons.length && !state.voice.disabled_reason && !state.mode && !state.model) return null;

  return (
    <Box sx={{ mx: 1.5, mb: compact ? 0.5 : 0.75, border: `1px solid ${c.border.subtle}`, borderRadius: 1.5, bgcolor: `${c.bg.secondary}88`, overflow: 'hidden' }}>
      <Box
        onClick={() => setOpen((v) => !v)}
        sx={{ display: 'flex', alignItems: 'center', gap: 0.75, px: 1, py: 0.5, cursor: 'pointer' }}
      >
        <InfoOutlinedIcon sx={{ fontSize: 14, color: c.text.tertiary }} />
        <Typography sx={{ fontSize: '0.68rem', color: c.text.secondary, fontWeight: 650, flex: 1 }}>
          Request context · {state.mode || 'mode'} · {state.model || 'model'} · {totalRefs} ref{totalRefs === 1 ? '' : 's'}
        </Typography>
        <Tooltip title={open ? 'Hide request preview' : 'Show request preview'}>
          <IconButton size="small" sx={{ width: 20, height: 20, color: c.text.tertiary }}>
            <ExpandMoreIcon sx={{ fontSize: 16, transform: open ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 120ms ease' }} />
          </IconButton>
        </Tooltip>
      </Box>
      <Collapse in={open}>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5, px: 1, pb: 0.75 }}>
          {sections.map((section) => (
            <Box key={section.label} sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexWrap: 'wrap' }}>
              <Typography sx={{ fontSize: '0.62rem', color: c.text.ghost, fontWeight: 700, textTransform: 'uppercase', minWidth: 58 }}>
                {section.label}
              </Typography>
              {section.values.slice(0, 8).map((value, idx) => (
                <Chip
                  key={`${section.label}-${value}-${idx}`}
                  label={value}
                  size="small"
                  sx={{ height: 20, maxWidth: 180, fontSize: '0.62rem', color: section.color || c.text.secondary, bgcolor: `${section.color || c.text.tertiary}12`, '& .MuiChip-label': { overflow: 'hidden', textOverflow: 'ellipsis' } }}
                />
              ))}
              {section.values.length > 8 && (
                <Typography sx={{ fontSize: '0.62rem', color: c.text.ghost }}>+{section.values.length - 8}</Typography>
              )}
            </Box>
          ))}
        </Box>
      </Collapse>
    </Box>
  );
};

export default ComposerContextPreview;
