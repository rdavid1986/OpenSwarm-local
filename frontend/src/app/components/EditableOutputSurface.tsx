import React from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import BrushOutlinedIcon from '@mui/icons-material/BrushOutlined';
import DifferenceIcon from '@mui/icons-material/Difference';
import type { Output, OutputIterationRecord } from '@/shared/state/outputsSlice';
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
  const hasCandidate = Boolean(candidateIteration);
  const stableProtected = previewMode === 'stable';

  return (
    <Box
      data-preview-control="true"
      onPointerDown={(e) => e.stopPropagation()}
      sx={{
        position: 'absolute',
        left: 12,
        bottom: 12,
        zIndex: 8,
        maxWidth: 460,
        px: 1,
        py: 0.75,
        borderRadius: 1.5,
        border: `1px solid ${hasCandidate ? c.status.warning : c.border.subtle}`,
        bgcolor: `${c.bg.surface}F2`,
        boxShadow: c.shadow.md,
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.65, flexWrap: 'wrap' }}>
        <BrushOutlinedIcon sx={{ fontSize: 15, color: hasCandidate ? c.status.warning : c.text.tertiary }} />
        <Typography sx={{ color: c.text.secondary, fontSize: '0.7rem', fontWeight: 700 }}>
          Canvas
        </Typography>
        <Chip size="small" label={stableProtected ? 'stable protected' : 'candidate'} sx={{ height: 20, fontSize: '0.62rem', color: stableProtected ? c.status.success : c.status.warning, bgcolor: stableProtected ? `${c.status.success}12` : `${c.status.warning}12` }} />
        {hasCandidate && <Chip size="small" label={`${changedCount} changed`} sx={{ height: 20, fontSize: '0.62rem' }} />}
      </Box>
      <Typography sx={{ color: c.text.tertiary, fontSize: '0.65rem', mt: 0.35, lineHeight: 1.35 }}>
        {hasCandidate
          ? 'Review candidate changes before accepting. Stable output is not modified until Accept.'
          : 'Stable output is read-only here. Targeted edits go through Refine/candidate flow.'}
      </Typography>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 0.55 }}>
        <Tooltip title={onRefine ? 'Prepare a targeted change through the existing refinement flow.' : 'No source Swarm/refinement handler connected for this output.'}>
          <span><Button size="small" disabled={!onRefine} onClick={onRefine} sx={{ fontSize: '0.66rem', textTransform: 'none' }}>Targeted change</Button></span>
        </Tooltip>
        <Button size="small" disabled={!onCompare} onClick={onCompare} startIcon={<DifferenceIcon sx={{ fontSize: 13 }} />} sx={{ fontSize: '0.66rem', textTransform: 'none' }}>Compare</Button>
        <Button size="small" disabled={!hasCandidate || !onOpenDiff} onClick={onOpenDiff} sx={{ fontSize: '0.66rem', textTransform: 'none' }}>Diff</Button>
        <Button size="small" disabled={!hasCandidate || !onAccept || actionLoading} onClick={onAccept} sx={{ fontSize: '0.66rem', textTransform: 'none', color: c.status.success }}>Accept</Button>
        <Button size="small" disabled={!hasCandidate || !onDiscard || actionLoading} onClick={onDiscard} sx={{ fontSize: '0.66rem', textTransform: 'none', color: c.status.error }}>Discard</Button>
      </Box>
      <Typography sx={{ color: c.text.ghost, fontSize: '0.6rem', mt: 0.35, fontFamily: c.font.mono }} noWrap>
        output:{output.id}{candidateIteration?.iteration_id ? ` · candidate:${candidateIteration.iteration_id}` : ''}
      </Typography>
    </Box>
  );
};

export default EditableOutputSurface;
