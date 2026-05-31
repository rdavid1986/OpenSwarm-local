import React, { useMemo, useState } from 'react';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Collapse from '@mui/material/Collapse';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import AutoFixHighOutlinedIcon from '@mui/icons-material/AutoFixHighOutlined';
import type { UnifiedComposerState } from '@/shared/types/unifiedComposer';
import { useClaudeTokens } from '@/shared/styles/ThemeContext';

interface Props {
  state?: UnifiedComposerState | null;
  compact?: boolean;
  title?: string;
}

function short(value: unknown, fallback = ''): string {
  const raw = String(value ?? fallback).trim();
  if (!raw) return fallback;
  if (/token|secret|password|cookie|bearer|private[_-]?key/i.test(raw)) return '[redacted]';
  return raw.length > 96 ? `${raw.slice(0, 93)}…` : raw;
}

const PromptSkillAuthoringPanel: React.FC<Props> = ({ state, compact = false, title = 'Prompt / skill authoring' }) => {
  const c = useClaudeTokens();
  const [open, setOpen] = useState(false);

  const rows = useMemo(() => {
    const mode = String(state?.mode || '').toLowerCase();
    const isSkillMode = mode.includes('skill');
    const contextRefs = state?.context_refs || [];
    const skillRefs = contextRefs.filter((ref) => ref.kind === 'skill');
    const workspaceRefs = contextRefs.filter((ref) => ref.kind === 'workspace' || ref.kind === 'directory');
    const fileRefs = [...contextRefs.filter((ref) => ref.kind === 'file'), ...(state?.attachment_refs || [])];

    const out: Array<{ label: string; values: string[]; tone: string }> = [
      {
        label: 'Authoring contract',
        values: [
          isSkillMode ? 'skill_builder:active' : 'skill_builder:available via /skill',
          'prompt_files:prepared',
          'project_instructions:prepared',
          'skill_candidates:policy-gated',
          'mcp_config_previews:prepared only',
        ],
        tone: c.status.info,
      },
    ];

    if (skillRefs.length) out.push({ label: 'Skill refs', values: skillRefs.map((ref) => `${short(ref.label)} · ${short(ref.source)}`), tone: c.accent.primary });
    if (workspaceRefs.length) out.push({ label: 'Workspace', values: workspaceRefs.map((ref) => short(ref.path || ref.label)), tone: c.status.success });
    if (fileRefs.length) out.push({ label: 'Prompt files', values: fileRefs.map((ref) => short((ref as any).path || ref.label)), tone: c.status.success });

    const disabled = [
      'create/edit prompt files needs a safe file writer flow',
      'install skill candidate requires existing Skill Builder policy gates',
      'MCP config preview does not activate MCP',
    ];
    out.push({ label: 'Prepared / disabled', values: disabled, tone: c.text.tertiary });

    return out;
  }, [c, state]);

  if (!state) return null;

  const total = rows.reduce((sum, row) => sum + row.values.length, 0);

  return (
    <Box sx={{ mx: compact ? 0 : 1.5, mb: compact ? 0.5 : 0.75, border: `1px solid ${c.border.subtle}`, borderRadius: 1.5, bgcolor: `${c.bg.secondary}66`, overflow: 'hidden' }}>
      <Box onClick={() => setOpen((value) => !value)} sx={{ display: 'flex', alignItems: 'center', gap: 0.75, px: 1, py: 0.55, cursor: 'pointer' }}>
        <AutoFixHighOutlinedIcon sx={{ fontSize: 14, color: c.text.tertiary }} />
        <Typography sx={{ fontSize: '0.68rem', color: c.text.secondary, fontWeight: 700, flex: 1 }}>
          {title} · {total} contract item{total === 1 ? '' : 's'}
        </Typography>
        <Tooltip title={open ? 'Hide authoring contract' : 'Show authoring contract'}>
          <IconButton size="small" sx={{ width: 20, height: 20, color: c.text.tertiary }}>
            <ExpandMoreIcon sx={{ fontSize: 16, transform: open ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 120ms ease' }} />
          </IconButton>
        </Tooltip>
      </Box>
      <Collapse in={open}>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.55, px: 1, pb: 0.85 }}>
          {rows.map((row) => (
            <Box key={row.label} sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexWrap: 'wrap' }}>
              <Typography sx={{ fontSize: '0.61rem', color: c.text.ghost, fontWeight: 800, textTransform: 'uppercase', minWidth: 104 }}>
                {row.label}
              </Typography>
              {row.values.slice(0, 8).map((value, idx) => (
                <Chip
                  key={`${row.label}-${value}-${idx}`}
                  label={value}
                  size="small"
                  sx={{ height: 20, maxWidth: 230, fontSize: '0.61rem', color: row.tone, bgcolor: `${row.tone}12`, '& .MuiChip-label': { overflow: 'hidden', textOverflow: 'ellipsis' } }}
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

export default PromptSkillAuthoringPanel;
