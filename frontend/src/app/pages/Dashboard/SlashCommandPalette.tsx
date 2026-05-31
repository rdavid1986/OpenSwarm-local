import React from 'react';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Typography from '@mui/material/Typography';
import { useClaudeTokens } from '@/shared/styles/ThemeContext';
import type { CommandPickerItem } from '@/app/components/CommandPicker';

export interface SlashCommandPreviewModel {
  command: string;
  label: string;
  description: string;
  risk: string;
  status: string;
  requiresApproval: boolean;
}

export function buildSlashCommandPreview(item: CommandPickerItem): SlashCommandPreviewModel | null {
  if (item.type !== 'slash' || item.payload?.opencode_preview !== true) return null;
  return {
    command: `/${item.command}`,
    label: item.name,
    description: item.description,
    risk: String(item.payload?.risk || 'unknown'),
    status: String(item.payload?.status || 'preview'),
    requiresApproval: item.payload?.requires_approval === true,
  };
}

export const SlashCommandPreview: React.FC<{ preview: SlashCommandPreviewModel | null }> = ({ preview }) => {
  const c = useClaudeTokens();
  if (!preview) return null;
  return (
    <Box sx={{ mx: 1.5, mt: 0.75, mb: 0.25, p: 1, borderRadius: `${c.radius.md}px`, border: `1px solid ${c.border.subtle}`, bgcolor: c.bg.elevated }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, flexWrap: 'wrap', mb: 0.5 }}>
        <Typography sx={{ color: c.text.primary, fontFamily: c.font.mono, fontSize: '0.78rem', fontWeight: 700 }}>{preview.command}</Typography>
        <Chip size="small" label="Preview only" sx={{ height: 20, fontSize: '0.65rem', color: c.status.info, bgcolor: c.status.infoBg }} />
        <Chip size="small" label="No execution" sx={{ height: 20, fontSize: '0.65rem', color: c.status.error, bgcolor: c.status.errorBg }} />
        <Chip size="small" label={`risk:${preview.risk}`} sx={{ height: 20, fontSize: '0.65rem', color: c.text.secondary, bgcolor: c.bg.secondary }} />
        {preview.requiresApproval && <Chip size="small" label="approval later" sx={{ height: 20, fontSize: '0.65rem', color: c.status.warning, bgcolor: c.status.warningBg }} />}
      </Box>
      <Typography sx={{ color: c.text.muted, fontSize: '0.74rem', lineHeight: 1.45 }}>
        {preview.description} This palette inserts text only; it does not call backend, shell, tools, MCP or models.
      </Typography>
    </Box>
  );
};
