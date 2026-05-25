import React from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import IconButton from '@mui/material/IconButton';
import DifferenceIcon from '@mui/icons-material/Difference';

export type OutputDiffRow = {
  path: string;
  status: 'added' | 'removed' | 'modified' | 'unchanged';
  before: string;
  after: string;
};

interface OutputDiffPanelProps {
  open: boolean;
  rows: OutputDiffRow[];
  changedCount: number;
  onClose: () => void;
  c: any;
}

const OutputDiffPanel: React.FC<OutputDiffPanelProps> = ({
  open,
  rows,
  changedCount,
  onClose,
  c,
}) => {
  if (!open) return null;

  return (
    <Box
      data-preview-control="true"
      onPointerDown={(e) => e.stopPropagation()}
      sx={{
        position: 'absolute',
        top: 12,
        right: 12,
        width: 420,
        maxWidth: 'calc(100% - 24px)',
        maxHeight: 'calc(100% - 24px)',
        zIndex: 8,
        display: 'flex',
        flexDirection: 'column',
        border: `1px solid ${c.border.medium}`,
        borderRadius: `${c.radius.lg}px`,
        bgcolor: c.bg.surface,
        boxShadow: c.shadow.lg,
        overflow: 'hidden',
      }}
    >
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          px: 1.25,
          py: 0.85,
          borderBottom: `1px solid ${c.border.subtle}`,
          bgcolor: c.bg.secondary,
        }}
      >
        <DifferenceIcon sx={{ fontSize: 16, color: c.text.muted }} />
        <Typography sx={{ color: c.text.primary, fontWeight: 600, fontSize: '0.78rem' }}>
          Candidate File Diff
        </Typography>
        <Box sx={{ flex: 1 }} />
        <Typography sx={{ color: c.text.ghost, fontSize: '0.68rem', fontFamily: c.font.mono }}>
          {changedCount} changed
        </Typography>
        <IconButton
          size="small"
          data-preview-control="true"
          onClick={onClose}
          sx={{ color: c.text.tertiary, p: 0.25 }}
        >
          <Typography sx={{ fontSize: '0.8rem' }}>×</Typography>
        </IconButton>
      </Box>

      <Box
        sx={{
          overflow: 'auto',
          p: 1,
          display: 'flex',
          flexDirection: 'column',
          gap: 0.75,
          '&::-webkit-scrollbar': { width: 5, height: 5 },
          '&::-webkit-scrollbar-track': { background: 'transparent' },
          '&::-webkit-scrollbar-thumb': {
            background: c.border.medium,
            borderRadius: 3,
            '&:hover': { background: c.border.strong },
          },
        }}
      >
        {rows.length === 0 || changedCount === 0 ? (
          <Typography sx={{ color: c.text.ghost, fontSize: '0.76rem' }}>
            No file changes detected yet. The candidate currently matches the stable output.
          </Typography>
        ) : (
          rows
            .filter((row) => row.status !== 'unchanged')
            .map((row) => (
              <Box
                key={row.path}
                sx={{
                  border: `1px solid ${c.border.subtle}`,
                  borderRadius: `${c.radius.md}px`,
                  overflow: 'hidden',
                  bgcolor: c.bg.page,
                }}
              >
                <Box
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 0.75,
                    px: 1,
                    py: 0.65,
                    borderBottom: `1px solid ${c.border.subtle}`,
                    bgcolor: c.bg.surface,
                  }}
                >
                  <Typography sx={{ color: c.text.primary, fontSize: '0.72rem', fontFamily: c.font.mono, flex: 1 }}>
                    {row.path}
                  </Typography>
                  <Typography
                    sx={{
                      color: row.status === 'added' ? c.status.success : row.status === 'removed' ? c.status.error : c.accent.primary,
                      fontSize: '0.65rem',
                      fontFamily: c.font.mono,
                      textTransform: 'uppercase',
                    }}
                  >
                    {row.status}
                  </Typography>
                </Box>
                <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr' }}>
                  <Box sx={{ p: 0.85, borderRight: `1px solid ${c.border.subtle}` }}>
                    <Typography sx={{ color: c.status.error, fontSize: '0.62rem', mb: 0.5, fontFamily: c.font.mono }}>
                      Before
                    </Typography>
                    <Box component="pre" sx={{ m: 0, color: c.text.muted, fontSize: '0.64rem', fontFamily: c.font.mono, whiteSpace: 'pre-wrap', wordBreak: 'break-word', maxHeight: 160, overflow: 'auto' }}>
                      {row.before || '(empty)'}
                    </Box>
                  </Box>
                  <Box sx={{ p: 0.85 }}>
                    <Typography sx={{ color: c.status.success, fontSize: '0.62rem', mb: 0.5, fontFamily: c.font.mono }}>
                      After
                    </Typography>
                    <Box component="pre" sx={{ m: 0, color: c.text.muted, fontSize: '0.64rem', fontFamily: c.font.mono, whiteSpace: 'pre-wrap', wordBreak: 'break-word', maxHeight: 160, overflow: 'auto' }}>
                      {row.after || '(empty)'}
                    </Box>
                  </Box>
                </Box>
              </Box>
            ))
        )}
      </Box>
    </Box>
  );
};

export default OutputDiffPanel;
