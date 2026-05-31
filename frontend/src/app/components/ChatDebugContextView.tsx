import React, { useMemo, useState } from 'react';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Collapse from '@mui/material/Collapse';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import BugReportOutlinedIcon from '@mui/icons-material/BugReportOutlined';
import type { UnifiedComposerState } from '@/shared/types/unifiedComposer';
import { useClaudeTokens } from '@/shared/styles/ThemeContext';

export interface ChatDebugRuntimeSnapshot {
  surfaceLabel: string;
  sessionId?: string | null;
  status?: string | null;
  mode?: string | null;
  model?: string | null;
  provider?: string | null;
  queueCount?: number;
  pendingApprovalsCount?: number;
  traceCount?: number;
  evidenceCount?: number;
  artifactCount?: number;
  latestActivity?: string | null;
  metrics?: Array<{ label: string; value: string | number | null | undefined }>;
}

interface Props {
  title?: string;
  state?: UnifiedComposerState | null;
  runtime?: ChatDebugRuntimeSnapshot | null;
  processTraceItems?: unknown[];
  compact?: boolean;
}

function safeText(value: unknown, fallback = ''): string {
  const raw = String(value ?? fallback).trim();
  if (!raw) return fallback;
  if (/token|secret|password|cookie|bearer|private[_-]?key/i.test(raw)) return '[redacted]';
  return raw.length > 120 ? `${raw.slice(0, 117)}…` : raw;
}

function countEnabled<T extends { disabled_reason?: unknown }>(items: T[] | undefined): number {
  return (items || []).filter((item) => !item.disabled_reason).length;
}

function traceSubsystems(items: unknown[] | undefined): string[] {
  const seen = new Set<string>();
  for (const raw of items || []) {
    const item = raw as any;
    const subsystem = safeText(item?.subsystem || item?.kind || item?.title, '');
    if (subsystem) seen.add(subsystem);
  }
  return Array.from(seen).slice(0, 8);
}

const ChatDebugContextView: React.FC<Props> = ({
  title = 'Debug context',
  state,
  runtime,
  processTraceItems = [],
  compact = false,
}) => {
  const c = useClaudeTokens();
  const [open, setOpen] = useState(false);

  const rows = useMemo(() => {
    const out: Array<{ label: string; values: string[]; tone?: string }> = [];

    if (state) {
      out.push({
        label: 'Request',
        values: [
          `surface:${safeText(state.source_surface)}`,
          `owner:${safeText(state.owner_id)}`,
          `mode:${safeText(state.mode || 'not provided')}`,
          `model:${safeText(state.model || 'not provided')}`,
          `prompt_length:${String((state.prompt || '').length)}`,
          state.loading ? 'loading:true' : 'loading:false',
          state.disabled ? 'disabled:true' : 'disabled:false',
        ],
        tone: c.status.info,
      });

      const contextValues = [
        ...state.context_refs.map((ref) => `${ref.kind}:${safeText(ref.label)}`),
        ...state.attachment_refs.map((ref) => `${ref.kind}:${safeText(ref.label)}`),
        ...state.selected_ui_elements.map((ref) => `ui:${safeText(ref.label)}`),
      ];
      if (contextValues.length) out.push({ label: 'Context refs', values: contextValues, tone: c.accent.primary });

      const researchValues = (state.research_sources || [])
        .filter((src) => src.state === 'selected' || src.state === 'requires_approval')
        .map((src) => `${src.kind}:${safeText(src.label)}:${src.state}`);
      if (researchValues.length) out.push({ label: 'Research', values: researchValues, tone: c.status.warning });

      if (state.edit_target) {
        out.push({
          label: 'Edit target',
          values: [`${state.edit_target.kind}:${safeText(state.edit_target.label)}`, state.edit_target.disabled_reason?.message || 'ready'].filter(Boolean),
          tone: c.status.info,
        });
      }

      const toolValues = state.tools_selected.map((tool) => `${safeText(tool.label)}:${tool.state}`);
      if (toolValues.length) out.push({ label: 'Tools', values: toolValues, tone: c.status.info });

      const refs = [...(state.evidence_refs || []), ...(state.trace_refs || [])].map((ref) => safeText(ref));
      if (refs.length) out.push({ label: 'Refs', values: refs, tone: c.status.success });

      const disabled = [
        ...state.disabled_reasons.map((reason) => reason.message),
        ...state.context_refs.map((ref) => ref.disabled_reason?.message).filter(Boolean) as string[],
        ...state.tools_available.map((tool) => tool.disabled_reason?.message).filter(Boolean) as string[],
        state.voice.disabled_reason?.message,
        ...(state.warnings || []),
      ].filter(Boolean).map((msg) => safeText(msg));
      if (disabled.length) out.push({ label: 'Redactions / disabled', values: disabled, tone: c.text.tertiary });
    }

    if (runtime) {
      const runtimeValues = [
        `surface:${safeText(runtime.surfaceLabel)}`,
        runtime.status ? `status:${safeText(runtime.status)}` : '',
        runtime.mode ? `mode:${safeText(runtime.mode)}` : '',
        runtime.model ? `model:${safeText(runtime.model)}` : '',
        runtime.provider ? `provider:${safeText(runtime.provider)}` : '',
        runtime.sessionId ? `id:${safeText(runtime.sessionId)}` : '',
        typeof runtime.queueCount === 'number' ? `queue:${runtime.queueCount}` : '',
        typeof runtime.pendingApprovalsCount === 'number' ? `approvals:${runtime.pendingApprovalsCount}` : '',
        typeof runtime.traceCount === 'number' ? `trace:${runtime.traceCount}` : '',
        typeof runtime.evidenceCount === 'number' ? `evidence:${runtime.evidenceCount}` : '',
        typeof runtime.artifactCount === 'number' ? `artifacts:${runtime.artifactCount}` : '',
        runtime.latestActivity ? `latest:${safeText(runtime.latestActivity)}` : '',
      ].filter(Boolean);
      if (runtimeValues.length) out.push({ label: 'Runtime', values: runtimeValues, tone: c.status.info });

      const metrics = (runtime.metrics || [])
        .filter((metric) => metric.value !== null && metric.value !== undefined && metric.value !== '')
        .map((metric) => `${safeText(metric.label)}:${safeText(metric.value)}`);
      if (metrics.length) out.push({ label: 'Metrics', values: metrics, tone: c.status.success });
    }

    const subsystems = traceSubsystems(processTraceItems);
    if (subsystems.length) out.push({ label: 'Trace subsystems', values: subsystems, tone: c.status.success });

    return out;
  }, [c, processTraceItems, runtime, state]);

  if (!rows.length) return null;

  const total = rows.reduce((sum, row) => sum + row.values.length, 0);

  return (
    <Box sx={{ mx: compact ? 0 : 1.5, mb: compact ? 0.5 : 0.75, border: `1px solid ${c.border.subtle}`, borderRadius: 1.5, bgcolor: `${c.bg.secondary}78`, overflow: 'hidden' }}>
      <Box onClick={() => setOpen((value) => !value)} sx={{ display: 'flex', alignItems: 'center', gap: 0.75, px: 1, py: 0.55, cursor: 'pointer' }}>
        <BugReportOutlinedIcon sx={{ fontSize: 14, color: c.text.tertiary }} />
        <Typography sx={{ fontSize: '0.68rem', color: c.text.secondary, fontWeight: 700, flex: 1 }}>
          {title} · {rows.length} sections · {total} refs
        </Typography>
        <Tooltip title={open ? 'Hide debug context' : 'Show debug context'}>
          <IconButton size="small" sx={{ width: 20, height: 20, color: c.text.tertiary }}>
            <ExpandMoreIcon sx={{ fontSize: 16, transform: open ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 120ms ease' }} />
          </IconButton>
        </Tooltip>
      </Box>
      <Collapse in={open}>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.55, px: 1, pb: 0.85 }}>
          {rows.map((row) => (
            <Box key={row.label} sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexWrap: 'wrap' }}>
              <Typography sx={{ fontSize: '0.61rem', color: c.text.ghost, fontWeight: 800, textTransform: 'uppercase', minWidth: 92 }}>
                {row.label}
              </Typography>
              {row.values.slice(0, 10).map((value, idx) => (
                <Chip
                  key={`${row.label}-${value}-${idx}`}
                  label={value}
                  size="small"
                  sx={{ height: 20, maxWidth: 220, fontSize: '0.61rem', color: row.tone || c.text.secondary, bgcolor: `${row.tone || c.text.secondary}12`, '& .MuiChip-label': { overflow: 'hidden', textOverflow: 'ellipsis' } }}
                />
              ))}
              {row.values.length > 10 && <Typography sx={{ fontSize: '0.62rem', color: c.text.ghost }}>+{row.values.length - 10}</Typography>}
            </Box>
          ))}
        </Box>
      </Collapse>
    </Box>
  );
};

export default ChatDebugContextView;
