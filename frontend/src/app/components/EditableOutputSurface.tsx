import React, { useState } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Tooltip from '@mui/material/Tooltip';
import BrushOutlinedIcon from '@mui/icons-material/BrushOutlined';
import DifferenceIcon from '@mui/icons-material/Difference';
import { Output, OutputIterationRecord } from '@/shared/state/outputsSlice';
import { useClaudeTokens } from '@/shared/styles/ThemeContext';

interface Props {
  output: Output;
  previewMode: 'stable' | 'candidate';
  candidateIteration: OutputIterationRecord | null;
  changedCount: number;
  onRefine?: () => void;
  onCompare?: () => void;
  onOpenDiff?: () => void;
  onAccept?: () => void;
  onDiscard?: () => void;
  actionLoading?: boolean;
}

const EditableOutputSurface: React.FC<Props> = ({
  output,
  previewMode,
  candidateIteration,
  changedCount,
  onRefine,
  onCompare,
  onOpenDiff,
  onAccept,
  onDiscard,
  actionLoading = false,
}) => {
  const c = useClaudeTokens();
  const [open, setOpen] = useState(false);
  const hasCandidate = Boolean(candidateIteration);
  const stableProtected = previewMode === 'stable';

  const runAction = (handler?: () => void) => {
    if (!handler || actionLoading) return;
    handler();
    setOpen(false);
  };

  return (
    <Box
      data-preview-control="true"
      onPointerDown={(e) => e.stopPropagation()}
      sx={{
        position: 'relative',
        display: 'inline-flex',
        alignItems: 'center',
        flexShrink: 0,
      }}
    >
      <Button
        size="small"
        data-preview-control="true"
        onClick={(e) => {
          e.stopPropagation();
          setOpen((value) => !value);
        }}
        startIcon={<BrushOutlinedIcon sx={{ fontSize: 14 }} />}
        sx={{
          minWidth: 0,
          px: 0.9,
          py: 0.25,
          borderRadius: `${c.radius.md}px`,
          color: hasCandidate ? c.status.warning : c.text.secondary,
          border: `1px solid ${hasCandidate ? c.status.warning : c.border.medium}`,
          bgcolor: open ? c.bg.muted : c.bg.surface,
          fontSize: '0.68rem',
          textTransform: 'none',
          cursor: 'pointer',
          '& .MuiButton-startIcon': { mr: 0.35 },
          '&:hover': { bgcolor: c.bg.muted },
        }}
      >
        Canvas{hasCandidate && changedCount > 0 ? ` · ${changedCount}` : ''}
      </Button>

      {open && (
        <Box
          sx={{
            position: 'absolute',
            top: 'calc(100% + 8px)',
            right: 0,
            zIndex: 80,
            width: 430,
            maxWidth: 'calc(100vw - 48px)',
            px: 1,
            py: 0.85,
            borderRadius: 1.5,
            border: `1px solid ${hasCandidate ? c.status.warning : c.border.subtle}`,
            bgcolor: `${c.bg.surface}F7`,
            boxShadow: c.shadow.lg,
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.65, flexWrap: 'wrap' }}>
            <BrushOutlinedIcon sx={{ fontSize: 15, color: hasCandidate ? c.status.warning : c.text.tertiary }} />
            <Typography sx={{ color: c.text.secondary, fontSize: '0.7rem', fontWeight: 700 }}>
              Canvas
            </Typography>
            <Chip
              size="small"
              label={stableProtected ? 'stable protected' : 'candidate'}
              sx={{
                height: 20,
                fontSize: '0.62rem',
                color: stableProtected ? c.status.success : c.status.warning,
                bgcolor: stableProtected ? `${c.status.success}12` : `${c.status.warning}12`,
              }}
            />
            {hasCandidate && <Chip size="small" label={`${changedCount} changed`} sx={{ height: 20, fontSize: '0.62rem' }} />}
          </Box>

          <Typography sx={{ color: c.text.tertiary, fontSize: '0.65rem', mt: 0.45, lineHeight: 1.35 }}>
            {hasCandidate
              ? 'Review candidate changes before accepting. Stable output is not modified until Accept.'
              : 'Stable output is read-only here. Refinements go through the Refine/candidate flow.'}
          </Typography>

          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 0.65 }}>
            <Tooltip title={onRefine ? 'Prepare a refinement through the existing candidate flow.' : 'No source Swarm/refinement handler connected for this output.'}>
              <span>
                <Button size="small" disabled={!onRefine || actionLoading} onClick={() => runAction(onRefine)} sx={{ fontSize: '0.66rem', textTransform: 'none' }}>
                  Refine
                </Button>
              </span>
            </Tooltip>
            <Button size="small" disabled={!onCompare || actionLoading} onClick={() => runAction(onCompare)} startIcon={<DifferenceIcon sx={{ fontSize: 13 }} />} sx={{ fontSize: '0.66rem', textTransform: 'none' }}>Compare</Button>
            <Button size="small" disabled={!onOpenDiff || actionLoading} onClick={() => runAction(onOpenDiff)} startIcon={<DifferenceIcon sx={{ fontSize: 13 }} />} sx={{ fontSize: '0.66rem', textTransform: 'none' }}>Diff</Button>
            <Button size="small" disabled={!onAccept || actionLoading} onClick={() => runAction(onAccept)} sx={{ fontSize: '0.66rem', textTransform: 'none', color: c.status.success }}>Accept</Button>
            <Button size="small" disabled={!onDiscard || actionLoading} onClick={() => runAction(onDiscard)} sx={{ fontSize: '0.66rem', textTransform: 'none', color: c.status.error }}>Discard</Button>
          </Box>

          <Typography sx={{ color: c.text.tertiary, fontSize: '0.62rem', mt: 0.45, fontFamily: c.font.mono, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            output:{output.id}
          </Typography>
        </Box>
      )}
    </Box>
  );
};

export default EditableOutputSurface;
