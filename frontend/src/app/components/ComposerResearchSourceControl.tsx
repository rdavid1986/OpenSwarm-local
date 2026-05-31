import React from 'react';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import PublicOutlinedIcon from '@mui/icons-material/PublicOutlined';
import FolderOutlinedIcon from '@mui/icons-material/FolderOutlined';
import InsertDriveFileOutlinedIcon from '@mui/icons-material/InsertDriveFileOutlined';
import AdsClickOutlinedIcon from '@mui/icons-material/AdsClickOutlined';
import FactCheckOutlinedIcon from '@mui/icons-material/FactCheckOutlined';
import type { UnifiedComposerResearchSourceRef } from '@/shared/types/unifiedComposer';
import { useClaudeTokens } from '@/shared/styles/ThemeContext';

interface Props {
  sources: UnifiedComposerResearchSourceRef[];
  visible: boolean;
  onToggleSource?: (id: string) => void;
}

function iconForSource(kind: UnifiedComposerResearchSourceRef['kind']) {
  const sx = { fontSize: 13 };
  if (kind === 'public_web') return <PublicOutlinedIcon sx={sx} />;
  if (kind === 'uploaded_or_attached_files') return <InsertDriveFileOutlinedIcon sx={sx} />;
  if (kind === 'browser_refs') return <AdsClickOutlinedIcon sx={sx} />;
  if (kind === 'evidence_refs') return <FactCheckOutlinedIcon sx={sx} />;
  return <FolderOutlinedIcon sx={sx} />;
}

const ComposerResearchSourceControl: React.FC<Props> = ({ sources, visible, onToggleSource }) => {
  const c = useClaudeTokens();
  if (!visible || sources.length === 0) return null;

  return (
    <Box sx={{ mx: 1.5, mb: 0.65, px: 1, py: 0.75, borderRadius: 1.5, border: `1px solid ${c.status.warning}33`, bgcolor: `${c.status.warning}0A` }}>
      <Typography sx={{ color: c.status.warning, fontSize: '0.68rem', fontWeight: 700, mb: 0.5 }}>
        Research sources · selection only, no web/tools run
      </Typography>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
        {sources.map((source) => {
          const selected = source.state === 'selected';
          const approval = source.state === 'requires_approval';
          const disabled = source.state === 'disabled' || source.state === 'not_configured' || source.state === 'unsupported';
          const color = selected ? c.status.success : approval ? c.status.warning : c.text.tertiary;
          const tooltip = source.disabled_reason?.message
            || (approval ? 'Requires explicit approval before any research runtime can run.' : source.label);
          return (
            <Tooltip key={source.id} title={tooltip} arrow>
              <span>
                <Chip
                  size="small"
                  icon={iconForSource(source.kind) as React.ReactElement}
                  label={`${source.label}${approval ? ' · approval' : ''}`}
                  onClick={() => !disabled && onToggleSource?.(source.id)}
                  sx={{
                    height: 23,
                    fontSize: '0.66rem',
                    color,
                    bgcolor: `${color}12`,
                    opacity: disabled ? 0.55 : 1,
                    cursor: disabled ? 'not-allowed' : 'pointer',
                    '& .MuiChip-icon': { color },
                  }}
                />
              </span>
            </Tooltip>
          );
        })}
      </Box>
    </Box>
  );
};

export default ComposerResearchSourceControl;
