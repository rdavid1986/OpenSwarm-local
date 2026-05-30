import React, { useMemo, useState } from 'react';
import Box from '@mui/material/Box';
import Collapse from '@mui/material/Collapse';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import HourglassEmptyIcon from '@mui/icons-material/HourglassEmpty';
import PauseCircleOutlineIcon from '@mui/icons-material/PauseCircleOutline';
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import AccountTreeOutlinedIcon from '@mui/icons-material/AccountTreeOutlined';
import MemoryOutlinedIcon from '@mui/icons-material/MemoryOutlined';
import ExtensionOutlinedIcon from '@mui/icons-material/ExtensionOutlined';
import TuneOutlinedIcon from '@mui/icons-material/TuneOutlined';
import AdsClickOutlinedIcon from '@mui/icons-material/AdsClickOutlined';
import FactCheckOutlinedIcon from '@mui/icons-material/FactCheckOutlined';
import TimelineOutlinedIcon from '@mui/icons-material/TimelineOutlined';
import SpeedOutlinedIcon from '@mui/icons-material/SpeedOutlined';
import CallSplitOutlinedIcon from '@mui/icons-material/CallSplitOutlined';
import VerifiedOutlinedIcon from '@mui/icons-material/VerifiedOutlined';
import LanguageIcon from '@mui/icons-material/Language';
import SettingsSuggestOutlinedIcon from '@mui/icons-material/SettingsSuggestOutlined';
import SmartToyOutlinedIcon from '@mui/icons-material/SmartToyOutlined';
import PsychologyOutlinedIcon from '@mui/icons-material/PsychologyOutlined';
import BuildOutlinedIcon from '@mui/icons-material/BuildOutlined';
import InsertDriveFileOutlinedIcon from '@mui/icons-material/InsertDriveFileOutlined';
import LayersOutlinedIcon from '@mui/icons-material/LayersOutlined';
import HubOutlinedIcon from '@mui/icons-material/HubOutlined';
import RuleOutlinedIcon from '@mui/icons-material/RuleOutlined';
import OutputOutlinedIcon from '@mui/icons-material/OutputOutlined';
import ContentCopyOutlinedIcon from '@mui/icons-material/ContentCopyOutlined';
import FolderOutlinedIcon from '@mui/icons-material/FolderOutlined';
import AttachFileOutlinedIcon from '@mui/icons-material/AttachFileOutlined';
import DifferenceOutlinedIcon from '@mui/icons-material/DifferenceOutlined';

import { useClaudeTokens } from '@/shared/styles/ThemeContext';
import { buildCardVisualTokens } from './cardVisualTokens';

export type ProcessTraceStatus =
  | 'planned'
  | 'running'
  | 'completed'
  | 'failed'
  | 'blocked'
  | 'skipped'
  | 'cancelled'
  | 'warning';

export type ProcessTraceItem = {
  trace_kind?: string;
  trace_version?: string;
  trace_id?: string;
  kind?: string;
  subsystem?: string;
  title?: string;
  summary?: string;
  status?: ProcessTraceStatus | string;
  started_at?: string | null;
  finished_at?: string | null;
  duration_ms?: number | null;
  icon_id?: string;
  badge?: string;
  details?: Record<string, unknown>;
  evidence_refs?: unknown[];
  artifact_refs?: unknown[];
  related_task_id?: string;
  related_agent_id?: string;
  related_miniagent_id?: string;
  related_skill_id?: string;
  related_action_id?: string;
  created_at?: string;
  visible_to_user?: boolean;
  internal_only?: boolean;
  metadata?: Record<string, unknown>;
};

export type ProcessTraceTurnContainer = {
  turn_trace_kind?: string;
  turn_trace_version?: string;
  turn_trace_id?: string;
  title?: string;
  status?: ProcessTraceStatus | string;
  turn_id?: string;
  message_id?: string;
  action_id?: string;
  started_at?: string | null;
  finished_at?: string | null;
  duration_ms?: number | null;
  default_collapsed_after_finish?: boolean;
  default_expanded_while_running?: boolean;
  child_trace_ids?: unknown[];
  item_count?: number;
  items?: ProcessTraceItem[];
  output_message_id?: string;
  related_task_ids?: unknown[];
  related_agent_ids?: unknown[];
  related_miniagent_ids?: unknown[];
  evidence_refs?: unknown[];
  artifact_refs?: unknown[];
  visible_to_user?: boolean;
  internal_only?: boolean;
  metadata?: Record<string, unknown>;
  created_at?: string;
};

type ProcessTraceDropdownProps = {
  item: ProcessTraceItem;
  defaultExpanded?: boolean;
  compact?: boolean;
  showRawDetails?: boolean;
  bare?: boolean;
};

const STATUS_LABELS: Record<string, string> = {
  planned: 'Ready',
  running: 'Running',
  completed: 'Completed',
  failed: 'Failed',
  blocked: 'Blocked',
  skipped: 'Skipped',
  cancelled: 'Cancelled',
  warning: 'Warning',
};

const SUBSYSTEM_INITIALS: Record<string, string> = {
  SwarmCore: 'SW',
  ReasoningCore: 'RS',
  ToolCore: 'TL',
  FileCore: 'FL',
  ContextCore: 'CX',
  MemoryCore: 'ME',
  SkillCore: 'SK',
  ModeCore: 'MO',
  ActionCore: 'AC',
  EvidenceCore: 'EV',
  TraceCore: 'TR',
  MetricCore: 'MT',
  HandoffCore: 'HF',
  MiniAgentCore: 'MA',
  ValidationCore: 'VA',
  OutputCore: 'OU',
  ReviewCore: 'RV',
  BrowserCore: 'BR',
  ConfigCore: 'CF',
  ModelCore: 'MD',
};

function formatDurationMs(durationMs?: number | null): string | null {
  if (durationMs == null || Number.isNaN(durationMs)) return null;
  const safeMs = Math.max(0, Math.round(durationMs));
  const seconds = safeMs / 1000;
  if (seconds < 60) return `${seconds.toFixed(2)}s`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds - minutes * 60;
  if (minutes < 60) return `${minutes}m ${remainingSeconds.toFixed(2)}s`;
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return remainingMinutes > 0 ? `${hours}h ${remainingMinutes}m` : `${hours}h`;
}

function normalizeStatus(status?: string): ProcessTraceStatus {
  const normalized = String(status || '').toLowerCase().replace(/[\s-]+/g, '_');
  if (normalized === 'idle' || normalized === 'ready' || normalized === 'queued' || normalized === 'pending') return 'planned';
  if (normalized === 'error') return 'failed';
  if (normalized === 'waiting_approval' || normalized === 'requires_approval') return 'blocked';
  if (['planned', 'running', 'completed', 'failed', 'blocked', 'skipped', 'cancelled', 'warning'].includes(normalized)) {
    return normalized as ProcessTraceStatus;
  }
  return 'planned';
}

const REDACTED_TRACE_VALUE = '[redacted]';
const MAX_TRACE_TEXT_LENGTH = 600;
const MAX_TRACE_COPY_LENGTH = 4000;
const MAX_TRACE_JSON_LENGTH = 5000;
const MAX_TRACE_ARRAY_ITEMS = 20;
const MAX_TRACE_OBJECT_KEYS = 40;
const MAX_VISIBLE_TURN_ITEMS = 30;
const MAX_DETAIL_ROWS = 18;

const SENSITIVE_TRACE_KEYS = new Set([
  'api_key',
  'apikey',
  'authorization',
  'bearer',
  'chain_of_thought',
  'client_secret',
  'connection_string',
  'content',
  'cookie',
  'credential',
  'credentials',
  'cot',
  'full_prompt',
  'full_response',
  'hidden_reasoning',
  'message',
  'password',
  'private_key',
  'private_reasoning',
  'prompt',
  'raw_prompt',
  'raw_response',
  'response',
  'refresh_token',
  'secret',
  'session',
  'session_id',
  'set_cookie',
  'set-cookie',
  'system_prompt',
  'token',
  'user_prompt',
  'webhook_secret',
]);

function normalizeTraceKey(value: string): string {
  return String(value || '').trim().toLowerCase().replace(/[\s.-]+/g, '_');
}

function isSensitiveTraceKey(key: string): boolean {
  const normalized = normalizeTraceKey(key);
  return SENSITIVE_TRACE_KEYS.has(normalized)
    || normalized.endsWith('_secret')
    || normalized.endsWith('_password')
    || normalized.endsWith('_api_key')
    || normalized.endsWith('_private_key')
    || normalized.endsWith('_access_token')
    || normalized.endsWith('_refresh_token')
    || normalized.endsWith('_client_secret')
    || normalized.endsWith('_token')
    || normalized.endsWith('_cookie')
    || normalized.endsWith('_session')
    || normalized.includes('webhook_secret')
    || normalized.includes('connection_string');
}

function redactTraceText(value: string): string {
  const clean = String(value || '')
    .replace(/(authorization\s*[:=]\s*bearer\s+)[^\s,;]+/gi, `$1${REDACTED_TRACE_VALUE}`)
    .replace(/\bbearer\s+[a-z0-9._~+/-]+=*/gi, `bearer ${REDACTED_TRACE_VALUE}`)
    .replace(/((?:api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|webhook[_-]?secret|password|secret|token|cookie|session)\s*[:=]\s*)[^\s,;]+/gi, `$1${REDACTED_TRACE_VALUE}`)
    .replace(/((?:postgres|postgresql|mysql|mongodb(?:\+srv)?|redis|amqp|mssql|sqlserver):\/\/)[^\s'"]+/gi, `$1${REDACTED_TRACE_VALUE}`)
    .replace(/\b(?:sk|pk|xoxb|xoxp|ghp|github_pat)[-_][a-z0-9_=-]{16,}\b/gi, REDACTED_TRACE_VALUE)
    .replace(/\beyJ[a-z0-9_-]{20,}\.[a-z0-9_-]{20,}\.[a-z0-9_-]{10,}\b/gi, REDACTED_TRACE_VALUE)
    .replace(/(chain[_ -]?of[_ -]?thought|private[_ -]?reasoning|hidden[_ -]?reasoning)\s*[:=]\s*[^\n]+/gi, `$1: ${REDACTED_TRACE_VALUE}`);

  return clean.length > MAX_TRACE_TEXT_LENGTH
    ? `${clean.slice(0, MAX_TRACE_TEXT_LENGTH).trimEnd()}…`
    : clean;
}

function sanitizeTraceValue(value: unknown, depth = 0): unknown {
  if (value == null) return value;
  if (typeof value === 'string') return redactTraceText(value);
  if (typeof value === 'number' || typeof value === 'boolean') return value;
  if (depth >= 3) return '[object redacted]';

  if (Array.isArray(value)) {
    const visible = value.slice(0, MAX_TRACE_ARRAY_ITEMS).map((item) => sanitizeTraceValue(item, depth + 1));
    return value.length > MAX_TRACE_ARRAY_ITEMS ? [...visible, `+${value.length - MAX_TRACE_ARRAY_ITEMS} more`] : visible;
  }

  if (typeof value === 'object') {
    const output: Record<string, unknown> = {};
    const entries = Object.entries(value as Record<string, unknown>);
    entries.slice(0, MAX_TRACE_OBJECT_KEYS).forEach(([key, item]) => {
      output[key] = isSensitiveTraceKey(key) ? REDACTED_TRACE_VALUE : sanitizeTraceValue(item, depth + 1);
    });
    if (entries.length > MAX_TRACE_OBJECT_KEYS) output.__truncated__ = `+${entries.length - MAX_TRACE_OBJECT_KEYS} more fields`;
    return output;
  }

  return String(value);
}

function stringifyDetail(value: unknown): string {
  const sanitized = sanitizeTraceValue(value);
  if (sanitized == null) return '';
  if (typeof sanitized === 'string') return sanitized;
  if (typeof sanitized === 'number' || typeof sanitized === 'boolean') return String(sanitized);
  try {
    const json = JSON.stringify(sanitized, null, 2);
    return json.length > MAX_TRACE_JSON_LENGTH ? `${json.slice(0, MAX_TRACE_JSON_LENGTH).trimEnd()}\n… [truncated]` : json;
  } catch {
    return REDACTED_TRACE_VALUE;
  }
}

function traceText(value: unknown, fallback = 'not provided', maxLength = MAX_TRACE_TEXT_LENGTH): string {
  const text = stringifyDetail(value).trim();
  if (!text) return fallback;
  return text.length > maxLength ? `${text.slice(0, maxLength).trimEnd()}…` : text;
}

function getDetailValue(details: Record<string, unknown>, ...keys: string[]): unknown {
  for (const key of keys) {
    const value = details[key];
    if (value !== undefined && value !== null && value !== '') return value;
  }
  return undefined;
}

function compactTraceList(value: unknown, limit = 5): string {
  const rawItems = Array.isArray(value) ? value : (value == null || value === '' ? [] : [value]);
  const items = rawItems.map((item) => traceText(item, '')).filter(Boolean);
  if (items.length === 0) return 'not provided';
  const visible = items.slice(0, limit).map((item) => (item.length > 96 ? `${item.slice(0, 96).trimEnd()}…` : item));
  const extra = items.length - visible.length;
  return extra > 0 ? `${visible.join('\n')} (+${extra} more)` : visible.join('\n');
}

function pushDetailRow(rows: Array<[string, unknown]>, label: string, value: unknown, options?: { list?: boolean }) {
  if (value === undefined || value === null || value === '') return;
  rows.push([label, options?.list ? compactTraceList(value) : traceText(value)]);
}

function buildSubsystemDetailRows(item: ProcessTraceItem, durationLabel: string | null): Array<[string, unknown]> {
  const rows: Array<[string, unknown]> = [];
  const details = item.details || {};
  const subsystem = String(item.subsystem || '').toLowerCase();
  const kind = String(item.kind || '').toLowerCase();
  const isToolOrAction = subsystem === 'toolcore' || subsystem === 'actioncore' || kind === 'tool' || kind === 'action';
  const isSkill = subsystem === 'skillcore' || kind === 'skill';
  const isFileOutput = ['filecore', 'outputcore'].includes(subsystem) || ['file', 'diff', 'workspace', 'output', 'artifact'].includes(kind);
  const isMiniAgentOrHandoff = ['miniagentcore', 'handoffcore'].includes(subsystem) || ['miniagent', 'handoff'].includes(kind);
  const isModel = subsystem === 'modelcore' || kind === 'model' || kind === 'model_snapshot';

  if (isToolOrAction) {
    pushDetailRow(rows, 'Tool', getDetailValue(details, 'tool_name', 'tool'));
    pushDetailRow(rows, 'Action', getDetailValue(details, 'action_name'));
    pushDetailRow(rows, 'Approval', getDetailValue(details, 'approval_status', 'approval_state'));
    pushDetailRow(rows, 'Policy', getDetailValue(details, 'permission_policy', 'policy'));
    pushDetailRow(rows, 'Input', getDetailValue(details, 'input_summary', 'input'));
    pushDetailRow(rows, 'Result', getDetailValue(details, 'result_summary', 'output_summary', 'result', 'output'));
    pushDetailRow(rows, 'Error', getDetailValue(details, 'error'));
    pushDetailRow(rows, 'Affected files', getDetailValue(details, 'affected_files', 'affected_paths'), { list: true });
    pushDetailRow(rows, 'Duration', durationLabel);
    pushDetailRow(rows, 'Evidence', item.evidence_refs, { list: true });
    pushDetailRow(rows, 'Action id', item.related_action_id);
    pushDetailRow(rows, 'Source', getDetailValue(details, 'source_kind') || item.metadata?.source_kind);
    return rows;
  }

  if (isSkill) {
    pushDetailRow(rows, 'Skill id', getDetailValue(details, 'skill_id') || item.related_skill_id);
    pushDetailRow(rows, 'Skill name', getDetailValue(details, 'skill_name'));
    pushDetailRow(rows, 'Use', getDetailValue(details, 'usage_reason', 'assignment_reason', 'reason'));
    pushDetailRow(rows, 'Scope', getDetailValue(details, 'scope'));
    pushDetailRow(rows, 'Input', getDetailValue(details, 'input_context', 'context', 'input'));
    pushDetailRow(rows, 'Output', getDetailValue(details, 'output_summary', 'output'));
    pushDetailRow(rows, 'Risk', getDetailValue(details, 'risk', 'risk_level'));
    pushDetailRow(rows, 'Install', getDetailValue(details, 'installation_status', 'install_status'));
    pushDetailRow(rows, 'Approval', getDetailValue(details, 'approval_status'));
    pushDetailRow(rows, 'Provenance', getDetailValue(details, 'provenance', 'source'));
    pushDetailRow(rows, 'Status', item.status);
    return rows;
  }

  if (isFileOutput) {
    pushDetailRow(rows, 'Read', getDetailValue(details, 'read_files'), { list: true });
    pushDetailRow(rows, 'Created', getDetailValue(details, 'created_files'), { list: true });
    pushDetailRow(rows, 'Modified', getDetailValue(details, 'modified_files'), { list: true });
    pushDetailRow(rows, 'Deleted', getDetailValue(details, 'deleted_files'), { list: true });
    pushDetailRow(rows, 'Affected', getDetailValue(details, 'affected_paths', 'affected_files'), { list: true });
    pushDetailRow(rows, 'Workspace', getDetailValue(details, 'workspace_path'));
    pushDetailRow(rows, 'Diff', getDetailValue(details, 'diff_summary'));
    pushDetailRow(rows, 'Output id', getDetailValue(details, 'output_id'));
    pushDetailRow(rows, 'Candidate', getDetailValue(details, 'candidate_id'));
    pushDetailRow(rows, 'Stable', getDetailValue(details, 'stable_output_id'));
    pushDetailRow(rows, 'Validation', getDetailValue(details, 'validation_state'));
    pushDetailRow(rows, 'Operation', getDetailValue(details, 'file_operation_kind'));
    pushDetailRow(rows, 'Artifacts', item.artifact_refs, { list: true });
    return rows;
  }

  if (isMiniAgentOrHandoff) {
    pushDetailRow(rows, 'MiniAgent', getDetailValue(details, 'miniagent_name'));
    pushDetailRow(rows, 'MiniAgent id', getDetailValue(details, 'miniagent_id') || item.related_miniagent_id);
    pushDetailRow(rows, 'Task', getDetailValue(details, 'task_id') || item.related_task_id);
    pushDetailRow(rows, 'From', getDetailValue(details, 'source_agent_id', 'source'));
    pushDetailRow(rows, 'To', getDetailValue(details, 'target_agent_id', 'target'));
    pushDetailRow(rows, 'Status', item.status);
    pushDetailRow(rows, 'Duration', durationLabel);
    pushDetailRow(rows, 'Input', getDetailValue(details, 'input_summary', 'input'));
    pushDetailRow(rows, 'Output', getDetailValue(details, 'output_summary', 'output'));
    pushDetailRow(rows, 'Evidence', item.evidence_refs, { list: true });
    pushDetailRow(rows, 'Artifacts', item.artifact_refs, { list: true });
    pushDetailRow(rows, 'Validation', getDetailValue(details, 'validation', 'validation_summary'));
    pushDetailRow(rows, 'Failure', getDetailValue(details, 'failure_reason', 'error'));
    return rows;
  }

  if (isModel) {
    pushDetailRow(rows, 'Provider', getDetailValue(details, 'provider'));
    pushDetailRow(rows, 'Model', getDetailValue(details, 'model'));
    pushDetailRow(rows, 'Health', getDetailValue(details, 'health'));
    pushDetailRow(rows, 'Capabilities', getDetailValue(details, 'capabilities'));
    pushDetailRow(rows, 'Loaded', getDetailValue(details, 'loaded'));
    pushDetailRow(rows, 'Running', getDetailValue(details, 'running'));
    pushDetailRow(rows, 'Expires', getDetailValue(details, 'expires_at'));
    return rows;
  }

  return rows;
}

export function normalizeProcessTraceTurnContainer(value: unknown): ProcessTraceTurnContainer | null {
  if (!value || typeof value !== 'object') return null;
  const data = value as Record<string, unknown>;
  const directItems = Array.isArray(data.items) ? data.items : undefined;
  const traceItems = Array.isArray(data.traceItems) ? data.traceItems : undefined;
  const processTraceItems = Array.isArray(data.process_trace_items) ? data.process_trace_items : undefined;
  const items = directItems || traceItems || processTraceItems;

  if (data.turn_trace_kind === 'process_trace_turn_container' || data.process_trace_turn === true || items) {
    return { ...(data as ProcessTraceTurnContainer), items: items as ProcessTraceItem[] | undefined };
  }
  return null;
}

function formatTraceTimestamp(value: unknown): string | null {
  const text = String(value || '').trim();
  if (!text) return null;
  const date = new Date(text);
  if (Number.isNaN(date.getTime())) return redactTraceText(text);
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function copySafeText(value: unknown) {
  const text = traceText(value, '', MAX_TRACE_COPY_LENGTH);
  if (!text || typeof navigator === 'undefined' || !navigator.clipboard) return;
  void navigator.clipboard.writeText(text);
}

function TraceChip({ label }: { label: string }) {
  const c = useClaudeTokens();
  return (
    <Typography
      component="span"
      sx={{
        display: 'inline-flex',
        alignItems: 'center',
        maxWidth: 180,
        px: 0.55,
        py: 0.18,
        borderRadius: 999,
        bgcolor: `${c.text.primary}0A`,
        border: `1px solid ${c.border.subtle}`,
        color: c.text.tertiary,
        fontSize: '0.62rem',
        fontWeight: 650,
        lineHeight: 1.25,
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
      }}
    >
      {redactTraceText(label)}
    </Typography>
  );
}

function FileGlyph({ type }: { type: 'file' | 'folder' | 'diff' | 'output' | 'attachment' | 'workspace' }) {
  const c = useClaudeTokens();
  const sx = { fontSize: 13, color: c.text.tertiary, flexShrink: 0 };
  if (type === 'folder' || type === 'workspace') return <FolderOutlinedIcon sx={sx} />;
  if (type === 'diff') return <DifferenceOutlinedIcon sx={sx} />;
  if (type === 'output') return <OutputOutlinedIcon sx={sx} />;
  if (type === 'attachment') return <AttachFileOutlinedIcon sx={sx} />;
  return <InsertDriveFileOutlinedIcon sx={sx} />;
}

function TracePathList({ title, value, type = 'file' }: { title: string; value: unknown; type?: 'file' | 'folder' | 'diff' | 'output' | 'attachment' | 'workspace' }) {
  const c = useClaudeTokens();
  const items = (Array.isArray(value) ? value : (value ? [value] : []))
    .map((item) => traceText(item, ''))
    .filter(Boolean);
  if (items.length === 0) return null;
  const visible = items.slice(0, 6);
  const extra = items.length - visible.length;
  return (
    <Box sx={{ display: 'grid', gap: 0.35 }}>
      <Typography sx={{ color: c.text.ghost, fontSize: '0.66rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
        {title}
      </Typography>
      {visible.map((path, idx) => (
        <Box key={`${title}-${idx}-${path}`} sx={{ display: 'flex', alignItems: 'center', gap: 0.55, minWidth: 0 }}>
          <FileGlyph type={type} />
          <Typography
            noWrap
            title={path}
            sx={{ color: c.text.tertiary, fontSize: '0.68rem', fontFamily: c.font.mono, minWidth: 0 }}
          >
            {path.length > 140 ? `${path.slice(0, 140).trimEnd()}…` : path}
          </Typography>
        </Box>
      ))}
      {extra > 0 && <Typography sx={{ color: c.text.ghost, fontSize: '0.64rem' }}>+{extra} more</Typography>}
    </Box>
  );
}

function SummaryList({ title, value }: { title: string; value: unknown }) {
  const c = useClaudeTokens();
  const items = (Array.isArray(value) ? value : (value ? [value] : []))
    .map((item) => traceText(item, ''))
    .filter(Boolean)
    .slice(0, 6);
  if (items.length === 0) return null;
  return (
    <Box sx={{ display: 'grid', gap: 0.35 }}>
      <Typography sx={{ color: c.text.ghost, fontSize: '0.66rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
        {title}
      </Typography>
      {items.map((item, idx) => (
        <Typography key={`${title}-${idx}`} sx={{ color: c.text.tertiary, fontSize: '0.7rem', lineHeight: 1.4, overflowWrap: 'anywhere' }}>
          • {item.length > 220 ? `${item.slice(0, 220).trimEnd()}…` : item}
        </Typography>
      ))}
    </Box>
  );
}

function RichTraceSections({ item }: { item: ProcessTraceItem }) {
  const c = useClaudeTokens();
  const details = item.details || {};
  const subsystem = String(item.subsystem || '').toLowerCase();
  const kind = String(item.kind || '').toLowerCase();
  const isFileOutput = ['filecore', 'outputcore'].includes(subsystem) || ['file', 'diff', 'workspace', 'output', 'artifact'].includes(kind);
  const summaryFields = [
    ['Session summary', getDetailValue(details, 'session_summary')],
    ['Key learnings', getDetailValue(details, 'key_learnings', 'learnings')],
    ['Decisions', getDetailValue(details, 'decisions')],
    ['Blockers', getDetailValue(details, 'blockers')],
    ['Next steps', getDetailValue(details, 'next_steps')],
    ['Validation', getDetailValue(details, 'validation_summary', 'validation')],
  ] as Array<[string, unknown]>;
  const hasSummary = summaryFields.some(([, value]) => value !== undefined && value !== null && value !== '');
  if (!isFileOutput && !hasSummary) return null;

  return (
    <Box sx={{ display: 'grid', gap: 0.85, mb: 1 }}>
      {isFileOutput && (
        <Box
          sx={{
            display: 'grid',
            gap: 0.75,
            p: 0.75,
            borderRadius: 1,
            border: `1px solid ${c.border.subtle}`,
            bgcolor: `${c.bg.elevated}66`,
          }}
        >
          <TracePathList title="Read" value={getDetailValue(details, 'read_files')} />
          <TracePathList title="Created" value={getDetailValue(details, 'created_files')} />
          <TracePathList title="Modified" value={getDetailValue(details, 'modified_files')} type="diff" />
          <TracePathList title="Deleted" value={getDetailValue(details, 'deleted_files')} />
          <TracePathList title="Affected" value={getDetailValue(details, 'affected_paths', 'affected_files')} type="diff" />
          <TracePathList title="Attachments" value={getDetailValue(details, 'attachments', 'attachment_refs') || item.artifact_refs} type="attachment" />
          <TracePathList title="Workspace" value={getDetailValue(details, 'workspace_path')} type="workspace" />
          {getDetailValue(details, 'diff_summary') && (
            <Typography sx={{ color: c.text.secondary, fontSize: '0.72rem', lineHeight: 1.45, overflowWrap: 'anywhere' }}>
              {traceText(getDetailValue(details, 'diff_summary'))}
            </Typography>
          )}
        </Box>
      )}
      {hasSummary && (
        <Box
          sx={{
            display: 'grid',
            gap: 0.75,
            p: 0.75,
            borderRadius: 1,
            border: `1px solid ${c.border.subtle}`,
            bgcolor: `${c.bg.elevated}66`,
          }}
        >
          {summaryFields.map(([label, value]) => <SummaryList key={label} title={label} value={value} />)}
        </Box>
      )}
    </Box>
  );
}

function StatusIcon({ status, color }: { status: ProcessTraceStatus; color: string }) {
  const sx = { fontSize: 19, color, flexShrink: 0 };
  if (status === 'completed') return null;
  if (status === 'failed') return <ErrorOutlineIcon sx={sx} />;
  if (status === 'blocked' || status === 'warning') return <WarningAmberIcon sx={sx} />;
  if (status === 'running') {
    return (
      <HourglassEmptyIcon
        sx={{
          ...sx,
          animation: 'processTraceHourglassClockwise 1.1s linear infinite',
          '@keyframes processTraceHourglassClockwise': {
            '0%': { transform: 'rotate(0deg)' },
            '100%': { transform: 'rotate(360deg)' },
          },
        }}
      />
    );
  }
  if (status === 'cancelled' || status === 'skipped') return <PauseCircleOutlineIcon sx={sx} />;
  return <RadioButtonUncheckedIcon sx={sx} />;
}

function normalizeIconKey(value?: string): string {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/_/g, '-');
}

function SubsystemIcon({
  iconId,
  subsystem,
  label,
  color,
}: {
  iconId?: string;
  subsystem?: string;
  label: string;
  color: string;
}) {
  const sx = { fontSize: 18, color };
  const iconKey = normalizeIconKey(iconId || subsystem);

  if (iconKey === 'swarm-core' || iconKey === 'swarmcore') return <AccountTreeOutlinedIcon sx={sx} />;
  if (iconKey === 'reasoning-core' || iconKey === 'reasoningcore') return <PsychologyOutlinedIcon sx={sx} />;
  if (iconKey === 'tool-core' || iconKey === 'toolcore') return <BuildOutlinedIcon sx={sx} />;
  if (iconKey === 'file-core' || iconKey === 'filecore') return <InsertDriveFileOutlinedIcon sx={sx} />;
  if (iconKey === 'context-core' || iconKey === 'contextcore') return <LayersOutlinedIcon sx={sx} />;
  if (iconKey === 'memory-core' || iconKey === 'memorycore') return <MemoryOutlinedIcon sx={sx} />;
  if (iconKey === 'skill-core' || iconKey === 'skillcore') return <ExtensionOutlinedIcon sx={sx} />;
  if (iconKey === 'mode-core' || iconKey === 'modecore') return <TuneOutlinedIcon sx={sx} />;
  if (iconKey === 'action-core' || iconKey === 'actioncore') return <AdsClickOutlinedIcon sx={sx} />;
  if (iconKey === 'evidence-core' || iconKey === 'evidencecore') return <FactCheckOutlinedIcon sx={sx} />;
  if (iconKey === 'trace-core' || iconKey === 'tracecore') return <TimelineOutlinedIcon sx={sx} />;
  if (iconKey === 'metric-core' || iconKey === 'metriccore') return <SpeedOutlinedIcon sx={sx} />;
  if (iconKey === 'handoff-core' || iconKey === 'handoffcore') return <CallSplitOutlinedIcon sx={sx} />;
  if (iconKey === 'miniagent-core' || iconKey === 'miniagentcore') return <HubOutlinedIcon sx={sx} />;
  if (iconKey === 'validation-core' || iconKey === 'validationcore') return <RuleOutlinedIcon sx={sx} />;
  if (iconKey === 'output-core' || iconKey === 'outputcore') return <OutputOutlinedIcon sx={sx} />;
  if (iconKey === 'review-core' || iconKey === 'reviewcore') return <VerifiedOutlinedIcon sx={sx} />;
  if (iconKey === 'browser-core' || iconKey === 'browsercore') return <LanguageIcon sx={sx} />;
  if (iconKey === 'config-core' || iconKey === 'configcore') return <SettingsSuggestOutlinedIcon sx={sx} />;
  if (iconKey === 'model-core' || iconKey === 'modelcore') return <SmartToyOutlinedIcon sx={sx} />;

  return (
    <Typography
      component="span"
      sx={{
        color,
        fontFamily: 'inherit',
        fontSize: '0.58rem',
        fontWeight: 800,
        letterSpacing: '-0.03em',
        lineHeight: 1,
      }}
    >
      {label}
    </Typography>
  );
}

export const ProcessTraceDropdown: React.FC<ProcessTraceDropdownProps> = ({
  item,
  defaultExpanded = false,
  compact = false,
  showRawDetails = false,
  bare = false,
}) => {
  const c = useClaudeTokens();
  const cardTokens = buildCardVisualTokens(c);
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [debugExpanded, setDebugExpanded] = useState(showRawDetails);

  const shouldHideTraceItem = item.internal_only || item.visible_to_user === false;

  const status = normalizeStatus(item.status);
  const durationLabel = formatDurationMs(item.duration_ms);
  const subsystem = redactTraceText(item.subsystem || 'TraceCore');
  const iconId = redactTraceText(item.icon_id || subsystem);
  const iconLabel = SUBSYSTEM_INITIALS[subsystem] || subsystem.slice(0, 2).toUpperCase() || 'TR';
  const title = redactTraceText(item.title || item.kind || 'Process trace');
  const summary = redactTraceText(item.summary || 'No process summary recorded.');
  const badge = redactTraceText(item.badge || STATUS_LABELS[status] || status);
  const evidenceCount = Array.isArray(item.evidence_refs) ? item.evidence_refs.length : 0;
  const artifactCount = Array.isArray(item.artifact_refs) ? item.artifact_refs.length : 0;
  const hasDebugDetails = Boolean(item.details && Object.keys(item.details).length > 0);
  const isDebugJsonTrace = item.kind === 'debug' || item.metadata?.display_mode === 'debug_json';
  const sanitizedDebugDetails = useMemo(
    () => (hasDebugDetails ? sanitizeTraceValue(item.details) : null),
    [hasDebugDetails, item.details],
  );

  const statusColor = useMemo(() => {
    if (status === 'completed') return c.status.success;
    if (status === 'failed') return c.status.error;
    if (status === 'blocked' || status === 'warning') return c.status.warning;
    if (status === 'running') return c.accent.primary;
    return c.text.tertiary;
  }, [c, status]);

  const detailRows = useMemo(() => {
    const rows: Array<[string, unknown]> = buildSubsystemDetailRows(item, durationLabel);
    const showInternalRefs = item.metadata?.show_internal_refs === true;
    if (showInternalRefs && item.related_task_id) rows.push(['Task', redactTraceText(item.related_task_id)]);
    if (showInternalRefs && item.related_agent_id) rows.push(['Agent', redactTraceText(item.related_agent_id)]);
    if (showInternalRefs && item.related_miniagent_id) rows.push(['MiniAgent', redactTraceText(item.related_miniagent_id)]);
    if (item.related_skill_id && !rows.some(([label]) => label === 'Skill id' || label === 'Skill')) rows.push(['Skill', redactTraceText(item.related_skill_id)]);
    if (item.related_action_id && !rows.some(([label]) => label === 'Action id' || label === 'Action')) rows.push(['Action', redactTraceText(item.related_action_id)]);
    if (item.started_at) rows.push(['Started', item.started_at]);
    if (item.finished_at) rows.push(['Finished', item.finished_at]);
    if (durationLabel && !isDebugJsonTrace && !rows.some(([label]) => label === 'Duration')) rows.push(['Duration', durationLabel]);
    if (evidenceCount > 0 && !rows.some(([label]) => label === 'Evidence')) rows.push(['Evidence refs', compactTraceList(item.evidence_refs)]);
    if (artifactCount > 0 && !rows.some(([label]) => label === 'Artifacts')) rows.push(['Artifact refs', compactTraceList(item.artifact_refs)]);
    if (rows.length === 0 && !hasDebugDetails) rows.push(['Status', STATUS_LABELS[status] || status]);
    return rows.length > MAX_DETAIL_ROWS
      ? [...rows.slice(0, MAX_DETAIL_ROWS), ['More fields', `+${rows.length - MAX_DETAIL_ROWS} more`]]
      : rows;
  }, [item, durationLabel, evidenceCount, artifactCount, isDebugJsonTrace, hasDebugDetails, status]);

  const metadataChips = useMemo(() => {
    const details = item.details || {};
    const metadata = item.metadata || {};
    const raw = [
      ['time', formatTraceTimestamp(item.created_at || item.started_at)],
      ['status', STATUS_LABELS[status] || status],
      ['model', getDetailValue(details, 'model') || metadata.model],
      ['mode', getDetailValue(details, 'mode') || metadata.mode],
      ['provider', getDetailValue(details, 'provider') || metadata.provider],
      ['route', getDetailValue(details, 'route', 'flow') || metadata.route || metadata.flow],
      ['output', getDetailValue(details, 'created_output', 'output_id') || metadata.created_output],
    ] as Array<[string, unknown]>;
    const counts = [
      ['tools', getDetailValue(details, 'used_tools', 'tool_count')],
      ['actions', getDetailValue(details, 'used_actions', 'action_count')],
      ['skills', getDetailValue(details, 'used_skills', 'skill_count')],
    ] as Array<[string, unknown]>;
    counts.forEach(([label, value]) => {
      if (Array.isArray(value) && value.length > 0) raw.push([label, value.length]);
      else if (typeof value === 'number' && value > 0) raw.push([label, value]);
    });
    return raw
      .filter(([, value]) => value !== undefined && value !== null && value !== '')
      .map(([label, value]) => `${label}: ${traceText(value)}`)
      .slice(0, 7);
  }, [item, status]);

  const copyDetailsText = useMemo(() => {
    const detailText = detailRows.map(([label, value]) => `${label}: ${traceText(value, '')}`).join('\n');
    return [title, summary, detailText].filter(Boolean).join('\n');
  }, [detailRows, summary, title]);

  if (shouldHideTraceItem) {
    return null;
  }

  return (
    <Box
      sx={{
        bgcolor: bare ? 'transparent' : cardTokens.trace.background,
        border: bare ? 'none' : `1px solid ${status === 'running' ? cardTokens.trace.runningBorder : cardTokens.trace.border}`,
        borderRadius: cardTokens.trace.radius,
        overflow: 'hidden',
        transition: 'border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease',
        boxShadow: bare ? 'none' : (status === 'running' ? cardTokens.trace.runningShadow : cardTokens.trace.shadow),
        outline: bare ? 'none' : (status === 'running' ? `1px solid ${c.accent.primary}10` : 'none'),
      }}
    >
      <Box
        onClick={() => setExpanded((value) => !value)}
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 0.75,
          px: compact ? cardTokens.trace.compactPx : cardTokens.trace.px,
          py: compact ? cardTokens.trace.compactPy : cardTokens.trace.py,
          cursor: 'pointer',
          userSelect: 'none',
          '&:hover': { bgcolor: bare ? 'transparent' : cardTokens.trace.headerHoverBackground },
          transition: 'background 0.15s ease',
        }}
      >
        <Tooltip title={subsystem} arrow>
          <Box
            sx={{
              width: 18,
              height: 18,
              borderRadius: '50%',
              display: 'grid',
              placeItems: 'center',
              flexShrink: 0,
              bgcolor: `${statusColor}18`,
              border: `1px solid ${statusColor}45`,
              color: statusColor,
            }}
          >
            <SubsystemIcon iconId={iconId} subsystem={subsystem} label={iconLabel} color={statusColor} />
          </Box>
        </Tooltip>

        <StatusIcon status={status} color={statusColor} />

        <Box sx={{ minWidth: 0, flex: 1 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, minWidth: 0 }}>
            <Typography
              noWrap
              sx={{
                color: c.text.primary,
                fontSize: compact ? '0.76rem' : '0.82rem',
                fontWeight: 700,
                minWidth: 0,
              }}
            >
              {title}
            </Typography>
            <Typography
              noWrap
              sx={{
                color: statusColor,
                fontSize: '0.64rem',
                fontWeight: 700,
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
                flexShrink: 0,
              }}
            >
              {badge}
            </Typography>
          </Box>
          {!compact && (
            <Typography
              noWrap
              sx={{
                color: c.text.tertiary,
                fontSize: '0.72rem',
                mt: 0.15,
              }}
            >
              {summary}
            </Typography>
          )}
          {!compact && metadataChips.length > 0 && (
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.35, mt: 0.45 }}>
              {metadataChips.map((chip) => <TraceChip key={chip} label={chip} />)}
            </Box>
          )}
        </Box>

        {durationLabel && (
          <Typography
            sx={{
              color: c.text.tertiary,
              fontSize: '0.66rem',
              fontFamily: c.font.mono,
              flexShrink: 0,
            }}
          >
            {durationLabel}
          </Typography>
        )}

        {evidenceCount > 0 && (
          <TraceChip label={`${evidenceCount} evidence`} />
        )}

        <Tooltip title="Copy safe summary" arrow>
          <IconButton
            size="small"
            onClick={(event) => {
              event.stopPropagation();
              copySafeText(`${title}\n${summary}`);
            }}
            sx={{ color: c.text.tertiary, p: 0.2, flexShrink: 0 }}
          >
            <ContentCopyOutlinedIcon sx={{ fontSize: 12 }} />
          </IconButton>
        </Tooltip>

        <IconButton size="small" sx={{ color: c.text.tertiary, p: 0.2, flexShrink: 0 }} aria-label={expanded ? 'Collapse trace' : 'Expand trace'}>
          <ExpandMoreIcon
            sx={{
              fontSize: 11.2,
              transform: expanded ? 'rotate(0deg)' : 'rotate(-90deg)',
              transition: 'transform 0.2s ease',
            }}
          />
        </IconButton>
      </Box>

      <Collapse in={expanded} timeout={180}>
        <Box
          sx={{
            borderTop: `1px solid ${cardTokens.trace.border}`,
            px: compact ? cardTokens.trace.compactPx : cardTokens.trace.px,
            py: cardTokens.trace.panelPadding,
            bgcolor: cardTokens.trace.expandedBackground,
          }}
        >
          {!isDebugJsonTrace && (
            <Typography
              sx={{
                color: c.text.secondary,
                fontSize: '0.76rem',
                lineHeight: 1.55,
                mb: detailRows.length > 0 ? 1 : 0,
                whiteSpace: 'pre-wrap',
                overflowWrap: 'anywhere',
              }}
            >
              {summary}
            </Typography>
          )}

          {!isDebugJsonTrace && <RichTraceSections item={item} />}

          {isDebugJsonTrace && hasDebugDetails && (
            <Typography
              component="pre"
              sx={{
                m: 0,
                p: 0.75,
                border: `1px solid ${cardTokens.trace.border}`,
                borderRadius: cardTokens.trace.nestedRadius,
                bgcolor: cardTokens.trace.nestedBackground,
                color: c.text.tertiary,
                fontSize: '0.68rem',
                fontFamily: c.font.mono,
                whiteSpace: 'pre-wrap',
                overflowWrap: 'anywhere',
                maxHeight: 260,
                overflow: 'auto',
              }}
            >
              {stringifyDetail(sanitizedDebugDetails)}
            </Typography>
          )}

          {!isDebugJsonTrace && detailRows.length > 0 && (
            <Box sx={{ display: 'grid', gap: 0.45 }}>
              {detailRows.map(([label, value]) => (
                <Box
                  key={label}
                  sx={{
                    display: 'grid',
                    gridTemplateColumns: '92px minmax(0, 1fr)',
                    gap: 1,
                    alignItems: 'start',
                  }}
                >
                  <Typography sx={{ color: c.text.ghost, fontSize: '0.68rem', fontWeight: 700 }}>
                    {label}
                  </Typography>
                  <Typography
                    component="pre"
                    sx={{
                      m: 0,
                      color: c.text.tertiary,
                      fontSize: '0.68rem',
                      fontFamily: typeof value === 'object' ? c.font.mono : c.font.sans,
                      whiteSpace: typeof value === 'object' ? 'pre-wrap' : 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      overflowWrap: 'anywhere',
                    }}
                  >
                    {stringifyDetail(value)}
                  </Typography>
                </Box>
              ))}
            </Box>
          )}

          {!isDebugJsonTrace && (detailRows.length > 0 || summary) && (
            <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 0.85 }}>
              <Box
                component="button"
                type="button"
                onClick={(event) => {
                  event.stopPropagation();
                  copySafeText(copyDetailsText);
                }}
                sx={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 0.4,
                  border: 'none',
                  bgcolor: 'transparent',
                  color: c.text.ghost,
                  cursor: 'pointer',
                  fontFamily: c.font.sans,
                  fontSize: '0.64rem',
                  fontWeight: 700,
                  p: 0.2,
                  '&:hover': { color: c.text.tertiary },
                }}
              >
                <ContentCopyOutlinedIcon sx={{ fontSize: 11 }} />
                Copy details
              </Box>
            </Box>
          )}

          {!isDebugJsonTrace && hasDebugDetails && (
            <Box sx={{ mt: detailRows.length > 0 ? 0.9 : 0 }}>
              <Box
                component="button"
                type="button"
                onClick={(event) => {
                  event.stopPropagation();
                  setDebugExpanded((value) => !value);
                }}
                sx={{
                  width: '100%',
                  border: bare ? 'none' : `1px solid ${cardTokens.trace.border}`,
                  borderRadius: cardTokens.trace.nestedRadius,
                  bgcolor: bare ? 'transparent' : cardTokens.trace.background,
                  color: c.text.tertiary,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 1,
                  px: 0.75,
                  py: 0.55,
                  fontFamily: c.font.sans,
                  fontSize: '0.68rem',
                  fontWeight: 700,
                  textAlign: 'left',
                  '&:hover': { bgcolor: cardTokens.trace.headerHoverBackground },
          transition: 'background 0.15s ease',
                }}
              >
                <span>Debug data · redacted JSON</span>
                <ExpandMoreIcon
                  sx={{
                    fontSize: 10.4,
                    transform: debugExpanded ? 'rotate(0deg)' : 'rotate(-90deg)',
                    transition: 'transform 0.2s ease',
                    color: c.text.ghost,
                  }}
                />
              </Box>

              <Collapse in={debugExpanded} timeout={160}>
                <Typography
                  component="pre"
                  sx={{
                    mt: 0.65,
                    mb: 0,
                    p: 0.75,
                    border: bare ? 'none' : `1px solid ${cardTokens.trace.border}`,
                    borderRadius: cardTokens.trace.nestedRadius,
                    bgcolor: bare ? 'transparent' : cardTokens.trace.nestedBackground,
                    color: c.text.tertiary,
                    fontSize: '0.66rem',
                    fontFamily: c.font.mono,
                    whiteSpace: 'pre-wrap',
                    overflowWrap: 'anywhere',
                    maxHeight: 220,
                    overflow: 'auto',
                  }}
                >
                  {stringifyDetail(sanitizedDebugDetails)}
                </Typography>
              </Collapse>
            </Box>
          )}
        </Box>
      </Collapse>
    </Box>
  );
};

export type ProcessTraceTurnDropdownProps = {
  container?: ProcessTraceTurnContainer | null;
  title?: string;
  status?: ProcessTraceStatus | string;
  duration_ms?: number | null;
  items?: ProcessTraceItem[];
  defaultExpanded?: boolean;
  compact?: boolean;
  bare?: boolean;
};

export const ProcessTraceTurnDropdown: React.FC<ProcessTraceTurnDropdownProps> = ({
  container = null,
  title = 'Thought',
  status = 'completed',
  duration_ms = null,
  items = [],
  defaultExpanded,
  compact = true,
  bare = false,
}) => {
  const c = useClaudeTokens();
  const cardTokens = buildCardVisualTokens(c);
  const effectiveTitle = container?.title || title || 'Thought';
  const effectiveStatus = container?.status || status || 'completed';
  const effectiveDurationMs = container?.duration_ms ?? duration_ms ?? null;
  const effectiveItems = Array.isArray(container?.items) ? container.items : (Array.isArray(items) ? items : []);
  const containerHidden = Boolean(container?.internal_only || container?.visible_to_user === false);
  const normalizedStatus = normalizeStatus(effectiveStatus);
  const durationLabel = formatDurationMs(effectiveDurationMs);
  const [expanded, setExpanded] = useState(
    defaultExpanded
    ?? container?.default_expanded_while_running
    ?? (normalizedStatus === 'running' || normalizedStatus === 'failed' || normalizedStatus === 'warning'),
  );
  const [childExpandedOverride, setChildExpandedOverride] = useState<boolean | null>(null);

  const allVisibleItems = useMemo(
    () => effectiveItems.filter((item) => !item.internal_only && item.visible_to_user !== false),
    [effectiveItems],
  );
  const hiddenTraceItemCount = Math.max(0, allVisibleItems.length - MAX_VISIBLE_TURN_ITEMS);
  const visibleItems = useMemo(
    () => allVisibleItems.slice(0, MAX_VISIBLE_TURN_ITEMS),
    [allVisibleItems],
  );

  const statusColor = useMemo(() => {
    if (normalizedStatus === 'completed') return c.status.success;
    if (normalizedStatus === 'failed') return c.status.error;
    if (normalizedStatus === 'blocked' || normalizedStatus === 'warning') return c.status.warning;
    if (normalizedStatus === 'running') return c.accent.primary;
    return c.text.tertiary;
  }, [c, normalizedStatus]);

  if (containerHidden || allVisibleItems.length === 0) return null;

  const headerTitle = durationLabel
    ? `${redactTraceText(effectiveTitle)} durante ${durationLabel}`
    : redactTraceText(effectiveTitle);
  const turnMetaChips = [
    formatTraceTimestamp(container?.created_at || container?.started_at),
    STATUS_LABELS[normalizedStatus] || normalizedStatus,
    durationLabel,
    container?.metadata?.model ? `model: ${traceText(container.metadata.model)}` : '',
    container?.metadata?.mode ? `mode: ${traceText(container.metadata.mode)}` : '',
    container?.metadata?.provider ? `provider: ${traceText(container.metadata.provider)}` : '',
  ].filter(Boolean).slice(0, 5) as string[];
  const turnCopyText = [
    headerTitle,
    `Status: ${STATUS_LABELS[normalizedStatus] || normalizedStatus}`,
    durationLabel ? `Duration: ${durationLabel}` : '',
    ...visibleItems.map((item) => `- ${traceText(item.title || item.kind, 'Trace item')}: ${traceText(item.summary, '')}`),
    hiddenTraceItemCount > 0 ? `+${hiddenTraceItemCount} more trace items` : '',
  ].filter(Boolean).join('\n');

  return (
    <Box
      sx={{
        bgcolor: bare ? 'transparent' : cardTokens.trace.turnBackground,
        border: bare ? 'none' : `1px solid ${normalizedStatus === 'running' ? cardTokens.trace.runningBorder : cardTokens.trace.border}`,
        borderRadius: cardTokens.trace.turnRadius,
        overflow: 'hidden',
        boxShadow: bare ? 'none' : (normalizedStatus === 'running' ? cardTokens.trace.runningTurnShadow : cardTokens.trace.turnShadow),
        outline: bare ? 'none' : (normalizedStatus === 'running' ? `1px solid ${c.accent.primary}10` : 'none'),
      }}
    >
      <Box
        onClick={() => setExpanded((value) => !value)}
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 0.75,
          px: compact ? cardTokens.trace.compactPx : cardTokens.trace.px,
          py: compact ? cardTokens.trace.turnCompactPy : cardTokens.trace.py,
          cursor: 'pointer',
          userSelect: 'none',
          '&:hover': { bgcolor: bare ? 'transparent' : cardTokens.trace.headerHoverBackground },
          transition: 'background 0.15s ease',
        }}
      >
        <Tooltip title="Turn work trace" arrow>
          <Box
            sx={{
              width: 18,
              height: 18,
              borderRadius: '50%',
              display: 'grid',
              placeItems: 'center',
              flexShrink: 0,
              bgcolor: `${statusColor}18`,
              border: `1px solid ${statusColor}45`,
            }}
          >
            <TimelineOutlinedIcon sx={{ fontSize: 10.8, color: statusColor }} />
          </Box>
        </Tooltip>

        <StatusIcon status={normalizedStatus} color={statusColor} />

        <Typography
          noWrap
          sx={{
            color: c.text.primary,
            fontSize: compact ? '0.78rem' : '0.84rem',
            fontWeight: 700,
            minWidth: 0,
            flex: 1,
          }}
        >
          {headerTitle}
        </Typography>

        <Typography
          noWrap
          sx={{
            color: c.text.tertiary,
            fontSize: '0.66rem',
            fontWeight: 650,
            flexShrink: 0,
          }}
        >
          {allVisibleItems.length} paso{allVisibleItems.length === 1 ? '' : 's'}
        </Typography>

        {!compact && turnMetaChips.map((chip) => <TraceChip key={chip} label={chip} />)}

        <Tooltip title="Copy safe turn summary" arrow>
          <IconButton
            size="small"
            onClick={(event) => {
              event.stopPropagation();
              copySafeText(turnCopyText);
            }}
            sx={{ color: c.text.tertiary, p: 0.2, flexShrink: 0 }}
          >
            <ContentCopyOutlinedIcon sx={{ fontSize: 12 }} />
          </IconButton>
        </Tooltip>

        <IconButton size="small" sx={{ color: c.text.tertiary, p: 0.2, flexShrink: 0 }} aria-label={expanded ? 'Collapse turn trace' : 'Expand turn trace'}>
          <ExpandMoreIcon
            sx={{
              fontSize: 11.2,
              transform: expanded ? 'rotate(0deg)' : 'rotate(-90deg)',
              transition: 'transform 0.2s ease',
            }}
          />
        </IconButton>
      </Box>

      <Collapse in={expanded} timeout={180}>
        <Box sx={{ borderTop: bare ? 'none' : `1px solid ${cardTokens.trace.border}`, p: compact ? cardTokens.trace.compactPanelPadding : cardTokens.trace.panelPadding, bgcolor: bare ? 'transparent' : cardTokens.trace.background }}>
          {visibleItems.length > 1 && (
            <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 0.8, mb: 0.65 }}>
              {[
                ['Expand all', true],
                ['Collapse all', false],
              ].map(([label, value]) => (
                <Box
                  key={String(label)}
                  component="button"
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation();
                    setChildExpandedOverride(Boolean(value));
                  }}
                  sx={{
                    border: 'none',
                    bgcolor: 'transparent',
                    color: c.text.ghost,
                    cursor: 'pointer',
                    fontFamily: c.font.sans,
                    fontSize: '0.64rem',
                    fontWeight: 700,
                    p: 0.1,
                    '&:hover': { color: c.text.tertiary },
                  }}
                >
                  {String(label)}
                </Box>
              ))}
            </Box>
          )}
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: cardTokens.trace.itemGap }}>
            {visibleItems.map((item) => (
              <ProcessTraceDropdown
                key={`${item.trace_id || `${item.kind}-${item.title}`}-${childExpandedOverride}`}
                item={item}
                compact
                defaultExpanded={childExpandedOverride ?? (item.status === 'running' || item.status === 'blocked' || item.status === 'failed' || item.status === 'warning')}
                bare={bare}
              />
            ))}
            {hiddenTraceItemCount > 0 && (
              <Typography sx={{ color: c.text.ghost, fontSize: '0.66rem', textAlign: 'center', py: 0.4 }}>
                +{hiddenTraceItemCount} more trace items hidden for performance
              </Typography>
            )}
          </Box>
        </Box>
      </Collapse>
    </Box>
  );
};

export default ProcessTraceDropdown;
