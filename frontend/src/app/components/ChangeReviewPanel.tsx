import React, { useMemo, useState } from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Collapse from '@mui/material/Collapse';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import DifferenceIcon from '@mui/icons-material/Difference';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import FactCheckOutlinedIcon from '@mui/icons-material/FactCheckOutlined';
import SourceEvidencePanel from './SourceEvidencePanel';
import { useClaudeTokens } from '@/shared/styles/ThemeContext';

export interface ChangeReviewModel {
  outputId?: string | null;
  candidateIterationId?: string | null;
  status?: string | null;
  filesChanged: string[];
  diffSummary?: Record<string, any> | null;
  tests: string[];
  evidenceRefs: string[];
  validationRefs: string[];
  requestedChange?: string | null;
}

function asArray(value: any): any[] {
  if (!value) return [];
  return Array.isArray(value) ? value : [value];
}

function diffFiles(summary: any): string[] {
  if (!summary || typeof summary !== 'object') return [];
  const direct = asArray(summary.files_changed || summary.changed_files || summary.files).map(String);
  if (direct.length) return direct;
  return Object.entries(summary)
    .filter(([, value]) => value && typeof value === 'object')
    .map(([key]) => key);
}

export function extractChangeReviewModel(source: any): ChangeReviewModel | null {
  const trace = source?.refinement_execution_trace || source?.refinementExecutionTrace || source?.change_review || source?.changeReview || source?.diff_review;
  const diffSummary = source?.diff_summary || source?.diffSummary || trace?.diff_summary || trace?.diffSummary || null;
  const outputId = source?.output_id || source?.outputId || source?.target_output_id || source?.targetOutputId || trace?.output_id || trace?.targetOutputId || null;
  const candidateIterationId = source?.candidate_iteration_id || source?.candidateIterationId || source?.iteration_id || source?.iterationId || trace?.candidate_iteration_id || trace?.iteration_id || null;
  const filesChanged = [
    ...asArray(source?.files_changed || source?.filesChanged || trace?.files_changed || trace?.filesChanged).map(String),
    ...diffFiles(diffSummary),
  ].filter(Boolean);
  const evidenceRefs = asArray(source?.evidence_refs || source?.evidenceRefs || trace?.evidence_refs || trace?.evidenceRefs).map(String);
  const validationRefs = asArray(source?.validation_refs || source?.validationRefs || trace?.validation_refs || trace?.validationRefs).map(String);
  const tests = asArray(source?.tests || source?.tests_executed || source?.testsExecuted || trace?.tests || trace?.tests_executed).map(String);
  const status = source?.status || trace?.status || (candidateIterationId ? 'candidate' : null);
  const requestedChange = source?.requested_change || source?.requestedChange || trace?.requested_change || trace?.requestedChange || null;
  const hasRealReview = outputId || candidateIterationId || filesChanged.length || evidenceRefs.length || validationRefs.length || tests.length || diffSummary;
  if (!hasRealReview) return null;
  return {
    outputId,
    candidateIterationId,
    status,
    filesChanged: Array.from(new Set(filesChanged)),
    diffSummary,
    tests,
    evidenceRefs,
    validationRefs,
    requestedChange,
  };
}

interface Props {
  source: any;
  compact?: boolean;
  onOpenPreview?: () => void;
  onCompare?: () => void;
  onAccept?: () => void;
  onDiscard?: () => void;
  onRequestAdjustment?: () => void;
  actionLoading?: boolean;
}

const ChangeReviewPanel: React.FC<Props> = ({ source, compact = false, onOpenPreview, onCompare, onAccept, onDiscard, onRequestAdjustment, actionLoading }) => {
  const c = useClaudeTokens();
  const [open, setOpen] = useState(false);
  const model = useMemo(() => extractChangeReviewModel(source), [source]);
  if (!model) return null;

  const canAccept = Boolean(onAccept && model.candidateIterationId && model.status !== 'accepted' && model.status !== 'discarded');
  const canDiscard = Boolean(onDiscard && model.candidateIterationId && model.status !== 'accepted' && model.status !== 'discarded');

  return (
    <Box sx={{ mt: compact ? 0.7 : 1, border: `1px solid ${c.border.subtle}`, borderRadius: 1.5, bgcolor: `${c.bg.secondary}88`, overflow: 'hidden' }}>
      <Box onClick={() => setOpen((v) => !v)} sx={{ display: 'flex', alignItems: 'center', gap: 0.6, px: 1, py: 0.6, cursor: 'pointer' }}>
        <DifferenceIcon sx={{ fontSize: 15, color: c.accent.primary }} />
        <Typography sx={{ color: c.text.secondary, fontSize: '0.7rem', fontWeight: 700, flex: 1 }}>
          Change review · {model.status || 'review'}{model.filesChanged.length ? ` · ${model.filesChanged.length} files` : ''}
        </Typography>
        <ExpandMoreIcon sx={{ fontSize: 15, color: c.text.tertiary, transform: open ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 120ms ease' }} />
      </Box>
      <Collapse in={open}>
        <Box sx={{ px: 1, pb: 0.85, display: 'flex', flexDirection: 'column', gap: 0.6 }}>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.45 }}>
            {model.outputId && <Chip size="small" label={`output:${model.outputId}`} sx={{ height: 21, fontSize: '0.64rem' }} />}
            {model.candidateIterationId && <Chip size="small" label={`candidate:${model.candidateIterationId}`} sx={{ height: 21, fontSize: '0.64rem', color: c.status.warning, bgcolor: `${c.status.warning}12` }} />}
            {model.evidenceRefs.length > 0 && <Chip size="small" icon={<FactCheckOutlinedIcon sx={{ fontSize: 12 }} />} label={`${model.evidenceRefs.length} evidence`} sx={{ height: 21, fontSize: '0.64rem', color: c.status.success, bgcolor: `${c.status.success}12` }} />}
          </Box>
          {model.requestedChange && (
            <Typography sx={{ color: c.text.secondary, fontSize: '0.68rem', lineHeight: 1.35 }}>
              {String(model.requestedChange).slice(0, 180)}
            </Typography>
          )}
          {model.filesChanged.length > 0 && (
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.4 }}>
              {model.filesChanged.slice(0, 8).map((file) => (
                <Tooltip key={file} title={file}>
                  <Chip size="small" label={file.split(/[\\/]/).slice(-2).join('/')} sx={{ height: 20, maxWidth: 180, fontSize: '0.62rem', fontFamily: c.font.mono }} />
                </Tooltip>
              ))}
              {model.filesChanged.length > 8 && <Typography sx={{ color: c.text.ghost, fontSize: '0.64rem' }}>+{model.filesChanged.length - 8}</Typography>}
            </Box>
          )}
          {model.tests.length > 0 && (
            <Typography sx={{ color: c.text.tertiary, fontSize: '0.66rem' }}>
              Tests: {model.tests.slice(0, 4).join(', ')}
            </Typography>
          )}
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
            <Button size="small" disabled={!onOpenPreview} onClick={(e) => { e.stopPropagation(); onOpenPreview?.(); }} sx={{ fontSize: '0.68rem', textTransform: 'none' }}>Open Preview</Button>
            <Button size="small" disabled={!onCompare} onClick={(e) => { e.stopPropagation(); onCompare?.(); }} sx={{ fontSize: '0.68rem', textTransform: 'none' }}>Compare</Button>
            <Button size="small" disabled={!canAccept || actionLoading} onClick={(e) => { e.stopPropagation(); onAccept?.(); }} sx={{ fontSize: '0.68rem', textTransform: 'none', color: c.status.success }}>Accept</Button>
            <Button size="small" disabled={!canDiscard || actionLoading} onClick={(e) => { e.stopPropagation(); onDiscard?.(); }} sx={{ fontSize: '0.68rem', textTransform: 'none', color: c.status.error }}>Discard</Button>
            <Button size="small" disabled={!onRequestAdjustment} onClick={(e) => { e.stopPropagation(); onRequestAdjustment?.(); }} sx={{ fontSize: '0.68rem', textTransform: 'none' }}>Request adjustment</Button>
          </Box>
          <SourceEvidencePanel message={{ evidence_refs: model.evidenceRefs, validation_refs: model.validationRefs, diff_summary: model.diffSummary }} compact />
        </Box>
      </Collapse>
    </Box>
  );
};

export default ChangeReviewPanel;
