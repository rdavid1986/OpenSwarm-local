import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import IconButton from '@mui/material/IconButton';
import Chip from '@mui/material/Chip';
import Button from '@mui/material/Button';
import CloseIcon from '@mui/icons-material/Close';
import MoreHorizIcon from '@mui/icons-material/MoreHoriz';
import DragIndicatorIcon from '@mui/icons-material/DragIndicator';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import {
  removeSwarmCard,
  setSwarmCardMode,
  setSwarmCardModel,
  setSwarmCardPosition,
  setSwarmCardSize,
  setSwarmCardSkillWorkspace,
  setSwarmCardSwarmId,
  toggleSwarmCardCollapsed,
} from '@/shared/state/dashboardLayoutSlice';
import {
  allowExperimentalApproval,
  chatExperimentalSwarm,
  createExperimentalSwarm,
  createOutputBridgeFromSwarm,
  denyExperimentalApproval,
  fetchExperimentalSwarm,
  resumeExperimentalApproval,
  startExperimentalImplementation,
} from '@/shared/state/experimentalSwarmsSlice';
import { renameDashboard } from '@/shared/state/dashboardsSlice';
import { openSettingsModal } from '@/shared/state/settingsSlice';
import { createCandidateOutputIteration, fetchOutputIterations, fetchOutputs, type OutputIterationRecord } from '@/shared/state/outputsSlice';
import { useAppDispatch, useAppSelector } from '@/shared/hooks';
import { useClaudeTokens } from '@/shared/styles/ThemeContext';
import type { CardType } from './useDashboardSelection';
import SwarmPromptInput from './SwarmPromptInput';
import { DEFAULT_SWARM_MODE, getSwarmModeOption } from './SwarmModePicker';
import type { SwarmMode } from '@/shared/state/dashboardLayoutSlice';
import { API_BASE } from '@/shared/config';
import ProcessTraceDropdown, { ProcessTraceItem, ProcessTraceTurnDropdown } from './ProcessTraceDropdown';
import { buildCardVisualTokens } from './cardVisualTokens';

type ResizeDir = 'n' | 's' | 'e' | 'w' | 'ne' | 'nw' | 'se' | 'sw';
type ImplementationVisualState =
  | 'ready'
  | 'running'
  | 'completed'
  | 'completed_with_output'
  | 'completed_without_output'
  | 'bridge_failed'
  | 'missing_flags'
  | 'failed'
  | 'verified'
  | 'unverified';

interface Props {
  swarmCardId: string;
  swarmId?: string | null;
  cardX: number;
  cardY: number;
  cardWidth: number;
  cardHeight: number;
  cardZOrder?: number;
  collapsed?: boolean;
  swarmMode?: SwarmMode;
  swarmModel?: string | null;
  previewOutputId?: string | null;
  skillWorkspaceId?: string | null;
  skillWorkspacePath?: string | null;
  zoom?: number;
  isSelected?: boolean;
  isHighlighted?: boolean;
  multiDragDelta?: { dx: number; dy: number } | null;
  onCardSelect?: (id: string, type: CardType, shiftKey: boolean) => void;
  onDragStart?: (id: string, type: CardType) => void;
  onDragMove?: (dx: number, dy: number, mouseX?: number, mouseY?: number) => void;
  onDragEnd?: (dx: number, dy: number, didDrag: boolean) => void;
  onBringToFront?: (id: string, type: CardType) => void;
  onDoubleClick?: (id: string, type: CardType) => void;
  onSwarmBound?: (patch: {
    swarmCardId: string;
    swarmId?: string | null;
    previewOutputId?: string | null;
    skillWorkspaceId?: string | null;
    skillWorkspacePath?: string | null;
    x?: number;
    y?: number;
    width?: number;
    height?: number;
  }) => void;
  onAddPreviewCard?: (outputId: string) => void;
  draftPrompt?: string | null;
  onDraftPromptConsumed?: () => void;
  dashboardId?: string;
}

const MIN_W = 520;
const MIN_H = 380;
const EDGE_THICKNESS = 6;
const CORNER_SIZE = 14;
const MIN_SIDE_W = 220;
const MAX_SIDE_W = 520;
const DEFAULT_SWARM_CONTEXT_LIMIT = 32_000;

const PREVIEW_REFINEMENT_MARKER = 'quiero refinar la app generada desde esta preview';
const SKILL_WORKSPACE_API = `${API_BASE}/skills`;

function stableSkillWorkspaceIdForSwarmCard(swarmCardId: string): string {
  const safeId = String(swarmCardId || 'swarm-main')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, '-')
    .replace(/^-+|-+$/g, '') || 'swarm-main';
  return `swarm-skill-ws-${safeId}`;
}

function parseCsvRefs(value: string | null | undefined): string[] {
  return (value || '')
    .split(',')
    .map((item) => item.trim())
    .filter((item) => item && item.toLowerCase() !== 'none' && item.toLowerCase() !== 'unknown');
}

function parsePreviewRefinementDraft(message: string): {
  outputId: string;
  outputName: string;
  sourceSwarmId: string;
  sourceTaskId: string;
  requestedChange: string;
  validationStatus: string;
  artifactRefs: string[];
  evidenceRefs: string[];
} | null {
  const lines = (message || '').split(/\r?\n/);
  const normalized = message.toLowerCase();
  if (!normalized.includes(PREVIEW_REFINEMENT_MARKER)) return null;

  const metadata: Record<string, string> = {};
  let requestedChange = '';
  let collectingChange = false;
  const metadataPrefixes = [
    'output id:',
    'output name:',
    'preset actual:',
    'source swarm:',
    'source task:',
    'validation status:',
    'artifacts:',
    'evidence:',
    'candidate iteration id:',
    'candidate workspace:',
    'base workspace:',
    'candidate reused:',
  ];

  for (const rawLine of lines) {
    const line = rawLine.trim();
    const lower = line.toLowerCase();
    const metadataPrefix = metadataPrefixes.find((prefix) => lower.startsWith(prefix));

    if (lower.startsWith('cambio solicitado:')) {
      collectingChange = true;
      requestedChange = line.split(':', 2)[1]?.trim() || '';
      continue;
    }

    if (metadataPrefix) {
      collectingChange = false;
      metadata[metadataPrefix.slice(0, -1)] = line.split(':', 2)[1]?.trim() || '';
      continue;
    }

    if (collectingChange && line) {
      requestedChange = [requestedChange, line].filter(Boolean).join('\n');
    }
  }

  const outputId = metadata['output id'] || '';
  const sourceSwarmId = metadata['source swarm'] || '';
  if (!outputId || !sourceSwarmId) return null;

  return {
    outputId,
    outputName: metadata['output name'] || '',
    sourceSwarmId,
    sourceTaskId: metadata['source task'] || '',
    requestedChange: requestedChange.trim(),
    validationStatus: metadata['validation status'] || '',
    artifactRefs: parseCsvRefs(metadata.artifacts),
    evidenceRefs: parseCsvRefs(metadata.evidence),
  };
}

function appendCandidateMetadataToRefinementDraft(
  message: string,
  candidate: OutputIterationRecord,
  reused: boolean,
): string {
  const statusLine = reused
    ? 'Refinamiento preparado para esta app. La candidate existente quedó disponible para revisión en Preview.'
    : 'Refinamiento preparado para esta app. Se creó una candidate para revisión en Preview.';
  const candidateMetadataLines = [
    statusLine,
    `Candidate iteration ID: ${candidate.iteration_id || ''}`,
    `Candidate workspace: ${candidate.candidate_workspace_path || ''}`,
    `Base workspace: ${candidate.base_workspace_path || ''}`,
    `Candidate reused: ${reused ? 'yes' : 'no'}`,
  ];
  const cleanLines = message
    .split('\n')
    .filter((line) => {
      const lower = line.trim().toLowerCase();
      return !(
        lower.startsWith('refinamiento preparado para esta app')
        || lower.startsWith('candidate iteration id:')
        || lower.startsWith('candidate workspace:')
        || lower.startsWith('base workspace:')
        || lower.startsWith('candidate reused:')
      );
    });

  const changeIndex = cleanLines.findIndex((line) => line.trim().toLowerCase().startsWith('cambio solicitado:'));
  if (changeIndex >= 0) {
    cleanLines.splice(changeIndex, 0, ...candidateMetadataLines, '');
    return cleanLines.join('\n').trimEnd();
  }

  return [
    cleanLines.join('\n').trimEnd(),
    '',
    ...candidateMetadataLines,
  ].join('\n');
}

function buildVisiblePreviewRefinementMessage(
  draft: ReturnType<typeof parsePreviewRefinementDraft>,
  _reused: boolean,
): string {
  if (!draft) return '';
  return draft.requestedChange.trim();
}

function buildInternalPreviewRefinementMessage(
  draft: ReturnType<typeof parsePreviewRefinementDraft>,
  requestedChange: string,
): string {
  if (!draft) return requestedChange;
  const artifactRefs = (draft.artifactRefs || []).join(', ') || 'none';
  const evidenceRefs = (draft.evidenceRefs || []).join(', ') || 'none';
  return [
    'Quiero refinar la app generada desde esta Preview.',
    '',
    `Output ID: ${draft.outputId}`,
    `Output name: ${draft.outputName || ''}`,
    `Source swarm: ${draft.sourceSwarmId}`,
    `Source task: ${draft.sourceTaskId || 'unknown'}`,
    `Validation status: ${draft.validationStatus || 'unknown'}`,
    `Artifacts: ${artifactRefs}`,
    `Evidence: ${evidenceRefs}`,
    '',
    'Cambio solicitado:',
    requestedChange,
  ].join('\n');
}

function emitOutputIterationsUpdated(outputId: string): void {
  window.dispatchEvent(new CustomEvent('openswarm:output-iterations-updated', { detail: { outputId } }));
}

function getSwarmMessageContextText(message: any): string {
  if (!message) return '';
  if (typeof message === 'string') return message;
  const payload = message.payload && typeof message.payload === 'object' ? message.payload : null;
  const content = payload?.content ?? message.content ?? message.text ?? '';
  if (typeof content === 'string') return content;
  try {
    return JSON.stringify(content);
  } catch {
    return '';
  }
}

function getSwarmModelContextLimit(model: string | null): number {
  const raw = String(model || '').toLowerCase();
  const directMatch = raw.match(/(\d+(?:\.\d+)?)\s*k/);
  if (directMatch) {
    return Math.max(1, Math.round(Number(directMatch[1]) * 1000));
  }
  if (raw.includes('1m') || raw.includes('1000000')) return 1_000_000;
  if (raw.includes('200k') || raw.includes('200000')) return 200_000;
  if (raw.includes('128k') || raw.includes('128000')) return 128_000;
  if (raw.includes('64k') || raw.includes('64000')) return 64_000;
  if (raw.includes('32k') || raw.includes('32000')) return 32_000;
  if (raw.includes('16k') || raw.includes('16000')) return 16_000;
  if (raw.includes('8k') || raw.includes('8000')) return 8_000;
  return DEFAULT_SWARM_CONTEXT_LIMIT;
}


const CURSOR_MAP: Record<ResizeDir, string> = {
  n: 'ns-resize',
  s: 'ns-resize',
  e: 'ew-resize',
  w: 'ew-resize',
  nw: 'nwse-resize',
  se: 'nwse-resize',
  ne: 'nesw-resize',
  sw: 'nesw-resize',
};

function renderText(value: any, fallback = ''): string {
  if (value == null) return fallback;
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (Array.isArray(value)) return value.map((item) => renderText(item)).filter(Boolean).join('\n');
  if (typeof value === 'object') {
    if (typeof value.summary === 'string') return value.summary;
    if (typeof value.text === 'string') return value.text;
    if (typeof value.content === 'string') return value.content;
    if (typeof value.message === 'string') return value.message;
    if (typeof value.value === 'string') return value.value;
    if (value.message) return renderText(value.message, fallback);
    if (value.response) return renderText(value.response, fallback);
    if (value.payload) return renderText(value.payload, fallback);
    return fallback;
  }
  return fallback;
}

function renderAnimatedText(value: string, baseDelayMs = 0): React.ReactNode {
  let visibleIndex = 0;

  return Array.from(value).map((char, idx) => {
    if (char === '\n') {
      return <br key={`line-${idx}`} />;
    }

    const delay = baseDelayMs + visibleIndex * 10.5;
    visibleIndex += 1;

    return (
      <Box
        key={`char-${idx}-${visibleIndex}`}
        component="span"
        sx={{
          display: 'inline',
          whiteSpace: char === ' ' ? 'pre' : 'normal',
          opacity: 0,
          animation: 'swarmCharReveal 0.16s ease-out forwards',
          animationDelay: `${delay}ms`,
          '@keyframes swarmCharReveal': {
            '0%': { opacity: 0, transform: 'translateY(2px)' },
            '100%': { opacity: 1, transform: 'translateY(0)' },
          },
        }}
      >
        {char === ' ' ? '\u00A0' : char}
      </Box>
    );
  });
}

function getVisibleSwarmMessageText(text: string): string {
  const normalized = renderText(text, '').trim();
  if (normalized === '__openswarm_pending_action__:confirm_refinement') return 'Confirmar cambio';
  if (normalized === '__openswarm_pending_action__:cancel_refinement') return 'Cancelar';
  return text;
}

function getSwarmMessageText(message: any): string {
  return renderText(
    message?.content ??
      message?.text ??
      message?.message ??
      message?.body ??
      message?.payload?.message?.content ??
      message?.payload?.response?.message?.content ??
      message?.payload?.response?.content ??
      message?.payload?.content,
    '',
  ).trim();
}

function getSwarmMessageRole(message: any): string {
  return String(
    message?.role ??
      message?.sender ??
      message?.payload?.role ??
      message?.payload?.message?.role ??
      message?.type ??
      '',
  ).toLowerCase();
}

function getSwarmMessageMetadata(message: any): {
  route: string;
  source: string;
  guard: boolean;
  reason: string;
  pendingAction: string;
  targetOutputId: string;
  availableActions: string[];
} {
  const payload = message?.payload || {};
  const route = renderText(payload.route ?? payload.message?.route ?? payload.response?.route, '').trim();
  const source = renderText(payload.source ?? payload.message?.source ?? payload.response?.source, '').trim();
  const guard = Boolean(payload.answer_guard_applied ?? payload.message?.answer_guard_applied ?? payload.response?.answer_guard_applied);
  const reason = renderText(payload.answer_guard_reason ?? payload.message?.answer_guard_reason ?? payload.response?.answer_guard_reason, '').trim();
  const riState = payload.ri_state || payload.message?.ri_state || payload.response?.ri_state || {};
  const pendingAction = renderText(riState.pending_action, '').trim();
  const targetOutputId = renderText(riState.target_output_id, '').trim();
  const availableActions = Array.isArray(riState.available_actions)
    ? riState.available_actions.map((action: any) => renderText(action, '').trim()).filter(Boolean)
    : [];

  return { route, source, guard, reason, pendingAction, targetOutputId, availableActions };
}

type McpRequiredUserAction = {
  actionType: string;
  target: string;
  label: string;
  reason: string;
  serverName: string;
};

function normalizeMcpRequiredUserAction(action: any): McpRequiredUserAction | null {
  if (!action || typeof action !== 'object') return null;
  const actionType = renderText(action.action_type ?? action.actionType ?? action.type, '').trim();
  const target = renderText(action.target ?? action.href ?? action.route, '').trim();
  const label = renderText(action.label ?? action.title ?? actionType, '').trim();
  const reason = renderText(action.reason ?? action.description, '').trim();
  const serverName = renderText(action.server_name ?? action.serverName ?? action.server, '').trim();
  if (!actionType && !target && !label) return null;
  return {
    actionType,
    target,
    label: label || 'Open action',
    reason,
    serverName,
  };
}

function collectMcpRequiredUserActionsFrom(value: any): McpRequiredUserAction[] {
  if (!value || typeof value !== 'object') return [];
  const rawActions = Array.isArray(value.required_user_actions)
    ? value.required_user_actions
    : Array.isArray(value.mcp_required_user_actions)
      ? value.mcp_required_user_actions
      : [];
  return rawActions
    .map(normalizeMcpRequiredUserAction)
    .filter(Boolean) as McpRequiredUserAction[];
}

function getMcpRequiredUserActions(message: any): McpRequiredUserAction[] {
  const payload = message?.payload || {};
  const response = payload.response || {};
  const riState = payload.ri_state || payload.message?.ri_state || response.ri_state || {};
  const sources = [
    payload,
    response,
    riState,
    payload.mcp_inspection,
    response.mcp_inspection,
    payload.mcp_fallback_plan,
    response.mcp_fallback_plan,
    payload.mcp_sandbox_policy,
    response.mcp_sandbox_policy,
    payload.mcp_evidence_bundle,
    response.mcp_evidence_bundle,
  ];

  const seen = new Set<string>();
  const actions: McpRequiredUserAction[] = [];
  for (const source of sources) {
    for (const action of collectMcpRequiredUserActionsFrom(source)) {
      const key = `${action.actionType}|${action.target}|${action.label}|${action.serverName}`;
      if (seen.has(key)) continue;
      seen.add(key);
      actions.push(action);
    }
  }
  return actions;
}

function getContextClarification(message: any): {
  question: string;
  options: any[];
  reason: string;
  creationType: string;
} {
  const payload = message?.payload || {};
  const clarification = payload.context_clarification
    || payload.message?.context_clarification
    || payload.response?.context_clarification
    || payload.final_result?.context_clarification
    || {};
  const options = Array.isArray(clarification.clarification_options)
    ? clarification.clarification_options
    : [];
  return {
    question: renderText(clarification.clarification_question, '').trim(),
    options,
    reason: renderText(clarification.reason, '').trim(),
    creationType: renderText(clarification.creation_type, '').trim(),
  };
}


function getPendingRefinementAction(message: any): {
  outputId: string;
  requestedChange: string;
  pendingAction: string;
  availableActions: string[];
} | null {
  const payload = message?.payload || {};
  const riState = payload.ri_state || payload.message?.ri_state || payload.response?.ri_state || {};
  const refinement = payload.refinement_request || payload.message?.refinement_request || payload.response?.refinement_request || {};
  const pendingAction = renderText(riState.pending_action || refinement.next_action, '').trim();
  const status = renderText(refinement.status, '').trim().toLowerCase();
  const availableActions = Array.isArray(riState.available_actions)
    ? riState.available_actions.map((action: any) => renderText(action, '').trim()).filter(Boolean)
    : [];
  const outputId = renderText(refinement.output_id || riState.target_output_id, '').trim();
  const requestedChange = renderText(refinement.requested_change, '').trim();
  const isPendingConfirm =
    pendingAction === 'confirm_refinement' ||
    availableActions.includes('confirm_refinement') ||
    (status === 'received' && Boolean(outputId));
  if (!isPendingConfirm || !outputId) return null;
  return { outputId, requestedChange, pendingAction: 'confirm_refinement', availableActions };
}

function getRefinementExecutionTrace(message: any): {
  status: string;
  reason: string;
  detail: string;
  providerReason: string;
  requiredAction: string;
  nextAction: string;
  candidateIterationId: string;
  filesChanged: string[];
  outputId: string;
} | null {
  const payload = message?.payload || {};
  const refinement = payload.refinement_request || payload.message?.refinement_request || payload.response?.refinement_request || {};
  const execution = payload.refinement_execution_result || payload.message?.refinement_execution_result || payload.response?.refinement_execution_result || {};
  const planner = execution.planner_result || {};
  const providerHealth = planner.provider_health || {};
  const status = renderText(execution.status || refinement.status, '').trim();
  const reason = renderText(execution.reason || planner.reason, '').trim();
  const detail = renderText(execution.detail || planner.status || planner.error_detail, '').trim();
  const providerReason = renderText(providerHealth.reason, '').trim();
  const requiredAction = renderText(providerHealth.required_action, '').trim();
  const nextAction = renderText(refinement.next_action, '').trim();
  const candidateIterationId = renderText(execution.candidate_iteration_id || refinement.candidate_iteration_id, '').trim();
  const outputId = renderText(refinement.output_id || execution.output_id, '').trim();
  const filesChanged = Array.isArray(execution.files_changed)
    ? execution.files_changed.map((item: any) => renderText(item, '').trim()).filter(Boolean)
    : [];

  if (!candidateIterationId && !status && !reason && nextAction !== 'review_candidate_diff') return null;

  return {
    status,
    reason,
    detail,
    providerReason,
    requiredAction,
    nextAction,
    candidateIterationId,
    filesChanged,
    outputId,
  };
}


function getSwarmProjectIntake(message: any): {
  question: any | null;
  options: any[];
  action: any | null;
  state: any | null;
} {
  const payload = message?.payload || {};
  return {
    question: payload.project_intake_question || null,
    options: Array.isArray(payload.project_intake_options) ? payload.project_intake_options : [],
    action: payload.project_intake_action || null,
    state: payload.project_intake_state || null,
  };
}

function humanizeStatus(value: any, fallback = 'pending'): string {
  const raw = renderText(value, fallback);
  const normalized = raw.replace(/_/g, ' ').trim();
  return normalized ? normalized.charAt(0).toUpperCase() + normalized.slice(1) : fallback;
}

function humanizeEvent(event: any): string {
  const type = renderText(event?.type, 'event');
  const title = renderText(event?.payload?.title || event?.payload?.tool || event?.payload?.status || event?.task_id, '');
  const labels: Record<string, string> = {
    dag_completed: 'Run completed',
    dag_started: 'Run started',
    dag_failed: 'Run failed',
    task_started: 'Task started',
    task_completed: 'Task completed',
    task_skipped: 'Task skipped',
    tool_started: 'Tool started',
    tool_completed: 'Tool completed',
    tool_failed: 'Tool failed',
    tool_approved: 'Tool approved',
    approval_required: 'Approval required',
    planner_validated: 'Plan validated',
    review_completed: 'Review completed',
    consolidation_started: 'Final summary started',
    consolidation_completed: 'Final summary completed',
    provider_response: 'Model response',
    provider_request: 'Model request',
  };
  const label = labels[type] || humanizeStatus(type, 'Event');
  return title ? `${label}: ${title}` : label;
}

function humanizeArtifact(artifact: any, fallback: string): string {
  return renderText(artifact?.name || artifact?.title || artifact?.path || artifact?.id, fallback);
}

function humanizeEvidence(evidence: any, fallback: string): string {
  const kindRaw = renderText(evidence?.kind || evidence?.type, 'evidence').trim();
  const kind = humanizeStatus(kindRaw, 'Evidence');

  if (kindRaw === 'artifact' && evidence?.artifact) {
    const artifactPath = renderText(evidence.artifact.path || evidence.artifact.id, 'artifact');
    const status = humanizeStatus(evidence.artifact.status, 'tracked');
    return `Artifact: ${artifactPath} · ${status}`;
  }

  if (kindRaw === 'review_result' && evidence?.review_result) {
    const artifactPath = renderText(evidence.review_result.artifact_path || evidence.review_result.artifact_id, 'artifact');
    const status = humanizeStatus(evidence.review_result.status, 'reviewed');
    return `Review: ${artifactPath} · ${status}`;
  }

  if (kindRaw === 'task_status' && Array.isArray(evidence?.tasks)) {
    const completed = evidence.tasks.filter((task: any) => task?.status === 'completed').length;
    return `Task status: ${completed}/${evidence.tasks.length} completed`;
  }

  if (kindRaw === 'tool_history_summary' && Array.isArray(evidence?.tools)) {
    const okTools = evidence.tools.filter((tool: any) => tool?.ok === true).length;
    return `Tool history: ${okTools}/${evidence.tools.length} successful`;
  }

  const path = renderText(
    evidence?.path ||
      evidence?.file_path ||
      evidence?.artifact?.path ||
      evidence?.review_result?.artifact_path ||
      evidence?.result?.path,
    '',
  );
  const tool = renderText(evidence?.tool || evidence?.tool_name || evidence?.result?.tool, '');
  if (path && tool) return `${kind}: ${tool} ${path}`;
  if (path) return `${kind}: ${path}`;
  if (tool) return `${kind}: ${tool}`;
  return renderText(evidence?.id || evidence?.summary, kind || fallback);
}

function normalizeStatusValue(value: any): string {
  return renderText(value, '').trim().toLowerCase();
}

function getClaimGuardStatus(finalResult: any): string {
  return normalizeStatusValue(finalResult?.claim_guard?.status);
}

function getImplementationStatus(swarm: any): string {
  return normalizeStatusValue(swarm?.implementation_state?.runner_status || swarm?.implementation?.status || swarm?.status);
}

function isTerminalImplementationState(status: string): boolean {
  return status === 'completed' || status === 'failed';
}


function buildMiniAgentInspectorProcessTraceItems(task: any, idx: number): ProcessTraceItem[] {
  const taskId = renderText(task?.id || task?.task_id || task?.name, `task-${idx + 1}`);
  const miniagentId = renderText(task?.miniagent_id || task?.mini_agent_id || task?.miniagent || task?.agent_id || task?.agent, '');
  const statusRaw = normalizeStatusValue(task?.status || task?.state || 'planned');
  const status: ProcessTraceItem['status'] =
    statusRaw === 'failed'
      ? 'failed'
      : statusRaw === 'blocked'
        ? 'blocked'
        : statusRaw === 'running'
          ? 'running'
          : statusRaw === 'completed'
            ? 'completed'
            : statusRaw === 'skipped'
              ? 'skipped'
              : 'planned';

  const title = renderText(task?.title || task?.name, `Task ${idx + 1}`);
  const description = renderText(task?.description || task?.summary || task?.goal, '').trim();
  const skillId = renderText(task?.skill_id || task?.assigned_skill_id || task?.skill?.id, '').trim();
  const skillName = renderText(task?.skill_name || task?.assigned_skill || task?.skill?.name || task?.skill, '').trim();
  const modeId = renderText(task?.mode_id || task?.mode, '').trim();
  const model = renderText(task?.model || task?.model_id || task?.provider_model, '').trim();
  const contextSummary = renderText(task?.context_summary || task?.context_packet?.summary || task?.context?.summary, '').trim();
  const microplan = renderText(task?.microplan || task?.plan || task?.steps, '').trim();
  const validation = renderText(task?.validation || task?.validation_summary || task?.validation_result, '').trim();
  const handoff = renderText(task?.handoff || task?.handoff_summary || task?.completed_work_summary, '').trim();
  const keyLearnings = renderText(task?.key_learnings || task?.learnings || task?.lessons, '').trim();

  const evidenceRefs = Array.isArray(task?.evidence_refs)
    ? task.evidence_refs.filter(Boolean)
    : Array.isArray(task?.evidence)
      ? task.evidence.map((item: any) => item?.id || item?.evidence_id || item?.ref || item?.path || item?.summary).filter(Boolean)
      : [];

  const artifactRefs = Array.isArray(task?.artifact_refs)
    ? task.artifact_refs.filter(Boolean)
    : Array.isArray(task?.artifacts)
      ? task.artifacts.map((item: any) => item?.id || item?.artifact_id || item?.path || item?.name).filter(Boolean)
      : [];

  const durationMs = typeof task?.duration_ms === 'number'
    ? task.duration_ms
    : typeof task?.runtime_ms === 'number'
      ? task.runtime_ms
      : typeof task?.elapsed_ms === 'number'
        ? task.elapsed_ms
        : null;

  const items: ProcessTraceItem[] = [
    {
      trace_id: `miniagent-task-${taskId}`,
      kind: 'summary',
      subsystem: 'TraceCore',
      title: 'MiniAgent task packet',
      summary: description || title,
      status,
      duration_ms: durationMs,
      icon_id: 'TraceCore',
      badge: humanizeStatus(statusRaw, 'planned'),
      related_task_id: taskId,
      related_miniagent_id: miniagentId || undefined,
      details: {
        task_id: taskId,
        miniagent_id: miniagentId || null,
        assignee: renderText(task?.agent || task?.assignee, '') || null,
        mode: modeId || null,
        model: model || null,
      },
    },
  ];

  if (contextSummary) {
    items.push({
      trace_id: `miniagent-context-${taskId}`,
      kind: 'context',
      subsystem: 'MemoryCore',
      title: 'Context packet',
      summary: contextSummary,
      status: 'completed',
      icon_id: 'MemoryCore',
      related_task_id: taskId,
      related_miniagent_id: miniagentId || undefined,
    });
  }

  if (skillId || skillName) {
    items.push({
      trace_id: `miniagent-skill-${taskId}`,
      kind: 'skill',
      subsystem: 'SkillCore',
      title: skillName || 'Assigned skill',
      summary: skillName ? `Assigned skill: ${skillName}` : `Assigned skill id: ${skillId}`,
      status: 'completed',
      icon_id: 'SkillCore',
      related_task_id: taskId,
      related_miniagent_id: miniagentId || undefined,
      related_skill_id: skillId || undefined,
      details: {
        skill_id: skillId || null,
        skill_name: skillName || null,
      },
    });
  }

  if (microplan) {
    items.push({
      trace_id: `miniagent-microplan-${taskId}`,
      kind: 'planning',
      subsystem: 'TraceCore',
      title: 'Microplan',
      summary: microplan,
      status: status === 'planned' ? 'planned' : 'completed',
      icon_id: 'TraceCore',
      related_task_id: taskId,
      related_miniagent_id: miniagentId || undefined,
    });
  }

  if (evidenceRefs.length > 0 || artifactRefs.length > 0) {
    items.push({
      trace_id: `miniagent-evidence-${taskId}`,
      kind: 'evidence',
      subsystem: 'EvidenceCore',
      title: 'Evidence and artifacts',
      summary: `${artifactRefs.length} artifacts · ${evidenceRefs.length} evidence refs.`,
      status: 'completed',
      icon_id: 'EvidenceCore',
      badge: 'evidence',
      related_task_id: taskId,
      related_miniagent_id: miniagentId || undefined,
      evidence_refs: evidenceRefs,
      artifact_refs: artifactRefs,
    });
  }

  if (validation) {
    items.push({
      trace_id: `miniagent-validation-${taskId}`,
      kind: 'validation',
      subsystem: 'ReviewCore',
      title: 'Validation',
      summary: validation,
      status: status === 'failed' ? 'failed' : 'completed',
      icon_id: 'ReviewCore',
      related_task_id: taskId,
      related_miniagent_id: miniagentId || undefined,
    });
  }

  if (handoff) {
    items.push({
      trace_id: `miniagent-handoff-${taskId}`,
      kind: 'handoff',
      subsystem: 'HandoffCore',
      title: 'Handoff',
      summary: handoff,
      status: 'completed',
      icon_id: 'HandoffCore',
      related_task_id: taskId,
      related_miniagent_id: miniagentId || undefined,
      evidence_refs: evidenceRefs,
    });
  }

  if (keyLearnings) {
    items.push({
      trace_id: `miniagent-learnings-${taskId}`,
      kind: 'review',
      subsystem: 'ReviewCore',
      title: 'Key learnings',
      summary: keyLearnings,
      status: 'completed',
      icon_id: 'ReviewCore',
      related_task_id: taskId,
      related_miniagent_id: miniagentId || undefined,
    });
  }

  return items.slice(0, 8);
}


function buildSwarmCardProcessTraceItems(params: {
  activeSwarm: any | null;
  activeSwarmId: string | null;
  activeSwarmMode: SwarmMode;
  activeSwarmModel: string | null;
  implementationLabel: string;
  implementationStatus: string;
  implementationVisualState: ImplementationVisualState;
  actionLoading: boolean;
  isImplementationActionRunning: boolean;
  swarmActionElapsedMs: number;
  lastSwarmActionDurationMs: number | null;
  lastSwarmActionWasImplementation: boolean;
  tasks: any[];
  approvals: any[];
  artifacts: any[];
  finalEvidence: any[];
  events: any[];
  finalResult: any;
  chatMessageCount: number;
}): ProcessTraceItem[] {
  const status: ProcessTraceItem['status'] = params.actionLoading
    ? 'running'
    : params.implementationVisualState === 'failed' || params.implementationVisualState === 'bridge_failed'
      ? 'failed'
      : params.implementationVisualState === 'missing_flags' || params.approvals.length > 0
        ? 'blocked'
        : params.implementationVisualState === 'idle'
          ? 'planned'
          : 'completed';

  const items: ProcessTraceItem[] = [
    {
      trace_id: `swarm-session-${params.activeSwarmId || 'new'}`,
      kind: 'summary',
      subsystem: 'SwarmCore',
      title: 'Swarm orchestration',
      summary: params.activeSwarmId
        ? `${params.implementationLabel} · ${params.chatMessageCount} visible messages`
        : 'New Swarm card waiting for a task.',
      status,
      duration_ms: params.actionLoading ? params.swarmActionElapsedMs : params.lastSwarmActionDurationMs,
      icon_id: 'SwarmCore',
      badge: params.implementationLabel,
      related_task_id: params.activeSwarmId || '',
      details: {
        mode: getSwarmModeOption(params.activeSwarmMode).label,
        model: params.activeSwarmModel || null,
        implementation_status: params.implementationStatus || null,
        events: params.events.length,
        tasks: params.tasks.length,
      },
    },
  ];

  if (params.actionLoading || params.lastSwarmActionDurationMs != null) {
    items.push({
      trace_id: `swarm-runtime-${params.activeSwarmId || 'new'}`,
      kind: 'metric',
      subsystem: 'MetricCore',
      title: params.actionLoading
        ? (params.isImplementationActionRunning ? 'Implementation running' : 'Thinking live')
        : (params.lastSwarmActionWasImplementation ? 'Implementation duration' : 'Thinking duration'),
      summary: params.actionLoading
        ? 'Swarm is currently processing this task.'
        : 'Latest visible Swarm duration captured in UI state.',
      status: params.actionLoading ? 'running' : 'completed',
      duration_ms: params.actionLoading ? params.swarmActionElapsedMs : params.lastSwarmActionDurationMs,
      icon_id: 'MetricCore',
      badge: params.actionLoading ? 'running' : 'duration',
      related_task_id: params.activeSwarmId || '',
      details: {
        implementation_action: params.isImplementationActionRunning,
        last_was_implementation: params.lastSwarmActionWasImplementation,
      },
    });
  }

  if (params.tasks.length > 0) {
    const completedTasks = params.tasks.filter((task: any) => normalizeStatusValue(task?.status) === 'completed').length;
    items.push({
      trace_id: `swarm-tasks-${params.activeSwarmId || 'new'}`,
      kind: 'worklog',
      subsystem: 'TraceCore',
      title: 'Task division',
      summary: `${completedTasks}/${params.tasks.length} tasks completed.`,
      status: completedTasks === params.tasks.length ? 'completed' : 'running',
      icon_id: 'TraceCore',
      badge: 'tasks',
      related_task_id: params.activeSwarmId || '',
      details: {
        total_tasks: params.tasks.length,
        completed_tasks: completedTasks,
      },
    });
  }

  if (params.approvals.length > 0) {
    items.push({
      trace_id: `swarm-approvals-${params.activeSwarmId || 'new'}`,
      kind: 'validation',
      subsystem: 'ReviewCore',
      title: 'Pending approvals',
      summary: `${params.approvals.length} approval${params.approvals.length === 1 ? '' : 's'} waiting for review.`,
      status: 'blocked',
      icon_id: 'ReviewCore',
      badge: 'review',
      related_task_id: params.activeSwarmId || '',
      details: {
        pending_approvals: params.approvals.length,
      },
    });
  }

  if (params.artifacts.length > 0 || params.finalEvidence.length > 0) {
    items.push({
      trace_id: `swarm-evidence-${params.activeSwarmId || 'new'}`,
      kind: 'evidence',
      subsystem: 'EvidenceCore',
      title: 'Artifacts and evidence',
      summary: `${params.artifacts.length} artifacts · ${params.finalEvidence.length} evidence refs.`,
      status: params.finalEvidence.length > 0 ? 'completed' : 'planned',
      icon_id: 'EvidenceCore',
      badge: 'evidence',
      related_task_id: params.activeSwarmId || '',
      artifact_refs: params.artifacts.map((artifact: any) => artifact?.id || artifact?.path || artifact?.name).filter(Boolean),
      evidence_refs: params.finalEvidence.map((evidence: any) => evidence?.id || evidence?.ref || evidence?.path || evidence?.summary).filter(Boolean),
      details: {
        artifacts: params.artifacts.length,
        final_evidence: params.finalEvidence.length,
      },
    });
  }

  if (params.finalResult && typeof params.finalResult === 'object') {
    const route = renderText(params.finalResult.route, '').trim();
    const artifactKind = renderText(params.finalResult.artifact_kind, '').trim();
    const verified = params.finalResult?.claim_guard?.status === 'verified';
    items.push({
      trace_id: `swarm-final-${params.activeSwarmId || 'new'}`,
      kind: 'review',
      subsystem: 'ReviewCore',
      title: 'Final result',
      summary: route || artifactKind || 'Final result available.',
      status: verified || params.implementationVisualState === 'verified' ? 'completed' : status,
      icon_id: 'ReviewCore',
      badge: verified ? 'verified' : 'final',
      related_task_id: params.activeSwarmId || '',
      details: {
        route: route || null,
        artifact_kind: artifactKind || null,
        claim_guard_status: params.finalResult?.claim_guard?.status || null,
      },
    });
  }

  return items.slice(0, 4);
}

function getImplementationVisualState(params: {
  hasSwarm: boolean;
  isRunning: boolean;
  implementationState: string;
  implementationStatus: string;
  claimGuardStatus: string;
  hasError: boolean;
}): ImplementationVisualState {
  if (params.isRunning) return 'running';
  if (params.implementationState === 'running') return 'running';
  if (params.implementationState === 'completed_with_output') return 'completed_with_output';
  if (params.implementationState === 'completed_without_output') return 'completed_without_output';
  if (params.implementationState === 'bridge_failed') return 'bridge_failed';
  if (params.implementationState === 'missing_flags') return 'missing_flags';
  if (params.implementationState === 'failed') return 'failed';
  if (params.hasError || params.implementationStatus === 'failed') return 'failed';
  if (params.implementationStatus === 'completed') {
    return params.claimGuardStatus === 'verified' ? 'verified' : 'unverified';
  }
  return 'ready';
}

const HANDLE_DEFS: { dir: ResizeDir; sx: Record<string, any> }[] = [
  { dir: 'n', sx: { top: -EDGE_THICKNESS / 2, left: CORNER_SIZE, right: CORNER_SIZE, height: EDGE_THICKNESS } },
  { dir: 's', sx: { bottom: -EDGE_THICKNESS / 2, left: CORNER_SIZE, right: CORNER_SIZE, height: EDGE_THICKNESS } },
  { dir: 'w', sx: { left: -EDGE_THICKNESS / 2, top: CORNER_SIZE, bottom: CORNER_SIZE, width: EDGE_THICKNESS } },
  { dir: 'e', sx: { right: -EDGE_THICKNESS / 2, top: CORNER_SIZE, bottom: CORNER_SIZE, width: EDGE_THICKNESS } },
  { dir: 'nw', sx: { top: -EDGE_THICKNESS / 2, left: -EDGE_THICKNESS / 2, width: CORNER_SIZE, height: CORNER_SIZE } },
  { dir: 'ne', sx: { top: -EDGE_THICKNESS / 2, right: -EDGE_THICKNESS / 2, width: CORNER_SIZE, height: CORNER_SIZE } },
  { dir: 'sw', sx: { bottom: -EDGE_THICKNESS / 2, left: -EDGE_THICKNESS / 2, width: CORNER_SIZE, height: CORNER_SIZE } },
  { dir: 'se', sx: { bottom: -EDGE_THICKNESS / 2, right: -EDGE_THICKNESS / 2, width: CORNER_SIZE, height: CORNER_SIZE } },
];

const ExperimentalSwarmCanvasCard: React.FC<Props> = ({
  swarmCardId,
  swarmId,
  cardX,
  cardY,
  cardWidth,
  cardHeight,
  cardZOrder = 0,
  collapsed = false,
  swarmMode = DEFAULT_SWARM_MODE,
  swarmModel = null,
  previewOutputId = null,
  skillWorkspaceId = null,
  skillWorkspacePath = null,
  zoom = 1,
  isSelected = false,
  isHighlighted = false,
  multiDragDelta,
  onCardSelect,
  onDragStart,
  onDragMove,
  onDragEnd,
  onBringToFront,
  onDoubleClick,
  onSwarmBound,
  onAddPreviewCard,
  draftPrompt,
  onDraftPromptConsumed,
  dashboardId,
}) => {
  const c = useClaudeTokens();
  const cardTokens = buildCardVisualTokens(c);
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const swarmState = useAppSelector((s) => s.experimentalSwarms);
  const dashboard = useAppSelector((s) => dashboardId ? s.dashboards.items[dashboardId] : undefined);
  const defaultModel = useAppSelector((s) => s.settings.data.default_model);

  const dragRef = useRef<{ sx: number; sy: number; ox: number; oy: number } | null>(null);
  const resizeRef = useRef<{
    dir: ResizeDir;
    sx: number;
    sy: number;
    ox: number;
    oy: number;
    ow: number;
    oh: number;
  } | null>(null);
  const sideResizeRef = useRef<{ sx: number; ow: number } | null>(null);
  const chatScrollRef = useRef<HTMLDivElement | null>(null);
  const chatEndRef = useRef<HTMLDivElement | null>(null);
  const startImplementationInFlightRef = useRef(false);
  const implementationPollingIntervalRef = useRef<number | null>(null);
  const implementationPollingRequestInFlightRef = useRef(false);

  const didDrag = useRef(false);
  const collapseClickTimerRef = useRef<number | null>(null);
  const suppressNextHeaderClickRef = useRef(false);
  const [isDragging, setIsDragging] = useState(false);
  const [localPos, setLocalPos] = useState<{ x: number; y: number } | null>(null);
  const [localSize, setLocalSize] = useState<{ x: number; y: number; w: number; h: number } | null>(null);
  const [sideWidth, setSideWidth] = useState(280);
  const [localSideWidth, setLocalSideWidth] = useState<number | null>(null);
  const [prompt, setPrompt] = useState('');
  const [customIntakeMode, setCustomIntakeMode] = useState(false);
  const promptInputRef = useRef<HTMLInputElement | HTMLTextAreaElement | null>(null);
  const [lastSubmittedPrompt, setLastSubmittedPrompt] = useState('');
  const [isStartingImplementation, setIsStartingImplementation] = useState(false);
  const [lastOutputBridgeOutputId, setLastOutputBridgeOutputId] = useState<string | null>(null);
  const [seenPreviewOutputId, setSeenPreviewOutputId] = useState<string | null>(previewOutputId || null);
  const [openPanelSections, setOpenPanelSections] = useState<Record<string, boolean>>({
    tasks: false,
    approvals: false,
    events: false,
    artifacts: false,
    evidence: false,
    finalResult: true,
  });

  const maybeRenameDashboardFromSwarmTitle = useCallback((title: any) => {
    if (!dashboardId || !dashboard) return;
    const nextName = renderText(title, '').trim();
    if (!nextName || nextName === dashboard.name) return;
    if (!dashboard.auto_named && dashboard.name !== 'Untitled Dashboard') return;
    dispatch(renameDashboard({
      id: dashboardId,
      name: nextName,
      previousName: dashboard.name,
      autoNamed: true,
    }));
  }, [dashboard, dashboardId, dispatch]);

  const [pendingPreviewRefinementDraft, setPendingPreviewRefinementDraft] = useState<ReturnType<typeof parsePreviewRefinementDraft> | null>(null);

  const activeSwarmMode = getSwarmModeOption(swarmMode).id;
  const activeSwarmModeRef = useRef<SwarmMode>(activeSwarmMode);
  activeSwarmModeRef.current = activeSwarmMode;
  const activeSwarmModel = swarmModel || defaultModel || null;

  useEffect(() => {
    if (!draftPrompt) return;
    const refinementDraft = parsePreviewRefinementDraft(draftPrompt);
    if (refinementDraft) {
      setPendingPreviewRefinementDraft({ ...refinementDraft, requestedChange: '' });
      setPrompt('');
      setCustomIntakeMode(false);
      window.setTimeout(() => promptInputRef.current?.focus(), 0);
      onDraftPromptConsumed?.();
      return;
    }

    setPendingPreviewRefinementDraft(null);
    setPrompt(draftPrompt);
    setCustomIntakeMode(false);
    window.setTimeout(() => promptInputRef.current?.focus(), 0);
    onDraftPromptConsumed?.();
  }, [draftPrompt, onDraftPromptConsumed]);

  const handleSwarmModeChange = useCallback((nextMode: SwarmMode) => {
    activeSwarmModeRef.current = nextMode;
    dispatch(setSwarmCardMode({ swarmCardId, swarmMode: nextMode }));
    setCustomIntakeMode(false);
  }, [dispatch, swarmCardId]);

  const handleSwarmModelChange = useCallback((nextModel: string) => {
    dispatch(setSwarmCardModel({ swarmCardId, swarmModel: nextModel }));
  }, [dispatch, swarmCardId]);

  const ensureSkillWorkspace = useCallback(async (): Promise<string | null> => {
    if (activeSwarmModeRef.current !== 'skill_builder') return skillWorkspacePath || null;
    if (skillWorkspacePath) return skillWorkspacePath;

    const workspaceId = skillWorkspaceId || stableSkillWorkspaceIdForSwarmCard(swarmCardId);
    try {
      const res = await fetch(`${SKILL_WORKSPACE_API}/workspace/seed`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ workspace_id: workspaceId }),
      });
      if (!res.ok) throw new Error(`Skill workspace seed failed: ${res.status}`);
      const data = await res.json();
      const nextPath = typeof data.path === 'string' && data.path.trim() ? data.path : null;
      if (!nextPath) throw new Error('Skill workspace seed response did not include path');

      // Persisted workspace is Skill Builder parity for SwarmCard, not skill installation.
      dispatch(setSwarmCardSkillWorkspace({
        swarmCardId,
        skillWorkspaceId: workspaceId,
        skillWorkspacePath: nextPath,
      }));
      onSwarmBound?.({
        swarmCardId,
        skillWorkspaceId: workspaceId,
        skillWorkspacePath: nextPath,
      });
      return nextPath;
    } catch (error) {
      console.warn('Failed to prepare Swarm Skill Builder workspace; continuing chat without workspace.', error);
      return null;
    }
  }, [dispatch, onSwarmBound, skillWorkspaceId, skillWorkspacePath, swarmCardId]);

  useEffect(() => {
    if (activeSwarmMode !== 'skill_builder') return;
    void ensureSkillWorkspace();
  }, [activeSwarmMode, ensureSkillWorkspace]);

  const activeSwarmId = swarmId || null;
  const activeSwarm = activeSwarmId && swarmState.swarm?.id === activeSwarmId ? swarmState.swarm : null;
  const hasLoadedActiveSwarm = Boolean(activeSwarm);
  const events = hasLoadedActiveSwarm ? swarmState.events.slice(-8).reverse() : [];
  const approvals = hasLoadedActiveSwarm ? swarmState.approvals.slice(0, 5) : [];
  const tasks = activeSwarm ? (activeSwarm.tasks || []) : [];
  const artifacts = hasLoadedActiveSwarm ? (swarmState.artifacts || []) : [];
  const finalEvidence = activeSwarm && Array.isArray((activeSwarm as any).final_evidence)
    ? (activeSwarm as any).final_evidence
    : [];
  const finalResult = activeSwarm ? activeSwarm.final_result : null;
  const implementationStatus = getImplementationStatus(activeSwarm);
  const persistedImplementationState = normalizeStatusValue((activeSwarm as any)?.implementation_state?.state);
  const claimGuardStatus = getClaimGuardStatus(finalResult);
  const evidenceLinked = Boolean((activeSwarm as any)?.orchestration_canvas_state?.evidence_linked);
  const implementationVisualState = getImplementationVisualState({
    hasSwarm: Boolean(activeSwarmId),
    isRunning: isStartingImplementation,
    implementationState: persistedImplementationState,
    implementationStatus,
    claimGuardStatus,
    hasError: Boolean(swarmState.error),
  });
  const implementationStateMeta: Record<ImplementationVisualState, { label: string; color: string; message: string }> = {
    ready: {
      label: activeSwarmId ? 'Listo' : 'Nuevo',
      color: c.text.tertiary,
      message: activeSwarmId ? 'Listo para iniciar implementación.' : 'Creá o vinculá un swarm para implementar.',
    },
    running: {
      label: 'Ejecutando',
      color: c.status.info,
      message: 'Implementación en ejecución. El botón queda bloqueado para evitar doble ejecución.',
    },
    completed: {
      label: 'Completado',
      color: c.status.success,
      message: 'Implementación completada.',
    },
    completed_with_output: {
      label: 'Output listo',
      color: c.status.success,
      message: 'Implementación completada con Output visualizable.',
    },
    completed_without_output: {
      label: 'Sin preview',
      color: c.status.warning,
      message: renderText((activeSwarm as any)?.implementation_state?.reason, 'Implementación completada sin Output visualizable.'),
    },
    bridge_failed: {
      label: 'Bridge falló',
      color: c.status.error,
      message: renderText((activeSwarm as any)?.implementation_state?.reason, 'Output Bridge validation failed.'),
    },
    missing_flags: {
      label: 'Flags faltantes',
      color: c.status.warning,
      message: renderText((activeSwarm as any)?.implementation_state?.reason, 'El backend actual no tiene los runners experimentales activos.'),
    },
    failed: {
      label: 'Falló',
      color: c.status.error,
      message: renderText((activeSwarm as any)?.implementation_state?.reason, 'La implementación falló. Revisá el error visible y la actividad reciente.'),
    },
    verified: {
      label: 'Verificado',
      color: c.status.success,
      message: 'Implementación completada y evidencia verificada.',
    },
    unverified: {
      label: 'No verificado',
      color: c.status.warning,
      message: evidenceLinked
        ? 'Implementación completada, pero la evidencia no quedó verificada por claim guard.'
        : 'Implementación completada con evidencia no verificada o no vinculada.',
    },
  };

  const implementationMeta = implementationStateMeta[implementationVisualState];
  const isImplementationActionRunning = isStartingImplementation || (swarmState.actionLoading && startImplementationInFlightRef.current);
  const [swarmActionStartedAt, setSwarmActionStartedAt] = useState<number | null>(null);
  const [swarmActionElapsedMs, setSwarmActionElapsedMs] = useState(0);
  const [lastSwarmActionDurationMs, setLastSwarmActionDurationMs] = useState<number | null>(null);
  const [lastSwarmActionWasImplementation, setLastSwarmActionWasImplementation] = useState(false);
  const isImplementationActionRunningRef = useRef(false);

  useEffect(() => {
    isImplementationActionRunningRef.current = isImplementationActionRunning;
  }, [isImplementationActionRunning]);

  useEffect(() => {
    if (!swarmState.actionLoading) {
      setSwarmActionStartedAt((previousStartedAt) => {
        if (previousStartedAt) {
          setLastSwarmActionDurationMs(Math.max(0, Date.now() - previousStartedAt));
          setLastSwarmActionWasImplementation(isImplementationActionRunningRef.current);
        }
        return null;
      });
      setSwarmActionElapsedMs(0);
      return;
    }

    const startedAt = Date.now();
    setSwarmActionStartedAt(startedAt);
    setSwarmActionElapsedMs(0);
    setLastSwarmActionDurationMs(null);
    setLastSwarmActionWasImplementation(isImplementationActionRunningRef.current);

    const interval = window.setInterval(() => {
      setSwarmActionElapsedMs(Math.max(0, Date.now() - startedAt));
    }, 100);

    return () => window.clearInterval(interval);
  }, [swarmState.actionLoading]);

  const formatSwarmActionDuration = useCallback((durationMs: number): string => {
    // UI displays a compact two-decimal label. Full precision remains in durationMs
    // for future persisted metrics and audit comparisons.
    const safeMs = Math.max(0, Math.round(durationMs));
    const seconds = safeMs / 1000;
    if (seconds < 60) return `${seconds.toFixed(2)}s`;
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds - minutes * 60;
    return `${minutes}m ${remainingSeconds.toFixed(2)}s`;
  }, []);

  const swarmActionElapsedLabel = formatSwarmActionDuration(swarmActionElapsedMs);
  const swarmActionStatusLabel = isImplementationActionRunning ? 'Implementation running' : 'Thinking';
  const lastSwarmActionLabel = lastSwarmActionDurationMs != null
    ? `${lastSwarmActionWasImplementation ? 'Implementation ran' : 'Thought'} for ${formatSwarmActionDuration(lastSwarmActionDurationMs)}`
    : null;

  const chatMessages = hasLoadedActiveSwarm
    ? (swarmState.messages || []).filter((message: any) => getVisibleSwarmMessageText(getSwarmMessageText(message)))
    : [];
  const swarmProcessTraceItems = useMemo(
    () => buildSwarmCardProcessTraceItems({
      activeSwarm,
      activeSwarmId,
      activeSwarmMode,
      activeSwarmModel,
      implementationLabel: implementationMeta.label,
      implementationStatus,
      implementationVisualState,
      actionLoading: swarmState.actionLoading,
      isImplementationActionRunning,
      swarmActionElapsedMs,
      lastSwarmActionDurationMs,
      lastSwarmActionWasImplementation,
      tasks,
      approvals,
      artifacts,
      finalEvidence,
      events,
      finalResult,
      chatMessageCount: chatMessages.length,
    }),
    [
      activeSwarm,
      activeSwarmId,
      activeSwarmMode,
      activeSwarmModel,
      implementationMeta.label,
      implementationStatus,
      implementationVisualState,
      swarmState.actionLoading,
      isImplementationActionRunning,
      swarmActionElapsedMs,
      lastSwarmActionDurationMs,
      lastSwarmActionWasImplementation,
      tasks,
      approvals,
      artifacts,
      finalEvidence,
      events,
      finalResult,
      chatMessages.length,
    ],
  );
  const finalRoute = typeof finalResult === 'object' && finalResult ? (finalResult as any).route : null;
  const finalAnswerGuardApplied = typeof finalResult === 'object' && finalResult ? (finalResult as any).answer_guard_applied : null;
  const showFinalResultDebugMetadata = false;
  const finalResponseSource = finalRoute && finalRoute !== 'normal_chat' ? 'local' : finalRoute === 'normal_chat' ? 'model' : null;
  const outputBridgeDecision = Array.isArray((activeSwarm as any)?.decisions)
    ? [...((activeSwarm as any).decisions || [])].reverse().find((decision: any) => (
      decision?.kind === 'output_bridge_created'
      && decision?.status === 'accepted'
      && decision?.metadata?.output_id
    ))
    : null;
  const outputBridgeOutputId = outputBridgeDecision?.metadata?.output_id || null;
  const activeSwarmOutputBridgeOutputId = (activeSwarm as any)?.output_bridge?.output_id || null;
  const refinementOutputId = finalResult && typeof finalResult === 'object'
    ? ((finalResult as any).refinement_request?.output_id || null)
    : null;
  const stableOutputBridgeOutputId = activeSwarmOutputBridgeOutputId || outputBridgeOutputId || lastOutputBridgeOutputId || previewOutputId || refinementOutputId || null;
  const shouldHighlightOpenPreview = Boolean(
    stableOutputBridgeOutputId
    && stableOutputBridgeOutputId !== seenPreviewOutputId
    && finalResult
    && typeof finalResult === 'object'
    && (
      persistedImplementationState === 'completed_with_output'
      || (finalResult as any).implementation_performed === true
      || Boolean((finalResult as any).refinement_request?.candidate_iteration_id)
      || (finalResult as any).refinement_request?.status === 'executed'
    )
  );

  useEffect(() => {
    setLastOutputBridgeOutputId(previewOutputId || null);
    setSeenPreviewOutputId(previewOutputId || null);
  }, [activeSwarmId, previewOutputId]);

  useEffect(() => {
    const persistentPreviewOutputId = activeSwarmOutputBridgeOutputId || outputBridgeOutputId || refinementOutputId || previewOutputId || null;
    if (persistentPreviewOutputId) {
      setLastOutputBridgeOutputId(persistentPreviewOutputId);
      onSwarmBound?.({ swarmCardId, previewOutputId: persistentPreviewOutputId });
    }
  }, [activeSwarmOutputBridgeOutputId, outputBridgeOutputId, onSwarmBound, previewOutputId, refinementOutputId, swarmCardId]);

  const canCreateOutputBridge = Boolean(
    activeSwarmId
    && !stableOutputBridgeOutputId
    && finalResult
    && typeof finalResult === 'object'
    && (finalResult as any).artifact_kind === 'static_app'
    && (finalResult as any).implementation_performed === true
    && (finalResult as any).claim_guard?.status === 'verified'
  );
  const shouldHideStartImplementationAction = Boolean(
    stableOutputBridgeOutputId
    || persistedImplementationState === 'completed_with_output'
    || persistedImplementationState === 'running'
  );
  const implementationErrors = Array.isArray((activeSwarm as any)?.implementation_state?.errors)
    ? (activeSwarm as any).implementation_state.errors
    : Array.isArray((activeSwarm as any)?.implementation?.errors)
      ? (activeSwarm as any).implementation.errors
      : [];
  const lastSubmittedAlreadyPersisted = !!activeSwarmId && !!lastSubmittedPrompt && chatMessages.some((message: any) => {
    const role = getSwarmMessageRole(message);
    return (role === 'user' || role === 'human') && getVisibleSwarmMessageText(getSwarmMessageText(message)) === lastSubmittedPrompt;
  });

  const contextEstimate = useMemo(() => {
    let totalChars = 0;
    for (const message of chatMessages) {
      totalChars += getSwarmMessageContextText(message).length;
    }
    if (lastSubmittedPrompt && !lastSubmittedAlreadyPersisted) {
      totalChars += lastSubmittedPrompt.length;
    }
    return {
      used: Math.round(totalChars / 4),
      limit: getSwarmModelContextLimit(activeSwarmModel),
    };
  }, [activeSwarmModel, chatMessages, lastSubmittedAlreadyPersisted, lastSubmittedPrompt]);


  const stopImplementationPolling = useCallback(() => {
    if (implementationPollingIntervalRef.current !== null) {
      window.clearInterval(implementationPollingIntervalRef.current);
      implementationPollingIntervalRef.current = null;
    }
    implementationPollingRequestInFlightRef.current = false;
  }, []);

  const pollImplementationSwarm = useCallback(async (swarmIdToPoll: string) => {
    if (implementationPollingRequestInFlightRef.current) return;

    implementationPollingRequestInFlightRef.current = true;
    try {
      await dispatch(fetchExperimentalSwarm(swarmIdToPoll));
    } finally {
      implementationPollingRequestInFlightRef.current = false;
    }
  }, [dispatch]);

  const startImplementationPolling = useCallback((swarmIdToPoll: string) => {
    if (implementationPollingIntervalRef.current !== null) return;

    void pollImplementationSwarm(swarmIdToPoll);
    implementationPollingIntervalRef.current = window.setInterval(() => {
      void pollImplementationSwarm(swarmIdToPoll);
    }, 2000);
  }, [pollImplementationSwarm]);

  useEffect(() => {
    if (!activeSwarmId) return;
    dispatch(fetchExperimentalSwarm(activeSwarmId));
  }, [activeSwarmId, dispatch]);

  useEffect(() => {
    return () => {
      stopImplementationPolling();
    };
  }, [activeSwarmId, stopImplementationPolling]);

  useEffect(() => {
    if (isTerminalImplementationState(implementationStatus) || swarmState.error) {
      stopImplementationPolling();
    }
  }, [implementationStatus, stopImplementationPolling, swarmState.error]);

  useEffect(() => {
    return () => {
      if (collapseClickTimerRef.current) {
        clearTimeout(collapseClickTimerRef.current);
        collapseClickTimerRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    const scrollToBottom = () => {
      const el = chatScrollRef.current;
      if (el) {
        el.scrollTop = el.scrollHeight;
      } else {
        chatEndRef.current?.scrollIntoView({ block: 'end' });
      }
    };
    scrollToBottom();
    window.setTimeout(scrollToBottom, 0);
  }, [chatMessages.length, events.length, lastSubmittedPrompt, swarmState.actionLoading]);

  const handleStart = useCallback(async () => {
    const cleanPrompt = prompt.trim();
    setCustomIntakeMode(false);
    if (!cleanPrompt && !activeSwarmId) return;

    let messageToSend = cleanPrompt || lastSubmittedPrompt || 'Continue';
    let visibleSubmittedPrompt = messageToSend;

    if (pendingPreviewRefinementDraft && cleanPrompt) {
      messageToSend = buildInternalPreviewRefinementMessage(pendingPreviewRefinementDraft, cleanPrompt);
      visibleSubmittedPrompt = cleanPrompt;
    }

    if (cleanPrompt) setPrompt('');

    let swarmIdToRun = activeSwarmId;
    const activeIntent = activeSwarm?.intent || null;
    const requestedMode = getSwarmModeOption(activeSwarmModeRef.current).id;
    const skillWorkspacePathToUse = requestedMode === 'skill_builder'
      ? await ensureSkillWorkspace()
      : null;

    const isPreviewRefinementMessage = Boolean(parsePreviewRefinementDraft(messageToSend));

    if (!swarmIdToRun || (cleanPrompt && activeIntent !== 'chat' && !isPreviewRefinementMessage)) {
      const action = await dispatch(createExperimentalSwarm({
        userPrompt: cleanPrompt || 'Experimental swarm',
        dashboardId,
        intent: 'chat',
        swarmMode: requestedMode,
        swarmModel: activeSwarmModel,
        workspacePath: skillWorkspacePathToUse,
      }));
      if (createExperimentalSwarm.fulfilled.match(action)) {
        swarmIdToRun = action.payload.id;
        dispatch(setSwarmCardSwarmId({ swarmCardId, swarmId: swarmIdToRun }));
        window.setTimeout(() => onSwarmBound?.({ swarmCardId, swarmId: swarmIdToRun }), 0);
      }
    }

    if (!swarmIdToRun) return;

    const refinementDraft = parsePreviewRefinementDraft(messageToSend);
    if (refinementDraft) {
      try {
        const existingIterations = await dispatch(fetchOutputIterations(refinementDraft.outputId)).unwrap();
        const latestCandidate = [...existingIterations]
          .reverse()
          .find((iteration) => iteration.status === 'candidate' && iteration.candidate_workspace_path);
        const candidate = latestCandidate || (await dispatch(createCandidateOutputIteration({
          outputId: refinementDraft.outputId,
          requestedChange: refinementDraft.requestedChange,
          sourceSwarmId: refinementDraft.sourceSwarmId,
          evidenceRefs: refinementDraft.evidenceRefs,
        })).unwrap()).iteration;
        const reusedCandidate = Boolean(latestCandidate);
        messageToSend = appendCandidateMetadataToRefinementDraft(messageToSend, candidate, reusedCandidate);
        visibleSubmittedPrompt = buildVisiblePreviewRefinementMessage(refinementDraft, reusedCandidate);
        setPendingPreviewRefinementDraft(null);
        emitOutputIterationsUpdated(refinementDraft.outputId);
      } catch (error) {
        console.error('Failed to prepare candidate iteration for Preview refinement', error);
        if (cleanPrompt) setPrompt(cleanPrompt);
        return;
      }
    }

    setLastSubmittedPrompt(visibleSubmittedPrompt);
    await dispatch(chatExperimentalSwarm({
      swarmId: swarmIdToRun,
      message: messageToSend,
      swarmMode: requestedMode,
      model: activeSwarmModel,
    }));
    dispatch(fetchExperimentalSwarm(swarmIdToRun));
  }, [activeSwarm?.intent, activeSwarmId, activeSwarmModel, dashboardId, dispatch, ensureSkillWorkspace, lastSubmittedPrompt, onSwarmBound, pendingPreviewRefinementDraft, prompt, swarmCardId]);

  useEffect(() => {
    const intakeStatus = (activeSwarm as any)?.project_intake_state?.status;
    const finalRoute = (activeSwarm as any)?.final_result?.route;
    const canUseSwarmTitle =
      intakeStatus === 'ready_to_implement' ||
      finalRoute === 'project_plan_ready' ||
      finalRoute === 'final_result';

    if (canUseSwarmTitle && activeSwarm?.title) {
      maybeRenameDashboardFromSwarmTitle(activeSwarm.title);
    }
  }, [activeSwarm, activeSwarm?.title, maybeRenameDashboardFromSwarmTitle]);

  const handleCreateOutputBridge = useCallback(async () => {
    if (!activeSwarmId || !activeSwarm) return;
    const action = await dispatch(createOutputBridgeFromSwarm({
      swarmId: activeSwarmId,
      name: `${renderText(activeSwarm.title, 'OpenSwarm App')}`,
      description: 'Static safe Output generated from verified Swarm static_app.',
    }));
    if (createOutputBridgeFromSwarm.fulfilled.match(action)) {
      const outputId = action.payload?.output_id;
      await dispatch(fetchExperimentalSwarm(activeSwarmId));
      await dispatch(fetchOutputs());
      if (outputId) {
        onAddPreviewCard?.(outputId);
      }
    }
  }, [activeSwarm, activeSwarmId, dispatch, onAddPreviewCard]);

  const handleOpenOutputPreview = useCallback(async () => {
    if (stableOutputBridgeOutputId) {
      setSeenPreviewOutputId(stableOutputBridgeOutputId);
      await dispatch(fetchOutputs());
      onAddPreviewCard?.(stableOutputBridgeOutputId);
      return;
    }
    if (canCreateOutputBridge) {
      await handleCreateOutputBridge();
    }
  }, [canCreateOutputBridge, dispatch, handleCreateOutputBridge, onAddPreviewCard, stableOutputBridgeOutputId]);

  const handleProjectIntakeOption = useCallback(async (option: any) => {
    const label = renderText(option?.label ?? option?.value, '').trim();
    const value = renderText(option?.value ?? option?.label, '').trim();
    if (!label) return;
    if (value === '__custom__') {
      setPrompt('');
      setCustomIntakeMode(true);
      window.setTimeout(() => promptInputRef.current?.focus(), 0);
      return;
    }
    if (!activeSwarmId || swarmState.actionLoading) return;

    setLastSubmittedPrompt(label);
    const requestedMode = getSwarmModeOption(activeSwarmModeRef.current).id;
    await dispatch(chatExperimentalSwarm({ swarmId: activeSwarmId, message: label, swarmMode: requestedMode, model: activeSwarmModel }));
    dispatch(fetchExperimentalSwarm(activeSwarmId));
  }, [activeSwarmId, activeSwarmModel, dispatch, swarmState.actionLoading]);

  const handleContextClarificationOption = useCallback(async (option: any) => {
    const label = renderText(option?.label ?? option?.value, '').trim();
    const value = renderText(option?.value ?? option?.label, '').trim();
    if (!label) return;
    if (value === '__custom__') {
      setPrompt('');
      setCustomIntakeMode(true);
      window.setTimeout(() => promptInputRef.current?.focus(), 0);
      return;
    }
    if (!activeSwarmId || swarmState.actionLoading) return;

    setLastSubmittedPrompt(label);
    const requestedMode = getSwarmModeOption(activeSwarmModeRef.current).id;
    await dispatch(chatExperimentalSwarm({ swarmId: activeSwarmId, message: label, swarmMode: requestedMode, model: activeSwarmModel }));
    dispatch(fetchExperimentalSwarm(activeSwarmId));
  }, [activeSwarmId, activeSwarmModel, dispatch, swarmState.actionLoading]);

  const handlePendingRefinementAction = useCallback(async (
    action: 'confirm' | 'edit' | 'cancel',
    pending: { requestedChange: string },
  ) => {
    if (action === 'edit') {
      setPrompt(pending.requestedChange || '');
      window.setTimeout(() => promptInputRef.current?.focus(), 0);
      return;
    }
    if (!activeSwarmId || swarmState.actionLoading) return;
    const message = action === 'confirm'
      ? '__openswarm_pending_action__:confirm_refinement'
      : '__openswarm_pending_action__:cancel_refinement';
    const label = action === 'confirm' ? 'Confirmar cambio' : 'Cancelar';
    setLastSubmittedPrompt(label);
    const requestedMode = getSwarmModeOption(activeSwarmModeRef.current).id;
    await dispatch(chatExperimentalSwarm({
      swarmId: activeSwarmId,
      message,
      swarmMode: requestedMode,
      model: activeSwarmModel,
    }));
    dispatch(fetchExperimentalSwarm(activeSwarmId));
  }, [activeSwarmId, activeSwarmModel, dispatch, swarmState.actionLoading]);

  const handleMcpRequiredUserAction = useCallback((action: McpRequiredUserAction) => {
    const actionType = action.actionType.toLowerCase();
    const target = action.target.toLowerCase();

    if (
      actionType === 'open_settings' ||
      actionType === 'activate_mcp' ||
      actionType === 'connect_account' ||
      actionType === 'review_permissions' ||
      target.startsWith('tools/') ||
      target.includes('/mcp/')
    ) {
      navigate('/actions');
      return;
    }

    dispatch(openSettingsModal('tools'));
  }, [dispatch, navigate]);

  const handleStartImplementation = useCallback(async (action?: any) => {
    if (!activeSwarmId || swarmState.actionLoading || startImplementationInFlightRef.current) return;
    if (action?.enabled === false) return;

    startImplementationInFlightRef.current = true;
    setIsStartingImplementation(true);
    startImplementationPolling(activeSwarmId);
    try {
      const implementationResult = await dispatch(startExperimentalImplementation({ swarmId: activeSwarmId, model: activeSwarmModel })).unwrap();
      const outputId = implementationResult?.output_bridge?.output_id || implementationResult?.output_bridge?.metadata?.output_id || null;
      if (outputId) {
        setLastOutputBridgeOutputId(outputId);
        setSeenPreviewOutputId(outputId);
        onSwarmBound?.({ swarmCardId, previewOutputId: outputId });
        await dispatch(fetchOutputs());
        onAddPreviewCard?.(outputId);
      }
      await dispatch(fetchExperimentalSwarm(activeSwarmId));
    } catch {
      // Error state is stored by the slice matcher and rendered in this card.
    } finally {
      stopImplementationPolling();
      startImplementationInFlightRef.current = false;
      setIsStartingImplementation(false);
    }
  }, [activeSwarmId, dispatch, onAddPreviewCard, onSwarmBound, startImplementationPolling, stopImplementationPolling, swarmCardId, swarmState.actionLoading]);

  const handleApprovalAction = useCallback(async (
    approvalId: string,
    actionType: 'allow' | 'deny' | 'resume',
  ) => {
    if (!activeSwarmId) return;

    if (actionType === 'allow') {
      await dispatch(allowExperimentalApproval({ swarmId: activeSwarmId, approvalId }));
    } else if (actionType === 'deny') {
      await dispatch(denyExperimentalApproval({ swarmId: activeSwarmId, approvalId }));
    } else {
      await dispatch(resumeExperimentalApproval({ swarmId: activeSwarmId, approvalId }));
    }

    dispatch(fetchExperimentalSwarm(activeSwarmId));
  }, [activeSwarmId, dispatch]);

  const computeResize = useCallback((e: React.PointerEvent) => {
    if (!resizeRef.current) return null;

    const { dir, sx, sy, ox, oy, ow, oh } = resizeRef.current;
    const dx = (e.clientX - sx) / zoom;
    const dy = (e.clientY - sy) / zoom;

    let x = ox;
    let y = oy;
    let w = ow;
    let h = oh;

    if (dir.includes('e')) w = ow + dx;
    if (dir.includes('w')) {
      w = ow - dx;
      x = ox + dx;
    }
    if (dir.includes('s')) h = oh + dy;
    if (dir.includes('n')) {
      h = oh - dy;
      y = oy + dy;
    }

    if (w < MIN_W) {
      if (dir.includes('w')) x = ox + ow - MIN_W;
      w = MIN_W;
    }
    if (h < MIN_H) {
      if (dir.includes('n')) y = oy + oh - MIN_H;
      h = MIN_H;
    }

    return { x, y, w, h };
  }, [zoom]);

  const closeOpenDropdowns = useCallback(() => {
    const close = () => {
      try {
        (document.activeElement as HTMLElement | null)?.blur?.();
        const keyOptions = { key: 'Escape', code: 'Escape', keyCode: 27, which: 27, bubbles: true, cancelable: true };
        window.dispatchEvent(new KeyboardEvent('keydown', keyOptions));
        document.dispatchEvent(new KeyboardEvent('keydown', keyOptions));
        window.dispatchEvent(new KeyboardEvent('keyup', keyOptions));
        document.dispatchEvent(new KeyboardEvent('keyup', keyOptions));
        document.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, cancelable: true }));
        document.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true }));
        document.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
      } catch {}
    };

    close();
    window.setTimeout(close, 0);
  }, []);

  const handleDragDown = useCallback((e: React.PointerEvent) => {
    if (e.button !== 0) return;
    const target = e.target as HTMLElement | null;
    if (!target?.closest('.swarm-drag-handle')) return;
    if (target.closest('button')) return;

    closeOpenDropdowns();
    e.stopPropagation();
    dragRef.current = { sx: e.clientX, sy: e.clientY, ox: cardX, oy: cardY };
    didDrag.current = false;
    setIsDragging(true);
    onDragStart?.(swarmCardId, 'swarm');
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  }, [cardX, cardY, closeOpenDropdowns, onDragStart, swarmCardId]);

  const handlePointerMove = useCallback((e: React.PointerEvent) => {
    if (dragRef.current) {
      const dx = (e.clientX - dragRef.current.sx) / zoom;
      const dy = (e.clientY - dragRef.current.sy) / zoom;
      if (!didDrag.current && Math.sqrt(dx * dx + dy * dy) < 3) return;
      didDrag.current = true;
      setLocalPos({ x: dragRef.current.ox + dx, y: dragRef.current.oy + dy });
      onDragMove?.(dx, dy, e.clientX, e.clientY);
    }

    if (resizeRef.current) {
      const result = computeResize(e);
      if (result) setLocalSize(result);
    }

    if (sideResizeRef.current) {
      const next = sideResizeRef.current.ow - (e.clientX - sideResizeRef.current.sx) / zoom;
      setLocalSideWidth(Math.max(MIN_SIDE_W, Math.min(MAX_SIDE_W, next)));
    }
  }, [computeResize, onDragMove, zoom]);

  const handlePointerUp = useCallback((e: React.PointerEvent) => {
    if (dragRef.current) {
      const dx = (e.clientX - dragRef.current.sx) / zoom;
      const dy = (e.clientY - dragRef.current.sy) / zoom;
      if (didDrag.current) {
        const x = Math.round((dragRef.current.ox + dx) / 24) * 24;
        const y = Math.round((dragRef.current.oy + dy) / 24) * 24;
        dispatch(setSwarmCardPosition({ swarmCardId, x, y }));
        window.setTimeout(() => onSwarmBound?.({ swarmCardId, x, y }), 0);
        suppressNextHeaderClickRef.current = true;
      }
      onDragEnd?.(dx, dy, didDrag.current);
      dragRef.current = null;
      didDrag.current = false;
      setLocalPos(null);
      setIsDragging(false);
    }

    if (resizeRef.current && localSize) {
      const x = Math.round(localSize.x);
      const y = Math.round(localSize.y);
      const width = Math.round(localSize.w);
      const height = Math.round(localSize.h);
      dispatch(setSwarmCardPosition({ swarmCardId, x, y }));
      dispatch(setSwarmCardSize({ swarmCardId, width, height }));
      window.setTimeout(() => onSwarmBound?.({ swarmCardId, x, y, width, height }), 0);
      resizeRef.current = null;
      setLocalSize(null);
    }

    if (sideResizeRef.current && localSideWidth != null) {
      setSideWidth(localSideWidth);
      sideResizeRef.current = null;
      setLocalSideWidth(null);
    }

    try { (e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId); } catch {}
  }, [dispatch, localSideWidth, localSize, onDragEnd, onSwarmBound, swarmCardId, zoom]);

  const handleResizeDown = useCallback((dir: ResizeDir) => (e: React.PointerEvent) => {
    if (e.button !== 0) return;
    e.preventDefault();
    e.stopPropagation();
    resizeRef.current = {
      dir,
      sx: e.clientX,
      sy: e.clientY,
      ox: cardX,
      oy: cardY,
      ow: cardWidth,
      oh: cardHeight,
    };
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  }, [cardX, cardY, cardWidth, cardHeight]);

  const handleSideResizeDown = useCallback((e: React.PointerEvent) => {
    if (e.button !== 0) return;
    e.preventDefault();
    e.stopPropagation();
    sideResizeRef.current = { sx: e.clientX, ow: localSideWidth ?? sideWidth };
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  }, [localSideWidth, sideWidth]);

  const mdDx = isSelected && multiDragDelta ? multiDragDelta.dx : 0;
  const mdDy = isSelected && multiDragDelta ? multiDragDelta.dy : 0;
  const displayX = localSize?.x ?? localPos?.x ?? (cardX + mdDx);
  const displayY = localSize?.y ?? localPos?.y ?? (cardY + mdDy);
  const displayW = localSize?.w ?? cardWidth;
  const displayH = collapsed ? 64 : (localSize?.h ?? cardHeight);
  const displaySideW = localSideWidth ?? sideWidth;

  const togglePanelSection = useCallback((section: string) => {
    setOpenPanelSections((prev) => ({ ...prev, [section]: !prev[section] }));
  }, []);

  const renderPanelHeader = useCallback((section: string, title: string, count?: number) => (
    <Box
      onClick={() => togglePanelSection(section)}
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 1,
        cursor: 'pointer',
        userSelect: 'none',
        py: 0.75,
      }}
    >
      <Typography sx={{ fontWeight: 650, fontSize: '0.82rem' }}>
        {title}{typeof count === 'number' ? ` · ${count}` : ''}
      </Typography>
      {openPanelSections[section] ? <ExpandMoreIcon sx={{ fontSize: 18 }} /> : <ChevronRightIcon sx={{ fontSize: 18 }} />}
    </Box>
  ), [openPanelSections, togglePanelSection]);

  return (
    <Box
      data-select-type="swarm-card"
      data-select-id={swarmCardId}
      onPointerDownCapture={() => onBringToFront?.(swarmCardId, 'swarm')}
      onClick={(e) => onCardSelect?.(swarmCardId, 'swarm', e.shiftKey)}
      onPointerDown={handleDragDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerCancel={handlePointerUp}
      sx={{
        position: 'absolute',
        left: displayX,
        top: displayY,
        width: displayW,
        height: displayH,
        zIndex: isDragging ? 999999 : cardZOrder,
        bgcolor: cardTokens.surface.background,
        border: `1px solid ${isSelected ? cardTokens.surface.selectedBorder : cardTokens.surface.border}`,
        borderRadius: cardTokens.surface.radius,
        overflow: 'hidden',
        boxShadow: isHighlighted ? cardTokens.surface.highlightedShadow : cardTokens.surface.shadow,
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {isDragging && (
        <Box
          onPointerDown={handleDragDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerCancel={handlePointerUp}
          sx={{
            position: 'absolute',
            inset: 0,
            zIndex: 40,
            cursor: 'grabbing',
            touchAction: 'none',
          }}
        />
      )}

      <Box
        className="swarm-drag-handle"
        onClick={(e) => {
          e.stopPropagation();
          if (suppressNextHeaderClickRef.current) {
            suppressNextHeaderClickRef.current = false;
            return;
          }
          if (collapseClickTimerRef.current) {
            clearTimeout(collapseClickTimerRef.current);
            collapseClickTimerRef.current = null;
          }
          collapseClickTimerRef.current = window.setTimeout(() => {
            collapseClickTimerRef.current = null;
            dispatch(toggleSwarmCardCollapsed(swarmCardId));
          }, 360);
        }}
        onDoubleClick={(e) => {
          e.stopPropagation();
          if (collapseClickTimerRef.current) {
            clearTimeout(collapseClickTimerRef.current);
            collapseClickTimerRef.current = null;
          }
          onDoubleClick?.(swarmCardId, 'swarm');
        }}
        onPointerDown={handleDragDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
        sx={{
          px: cardTokens.surface.headerPaddingX,
          py: cardTokens.surface.headerPaddingY,
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          borderBottom: collapsed ? 'none' : `1px solid ${cardTokens.surface.border}`,
          cursor: isDragging ? 'grabbing' : 'grab',
          touchAction: 'none',
          userSelect: 'none',
        }}
      >
        <Box
          className="drag-handle"
          sx={{
            display: 'flex',
            alignItems: 'center',
            color: cardTokens.polish.mutedActionColor,
            flexShrink: 0,
          }}
        >
          <DragIndicatorIcon sx={{ fontSize: 16 }} />
        </Box>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, minWidth: 0 }}>
            <Typography sx={{ fontWeight: 650, fontSize: '0.95rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: c.text.primary }}>
              Swarm
            </Typography>
            <Chip
              size="small"
              label={getSwarmModeOption(activeSwarmMode).label}
              sx={{
                height: 22,
                fontSize: '0.68rem',
                fontWeight: 650,
                color: c.text.secondary,
                bgcolor: cardTokens.polish.subtleChipBackground,
                border: `1px solid ${cardTokens.polish.subtleChipBorder}`,
                flexShrink: 0,
              }}
            />
            <Chip
              size="small"
              label={implementationMeta.label}
              sx={{
                height: 22,
                fontSize: '0.68rem',
                color: implementationMeta.color,
                bgcolor: `${implementationMeta.color}18`,
                border: `1px solid ${implementationMeta.color}55`,
                fontWeight: 650,
                flexShrink: 0,
              }}
            />
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25, mt: 0.25, minWidth: 0 }}>
            <Typography sx={{ color: c.text.tertiary, fontSize: '0.72rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {activeSwarmModel || 'No model selected'}
            </Typography>
            {swarmState.actionLoading && (
              <Typography sx={{ color: c.text.tertiary, fontSize: '0.72rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flexShrink: 0 }}>
                {swarmActionStatusLabel} · {swarmActionElapsedLabel}
              </Typography>
            )}
          </Box>
        </Box>
        {(stableOutputBridgeOutputId || canCreateOutputBridge) && (
          <Button
            size="small"
            variant="outlined"
            onClick={(e) => {
              e.stopPropagation();
              handleOpenOutputPreview();
            }}
            onPointerDown={(e) => e.stopPropagation()}
            sx={{
              minHeight: 28,
              px: 1.2,
              py: 0.25,
              borderRadius: cardTokens.trace.radius,
              bgcolor: cardTokens.surface.background,
              color: c.text.primary,
              borderColor: shouldHighlightOpenPreview ? c.accent.primary : c.border.medium,
              boxShadow: shouldHighlightOpenPreview ? `0 0 0 1px ${c.accent.primary}22, 0 0 10px ${c.accent.primary}12` : c.shadow.sm,
              animation: shouldHighlightOpenPreview ? 'previewAttentionBreath 2.25s ease-in-out infinite' : 'none',
              '@keyframes previewAttentionBreath': {
                '0%': { boxShadow: `0 0 0 1px ${c.accent.primary}10, 0 0 4px ${c.accent.primary}08` },
                '50%': { boxShadow: `0 0 0 1px ${c.accent.primary}77, 0 0 18px ${c.accent.primary}38` },
                '100%': { boxShadow: `0 0 0 1px ${c.accent.primary}10, 0 0 4px ${c.accent.primary}08` },
              },
              fontSize: '0.74rem',
              fontWeight: 500,
              textTransform: 'none',
              flexShrink: 0,
              cursor: 'pointer',
              '&:hover': {
                bgcolor: cardTokens.polish.hoverBackground,
                borderColor: cardTokens.surface.selectedBorder,
                boxShadow: cardTokens.surface.shadow,
              },
            }}
          >
            Open Preview
          </Button>
        )}

        <IconButton
          size="small"
          onClick={(e) => e.stopPropagation()}
          onPointerDown={(e) => e.stopPropagation()}
          onDoubleClick={(e) => e.stopPropagation()}
        >
          <MoreHorizIcon fontSize="small" />
        </IconButton>
        <IconButton
          size="small"
          onClick={(e) => {
            e.stopPropagation();
            dispatch(removeSwarmCard(swarmCardId));
          }}
          onPointerDown={(e) => e.stopPropagation()}
          onDoubleClick={(e) => e.stopPropagation()}
        >
          <CloseIcon fontSize="small" />
        </IconButton>
      </Box>

      {!collapsed && (
      <Box
        sx={{
          flex: 1,
          overflow: 'hidden',
          display: 'grid',
          gridTemplateColumns: `minmax(0, 1fr) 8px ${displaySideW}px`,
        }}
      >
        <Box sx={{ minWidth: 0, minHeight: 0, display: 'flex', flexDirection: 'column', bgcolor: cardTokens.surface.bodyBackground, overflow: 'hidden' }}>
          <Box
            ref={chatScrollRef}
            onWheel={(e) => e.stopPropagation()}
            sx={{ flex: '1 1 0', height: 0, overflowY: 'auto', overflowX: 'hidden', p: cardTokens.surface.padding, minHeight: 0 }}
          >
            <Box sx={{ maxWidth: 860, mx: 'auto', display: 'flex', flexDirection: 'column', gap: 1.5 }}>
              {chatMessages.length === 0 && events.length === 0 && (
                <Box sx={{ alignSelf: 'stretch', maxWidth: '100%', bgcolor: 'transparent', border: 'none', px: 0.5, py: 1.25 }}>
                  <style>{`@keyframes swarm-text-shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }`}</style>
                  <Typography
                    sx={{
                      fontSize: '0.88rem',
                      lineHeight: 1.55,
                      background: `linear-gradient(90deg, ${c.text.ghost} 0%, ${c.text.ghost} 40%, ${c.text.primary} 50%, ${c.text.ghost} 60%, ${c.text.ghost} 100%)`,
                      backgroundSize: '200% 100%',
                      WebkitBackgroundClip: 'text',
                      backgroundClip: 'text',
                      WebkitTextFillColor: 'transparent',
                      color: 'transparent',
                      animation: 'swarm-text-shimmer 5.1s linear infinite',
                    }}
                  >
                    Describe a large task. Swarm will plan and run an experimental orchestration for this dashboard.
                  </Typography>
                </Box>
              )}

              {chatMessages.map((message: any, idx: number) => {
                const role = getSwarmMessageRole(message);
                const isUser = role === 'user' || role === 'human';
                const body = getVisibleSwarmMessageText(getSwarmMessageText(message));
                const metadata = getSwarmMessageMetadata(message);
                const contextClarification = !isUser ? getContextClarification(message) : { question: '', options: [], reason: '', creationType: '' };
                const pendingRefinementAction = !isUser ? getPendingRefinementAction(message) : null;
                const mcpRequiredUserActions = !isUser ? getMcpRequiredUserActions(message) : [];
                const refinementExecutionTrace = !isUser ? getRefinementExecutionTrace(message) : null;
                const projectIntake = getSwarmProjectIntake(message);
                const intakeSkippedQuestions = Array.isArray(projectIntake.state?.skipped_questions)
                  ? projectIntake.state.skipped_questions.map((item: any) => renderText(item, '').trim()).filter(Boolean)
                  : [];
                const hasPreviousIntakeTrace = chatMessages.slice(0, idx).some((previousMessage: any) => {
                  const previousIntake = getSwarmProjectIntake(previousMessage);
                  return Array.isArray(previousIntake.state?.skipped_questions) && previousIntake.state.skipped_questions.length > 0;
                });
                const shouldShowIntakeTrace = !isUser && intakeSkippedQuestions.length > 0 && !hasPreviousIntakeTrace;
                const intakePolicyReason = renderText(projectIntake.state?.question_policy?.reason || projectIntake.state?.intake_profile?.reason, '').trim();
                const isLatestChatMessage = idx === chatMessages.length - 1;
                const currentProjectIntakeAction = !isUser && isLatestChatMessage && (activeSwarm as any)?.project_intake_action?.type === 'start_implementation'
                  ? (activeSwarm as any).project_intake_action
                  : projectIntake.action;
                const localProviderHealth = currentProjectIntakeAction?.capabilities?.local_provider_health || null;
                const localProviderUnavailable = Boolean(localProviderHealth && localProviderHealth.ok === false);
                const nextMessage = chatMessages[idx + 1];
                const nextRole = getSwarmMessageRole(nextMessage);
                const intakeAnswer = !isUser && projectIntake.options.length > 0 && (nextRole === 'user' || nextRole === 'human')
                  ? getVisibleSwarmMessageText(getSwarmMessageText(nextMessage))
                  : '';
                const metadataText = [
                  metadata.route,
                  metadata.source,
                  metadata.guard ? `guard${metadata.reason ? `: ${metadata.reason}` : ''}` : '',
                  metadata.pendingAction ? `pending: ${metadata.pendingAction}` : '',
                  metadata.targetOutputId ? `target: ${metadata.targetOutputId}` : '',
                  metadata.availableActions.length ? `actions: ${metadata.availableActions.join(', ')}` : '',
                ].filter(Boolean).join(' · ');
                const showMessageDebugMetadata = false;
                const messagePreview = body.length > 180 ? `${body.slice(0, 180).trimEnd()}…` : body;
                const isLatestCompletedAssistantTrace = !isUser && isLatestChatMessage && !swarmState.actionLoading;
                const messageTraceItems: ProcessTraceItem[] = [];
                if (!isUser) {
                  messageTraceItems.push({
                    trace_id: `swarm-message-${message.id || idx}`,
                    kind: 'message',
                    subsystem: 'ReasoningCore',
                    icon_id: 'reasoning-core',
                    title: 'Respuesta del Swarm',
                    summary: messagePreview || 'Respuesta del Swarm registrada.',
                    status: 'completed',
                    duration_ms: isLatestCompletedAssistantTrace ? lastSwarmActionDurationMs : undefined,
                    badge: 'message',
                    related_task_id: activeSwarmId || undefined,
                    details: {
                      route: metadata.route || null,
                      source: metadata.source || null,
                      guard: metadata.guard || null,
                      pending_action: metadata.pendingAction || null,
                      target_output_id: metadata.targetOutputId || null,
                      available_actions: metadata.availableActions,
                      message_preview: messagePreview || null,
                      visible_message_index: idx,
                    },
                  });
                  if (projectIntake.options.length > 0 || currentProjectIntakeAction?.type) {
                    messageTraceItems.push({
                      trace_id: `swarm-intake-${message.id || idx}`,
                      kind: 'intake',
                      subsystem: 'ActionCore',
                      icon_id: 'action-core',
                      title: 'Acción de intake',
                      summary: projectIntake.question || currentProjectIntakeAction?.label || 'Esperando una elección estructurada del usuario.',
                      status: 'planned',
                      badge: projectIntake.options.length > 0 ? `${projectIntake.options.length} opciones` : 'action',
                      related_action_id: currentProjectIntakeAction?.type || undefined,
                      details: {
                        question: projectIntake.question || null,
                        options: projectIntake.options.map((option: any) => renderText(option?.label ?? option?.value, '')).filter(Boolean),
                        action_type: currentProjectIntakeAction?.type || null,
                        provider_health_ok: localProviderHealth?.ok ?? null,
                        provider_unavailable: localProviderUnavailable,
                      },
                    });
                  }
                }

                return (
                  <Box
                    key={message.id || idx}
                    sx={{
                      alignSelf: isUser ? 'flex-end' : 'stretch',
                      maxWidth: isUser ? '78%' : '100%',
                      minWidth: 0,
                      overflow: 'hidden',
                      mr: '15px',
                      bgcolor: 'transparent',
                      color: c.text.primary,
                      border: 'none',
                      borderRadius: isUser ? 0.85 : 0,
                      px: isUser ? 1.5 : 0.5,
                      py: isUser ? 1.15 : 1.25,
                    }}
                  >
                    {!isUser && (
                      <Typography sx={{ color: c.text.muted, fontSize: '0.7rem', mb: 0.5 }}>
                        Swarm
                      </Typography>
                    )}
                    {messageTraceItems.length > 0 && (
                      <Box sx={{ mb: 1 }}>
                        <ProcessTraceTurnDropdown
                          container={{
                            turn_trace_kind: 'process_trace_turn_container',
                            turn_trace_version: 'openswarm.process_trace_turn_container.v1',
                            turn_trace_id: `swarm-message-turn-${message.id || idx}`,
                            title: 'Pensado',
                            status: 'completed',
                            message_id: String(message.id || idx),
                            output_message_id: String(message.id || idx),
                            duration_ms: isLatestCompletedAssistantTrace ? lastSwarmActionDurationMs : undefined,
                            default_collapsed_after_finish: true,
                            default_expanded_while_running: false,
                            child_trace_ids: messageTraceItems.map((trace) => trace.trace_id).filter(Boolean),
                            related_task_ids: activeSwarmId ? [activeSwarmId] : [],
                            items: messageTraceItems,
                            metadata: {
                              source: 'swarm_chat_message',
                              visible_message_index: idx,
                            },
                          }}
                          compact
                          defaultExpanded={false}
                        />
                      </Box>
                    )}
                    <Typography
                      sx={{
                        fontSize: '0.88rem',
                        lineHeight: 1.55,
                        whiteSpace: 'pre-wrap',
                        overflowWrap: 'break-word',
                        wordBreak: 'normal',
                        maxWidth: '100%',
                      }}
                    >
                      {isLatestChatMessage ? renderAnimatedText(body) : body}
                    </Typography>
                    {shouldShowIntakeTrace && (
                      <Box
                        sx={{
                          mt: 1,
                          px: 1,
                          py: 0.75,
                          borderRadius: 1,
                          bgcolor: `${c.status.info}0A`,
                          border: `1px solid ${c.status.info}33`,
                          maxWidth: '100%',
                        }}
                      >
                        <Typography sx={{ color: c.status.info, fontSize: '0.7rem', fontWeight: 650 }}>
                          Intake adaptado
                        </Typography>
                        <Typography sx={{ color: c.text.secondary, fontSize: '0.68rem', lineHeight: 1.35, mt: 0.25 }}>
                          OpenSwarm omitió preguntas no necesarias para este tipo de proyecto.
                        </Typography>
                        <Typography sx={{ color: c.text.tertiary, fontSize: '0.66rem', lineHeight: 1.35, mt: 0.35 }}>
                          Omitidas: {intakeSkippedQuestions.join(', ')}
                        </Typography>
                        {intakePolicyReason && (
                          <Typography sx={{ color: c.text.tertiary, fontSize: '0.66rem', lineHeight: 1.35, mt: 0.35 }}>
                            Criterio: {intakePolicyReason}
                          </Typography>
                        )}
                      </Box>
                    )}
                    {!isUser && contextClarification.options.length > 0 && (
                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75, mt: 1 }}>
                        {contextClarification.options.map((option: any, optionIdx: number) => {
                          const label = renderText(option?.label ?? option?.value, `Option ${optionIdx + 1}`);
                          const value = renderText(option?.value ?? option?.label, '').trim();
                          const kind = renderText(option?.kind, '').trim();
                          const isCustom = value === '__custom__';
                          return (
                            <Button
                              key={`${message.id || idx}-clarification-option-${optionIdx}`}
                              size="small"
                              variant="outlined"
                              disabled={swarmState.actionLoading || !isLatestChatMessage}
                              onClick={(e) => {
                                e.stopPropagation();
                                handleContextClarificationOption(option);
                              }}
                              sx={{
                                minHeight: 26,
                                px: 1,
                                py: 0.25,
                                fontSize: '0.72rem',
                                textTransform: 'none',
                                opacity: !isLatestChatMessage ? 0.45 : 1,
                                borderRadius: 0.5,
                                color: kind === 'recommended' ? '#1d4ed8' : c.text.secondary,
                                bgcolor: 'transparent',
                                borderColor: 'transparent',
                                borderWidth: 0,
                                fontWeight: kind === 'recommended' ? 650 : 400,
                                fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                                boxShadow: 'none',
                                '&:hover': {
                                  bgcolor: 'transparent',
                                  borderColor: 'transparent',
                                  color: '#1d4ed8',
                                  textDecoration: 'underline',
                                  textUnderlineOffset: '3px',
                                },
                              }}
                            >
                              {label}{kind === 'recommended' && !isCustom ? ' · recomendado' : ''}
                            </Button>
                          );
                        })}
                      </Box>
                    )}
                    {!isUser && projectIntake.options.length > 0 && (
                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75, mt: 1 }}>
                        {projectIntake.options.map((option: any, optionIdx: number) => {
                          const label = renderText(option?.label ?? option?.value, `Option ${optionIdx + 1}`);
                          const value = renderText(option?.value ?? option?.label, '').trim();
                          const isCustom = value === '__custom__';
                          const isSelected = !!intakeAnswer && !isCustom && (label === intakeAnswer || value === intakeAnswer);
                          return (
                            <Button
                              key={`${message.id || idx}-option-${optionIdx}`}
                              size="small"
                              variant="outlined"
                              disabled={swarmState.actionLoading || !isLatestChatMessage}
                              onClick={(e) => {
                                e.stopPropagation();
                                handleProjectIntakeOption(option);
                              }}
                              sx={{
                                minHeight: 26,
                                px: 1,
                                py: 0.25,
                                fontSize: '0.72rem',
                                textTransform: 'none',
                                opacity: !isLatestChatMessage && !isSelected ? 0.45 : 1,
                                borderRadius: 0.5,
                                color: isSelected ? '#1d4ed8' : c.text.secondary,
                                bgcolor: 'transparent',
                                borderColor: 'transparent',
                                borderWidth: 0,
                                fontWeight: 400,
                                fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                                boxShadow: 'none',
                                '&:before': isSelected ? {
                                  content: '"✓"',
                                  marginRight: '6px',
                                  color: '#1d4ed8',
                                } : undefined,
                                '&:hover': {
                                  bgcolor: 'transparent',
                                  borderColor: 'transparent',
                                  color: '#1d4ed8',
                                  textDecoration: 'underline',
                                  textUnderlineOffset: '3px',
                                },
                              }}
                            >
                              {label}
                            </Button>
                          );
                        })}
                      </Box>
                    )}
                    {!isUser && mcpRequiredUserActions.length > 0 && (
                      <Box
                        sx={{
                          mt: 1,
                          px: 1,
                          py: 0.85,
                          borderRadius: 1,
                          bgcolor: `${c.status.warning}0A`,
                          border: `1px solid ${c.status.warning}33`,
                          maxWidth: '100%',
                        }}
                      >
                        <Typography sx={{ color: c.status.warning, fontSize: '0.7rem', fontWeight: 650 }}>
                          Acción requerida para MCP
                        </Typography>
                        <Typography sx={{ color: c.text.secondary, fontSize: '0.68rem', lineHeight: 1.35, mt: 0.25 }}>
                          OpenSwarm necesita una acción manual antes de usar este MCP o su fallback.
                        </Typography>
                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75, mt: 0.75 }}>
                          {mcpRequiredUserActions.map((action, actionIdx) => (
                            <Button
                              key={`${message.id || idx}-mcp-required-action-${actionIdx}`}
                              size="small"
                              variant="outlined"
                              disabled={swarmState.actionLoading}
                              onClick={(e) => {
                                e.stopPropagation();
                                handleMcpRequiredUserAction(action);
                              }}
                              sx={{
                                minHeight: 28,
                                px: 1,
                                py: 0.25,
                                fontSize: '0.72rem',
                                textTransform: 'none',
                                borderRadius: 0.75,
                                color: c.status.warning,
                                borderColor: `${c.status.warning}66`,
                                bgcolor: `${c.status.warning}08`,
                                '&:hover': { bgcolor: `${c.status.warning}14`, borderColor: c.status.warning },
                              }}
                            >
                              {action.label}
                            </Button>
                          ))}
                        </Box>
                      </Box>
                    )}
                    {!isUser && pendingRefinementAction && (
                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75, mt: 1 }}>
                        <Button
                          size="small"
                          variant="outlined"
                          disabled={swarmState.actionLoading || !isLatestChatMessage}
                          onClick={(e) => {
                            e.stopPropagation();
                            handlePendingRefinementAction('confirm', pendingRefinementAction);
                          }}
                          sx={{
                            minHeight: 28,
                            px: 1,
                            py: 0.25,
                            fontSize: '0.72rem',
                            textTransform: 'none',
                            borderRadius: 0.75,
                            color: '#1d4ed8',
                            borderColor: '#1d4ed855',
                            bgcolor: '#1d4ed808',
                            '&:hover': { bgcolor: '#1d4ed814', borderColor: '#1d4ed8' },
                          }}
                        >
                          Confirmar cambio
                        </Button>
                        <Button
                          size="small"
                          variant="outlined"
                          disabled={swarmState.actionLoading || !isLatestChatMessage}
                          onClick={(e) => {
                            e.stopPropagation();
                            handlePendingRefinementAction('edit', pendingRefinementAction);
                          }}
                          sx={{
                            minHeight: 28,
                            px: 1,
                            py: 0.25,
                            fontSize: '0.72rem',
                            textTransform: 'none',
                            borderRadius: 0.75,
                            color: c.text.secondary,
                            borderColor: c.border.medium,
                            bgcolor: 'transparent',
                            '&:hover': { bgcolor: c.bg.muted, borderColor: c.border.strong },
                          }}
                        >
                          Editar pedido
                        </Button>
                        <Button
                          size="small"
                          variant="outlined"
                          disabled={swarmState.actionLoading || !isLatestChatMessage}
                          onClick={(e) => {
                            e.stopPropagation();
                            handlePendingRefinementAction('cancel', pendingRefinementAction);
                          }}
                          sx={{
                            minHeight: 28,
                            px: 1,
                            py: 0.25,
                            fontSize: '0.72rem',
                            textTransform: 'none',
                            borderRadius: 0.75,
                            color: c.status.error,
                            borderColor: `${c.status.error}55`,
                            bgcolor: `${c.status.error}08`,
                            '&:hover': { bgcolor: `${c.status.error}14`, borderColor: c.status.error },
                          }}
                        >
                          Cancelar
                        </Button>
                      </Box>
                    )}
                    {!isUser && refinementExecutionTrace && (() => {
                      const traceStatus = refinementExecutionTrace.status;
                      const isExecuted = traceStatus === 'executed' || refinementExecutionTrace.nextAction === 'review_candidate_diff';
                      const isNoChange = traceStatus === 'no_change';
                      const isFailed = traceStatus === 'failed';
                      const isBlocked = traceStatus === 'blocked';
                      const traceColor = isExecuted
                        ? c.status.success
                        : isNoChange
                          ? c.status.warning
                          : isFailed || isBlocked
                            ? c.status.error
                            : c.status.info;
                      const traceTitle = isExecuted
                        ? 'Candidate lista para revisar'
                        : isNoChange
                          ? 'Refinement sin cambios'
                          : isBlocked
                            ? 'Refinement bloqueado'
                            : isFailed
                              ? 'Refinement falló'
                              : 'Refinement actualizado';
                      const traceMessage = isExecuted
                        ? 'El cambio se aplicó sobre la candidate. El Output activo todavía no fue modificado.'
                        : isNoChange
                          ? 'El modelo no propuso cambios sobre los archivos permitidos. La candidate no fue modificada.'
                          : isBlocked
                            ? 'El cambio está preparado, pero no se ejecutó porque el guard o la metadata requerida lo bloqueó.'
                            : 'No se pudo aplicar el cambio sobre la candidate. El Output activo no fue modificado.';
                      const traceReason = refinementExecutionTrace.providerReason || refinementExecutionTrace.reason || refinementExecutionTrace.detail;
                      const traceReasonText = String(traceReason || '').toLowerCase();
                      const isExecutedWarning = isExecuted && (
                        traceReasonText.includes('evidence_insufficient') ||
                        traceReasonText.includes('evidence insufficient')
                      );
                      return (
                        <Box
                          sx={{
                            mt: 1,
                            px: 1,
                            py: 0.8,
                            borderRadius: 1,
                            bgcolor: `${traceColor}0A`,
                            border: `1px solid ${traceColor}44`,
                            maxWidth: '100%',
                          }}
                        >
                          <Typography sx={{ color: traceColor, fontSize: '0.7rem', fontWeight: 650 }}>
                            {traceTitle}
                          </Typography>
                          <Typography sx={{ color: c.text.secondary, fontSize: '0.68rem', lineHeight: 1.35, mt: 0.25 }}>
                            {traceMessage}
                          </Typography>
                          {traceReason && (
                            <Typography sx={{ color: c.text.tertiary, fontSize: '0.66rem', lineHeight: 1.35, mt: 0.35 }}>
                              {isExecutedWarning ? 'Advertencia' : 'Motivo real'}: {traceReason}
                            </Typography>
                          )}
                          {refinementExecutionTrace.requiredAction && (
                            <Typography sx={{ color: c.text.tertiary, fontSize: '0.66rem', lineHeight: 1.35, mt: 0.35 }}>
                              {refinementExecutionTrace.requiredAction}
                            </Typography>
                          )}
                          {refinementExecutionTrace.filesChanged.length > 0 && (
                            <Typography sx={{ color: c.text.tertiary, fontSize: '0.66rem', lineHeight: 1.35, mt: 0.35 }}>
                              Archivos cambiados: {refinementExecutionTrace.filesChanged.join(', ')}
                            </Typography>
                          )}
                          {isExecuted && (
                            <Typography sx={{ color: c.text.tertiary, fontSize: '0.66rem', lineHeight: 1.35, mt: 0.35 }}>
                              Siguiente paso: abrir Preview, revisar Compare/Diff y elegir Accept o Discard.
                            </Typography>
                          )}
                          {isExecuted && (stableOutputBridgeOutputId || canCreateOutputBridge) && (
                            <Button
                              size="small"
                              variant="outlined"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleOpenOutputPreview();
                              }}
                              onPointerDown={(e) => e.stopPropagation()}
                              sx={{
                                mt: 0.65,
                                minHeight: 26,
                                px: 0.9,
                                py: 0.2,
                                borderRadius: 0.75,
                                color: '#1d4ed8',
                                borderColor: '#1d4ed855',
                                bgcolor: '#1d4ed808',
                                fontSize: '0.68rem',
                                textTransform: 'none',
                                '&:hover': { bgcolor: '#1d4ed814', borderColor: '#1d4ed8' },
                              }}
                            >
                              Abrir Preview
                            </Button>
                          )}
                        </Box>
                      );
                    })()}
                    {!isUser && intakeAnswer && (
                      <Box sx={{ mt: 0.85, px: 1, py: 0.75, borderRadius: 1, bgcolor: c.bg.page, border: `1px solid ${c.border.subtle}` }}>
                        <Typography sx={{ color: c.text.tertiary, fontSize: '0.68rem', mb: 0.25 }}>
                          Respuesta elegida
                        </Typography>
                        <Typography sx={{ color: c.text.primary, fontSize: '0.78rem', lineHeight: 1.4 }}>
                          {intakeAnswer}
                        </Typography>
                      </Box>
                    )}
                    {!isUser && currentProjectIntakeAction?.type === 'start_implementation' && !shouldHideStartImplementationAction && (
                      <Box sx={{ mt: 0.55, display: 'flex', flexDirection: 'column', gap: 0.35, alignItems: 'flex-start' }}>
                        <Button
                          size="small"
                          variant="contained"
                          disabled={swarmState.actionLoading || isImplementationActionRunning || !activeSwarmId || currentProjectIntakeAction.enabled === false}
                          onClick={(e) => {
                            e.stopPropagation();
                            handleStartImplementation(currentProjectIntakeAction);
                          }}
                          sx={{
                            minHeight: 28,
                            px: 0.25,
                            py: 0.2,
                            fontSize: '0.74rem',
                            textTransform: 'none',
                            fontWeight: 500,
                            fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                            bgcolor: 'transparent',
                            color: '#1d4ed8',
                            border: 'none',
                            boxShadow: 'none',
                            '&:before': {
                              content: '">"',
                              marginRight: '6px',
                              color: '#1d4ed8',
                            },
                            '&:hover': {
                              bgcolor: 'transparent',
                              color: '#1e40af',
                              textDecoration: 'underline',
                              textUnderlineOffset: '3px',
                              boxShadow: 'none',
                            },
                            '&.Mui-disabled': {
                              bgcolor: 'transparent',
                              color: cardTokens.polish.mutedActionColor,
                              borderColor: 'transparent',
                            },
                          }}
                        >
                          {isImplementationActionRunning
                            ? 'Ejecutando implementación…'
                            : persistedImplementationState === 'failed' || persistedImplementationState === 'completed_without_output' || persistedImplementationState === 'bridge_failed'
                              ? 'Retry Swarm Implementation'
                              : renderText(currentProjectIntakeAction.label, 'Start Swarm Implementation')}
                        </Button>
                        {(isImplementationActionRunning || implementationStatus || claimGuardStatus || swarmState.error) && (
                          <Chip
                            size="small"
                            label={implementationMeta.message}
                            sx={{
                              height: 'auto',
                              maxWidth: '100%',
                              color: implementationMeta.color,
                              bgcolor: `${implementationMeta.color}14`,
                              border: `1px solid ${implementationMeta.color}44`,
                              '& .MuiChip-label': {
                                display: 'block',
                                whiteSpace: 'normal',
                                py: 0.35,
                                fontSize: '0.68rem',
                                lineHeight: 1.35,
                              },
                            }}
                          />
                        )}
                        {!currentProjectIntakeAction.enabled && localProviderUnavailable && (
                          <Box
                            sx={{
                              mt: 0.35,
                              px: 1,
                              py: 0.75,
                              borderRadius: 1,
                              bgcolor: `${c.status.warning}10`,
                              border: `1px solid ${c.status.warning}44`,
                              maxWidth: '100%',
                            }}
                          >
                            <Typography sx={{ color: c.status.warning, fontSize: '0.7rem', fontWeight: 650 }}>
                              Provider local no disponible
                            </Typography>
                            <Typography sx={{ color: c.text.secondary, fontSize: '0.68rem', lineHeight: 1.35, mt: 0.25 }}>
                              {renderText(localProviderHealth.reason || currentProjectIntakeAction.reason, 'Ollama no está corriendo o no responde.')}
                            </Typography>
                            {localProviderHealth.required_action && (
                              <Typography sx={{ color: c.text.tertiary, fontSize: '0.66rem', lineHeight: 1.35, mt: 0.35 }}>
                                {renderText(localProviderHealth.required_action)}
                              </Typography>
                            )}
                          </Box>
                        )}
                        {!currentProjectIntakeAction.enabled && !localProviderUnavailable && (
                          <Typography sx={{ color: c.text.tertiary, fontSize: '0.68rem' }}>
                            {renderText(currentProjectIntakeAction.reason, 'La implementacion se habilita cuando el runner experimental esta activo.')}
                          </Typography>
                        )}
                      </Box>
                    )}
                    {!isUser && currentProjectIntakeAction?.type === 'start_implementation' && shouldHideStartImplementationAction && (
                      <Box sx={{ mt: 0.55, display: 'flex', flexDirection: 'column', gap: 0.35, alignItems: 'flex-start' }}>
                        <Chip
                          size="small"
                          label={implementationMeta.message}
                          sx={{
                            height: 'auto',
                            maxWidth: '100%',
                            color: implementationMeta.color,
                            bgcolor: `${implementationMeta.color}14`,
                            border: `1px solid ${implementationMeta.color}44`,
                            '& .MuiChip-label': {
                              display: 'block',
                              whiteSpace: 'normal',
                              py: 0.35,
                              fontSize: '0.68rem',
                              lineHeight: 1.35,
                            },
                          }}
                        />
                      </Box>
                    )}
                    {!isUser && currentProjectIntakeAction?.type === 'start_implementation' && implementationErrors.length > 0 && (
                      <Typography sx={{ color: c.status.error, fontSize: '0.68rem', mt: 0.5, whiteSpace: 'pre-wrap' }}>
                        {implementationErrors.slice(0, 2).map((error: any) => renderText(error?.error || error?.message || error?.detail || JSON.stringify(error), 'implementation_error')).join('\n')}
                      </Typography>
                    )}
                    {showMessageDebugMetadata && !isUser && metadataText && (
                      <Typography sx={{ color: c.text.tertiary, fontSize: '0.68rem', mt: 0.75 }}>
                        {metadataText}
                      </Typography>
                    )}
                  </Box>
                );
              })}

              {lastSubmittedPrompt && !lastSubmittedAlreadyPersisted && (
                <Box
                  sx={{
                    alignSelf: 'flex-end',
                    maxWidth: '78%',
                    bgcolor: 'transparent',
                    color: c.text.primary,
                    border: 'none',
                    borderRadius: 0.85,
                    px: 1.5,
                    py: 1.15,
                  }}
                >
                  <Typography
                    sx={{
                      fontSize: '0.88rem',
                      lineHeight: 1.55,
                      whiteSpace: 'pre-wrap',
                    }}
                  >
                    {renderAnimatedText(lastSubmittedPrompt)}
                  </Typography>
                </Box>
              )}

              {chatMessages.length === 0 && !lastSubmittedPrompt && events.slice(0, 4).map((event: any) => (
                <Box key={event.id || `${humanizeEvent(event)}-${event.created_at}`} sx={{ alignSelf: 'flex-start', maxWidth: '86%', bgcolor: c.bg.surface, border: `1px solid ${c.border.subtle}`, borderRadius: 1.25, px: 1.5, py: 1 }}>
                  <Typography sx={{ fontSize: '0.78rem', color: c.text.muted }}>
                    {humanizeEvent(event)}
                  </Typography>
                </Box>
              ))}

              {lastSwarmActionLabel && !swarmState.actionLoading && (
                <Box
                  sx={{
                    alignSelf: 'stretch',
                    maxWidth: '100%',
                    bgcolor: 'transparent',
                    border: 'none',
                    borderRadius: 0,
                    px: 0.5,
                    py: 0.35,
                    display: 'flex',
                    alignItems: 'center',
                  }}
                >
                  <Typography sx={{ fontSize: '0.72rem', color: c.text.tertiary, fontStyle: 'italic' }}>
                    {lastSwarmActionLabel}
                  </Typography>
                </Box>
              )}

              {swarmState.actionLoading && (
                <Box
                  sx={{
                    alignSelf: 'stretch',
                    maxWidth: '100%',
                    bgcolor: 'transparent',
                    border: 'none',
                    borderRadius: 0,
                    px: 0.5,
                    py: 0.75,
                  }}
                >
                  <ProcessTraceTurnDropdown
                    container={{
                      turn_trace_kind: 'process_trace_turn_container',
                      turn_trace_version: 'openswarm.process_trace_turn_container.v1',
                      turn_trace_id: `swarm-live-turn-${activeSwarmId || swarmCardId}`,
                      title: swarmActionStatusLabel === 'Thinking' ? 'Pensando' : swarmActionStatusLabel,
                      status: 'running',
                      duration_ms: swarmActionElapsedMs,
                      default_collapsed_after_finish: false,
                      default_expanded_while_running: true,
                      child_trace_ids: [
                        `swarm-live-reasoning-${activeSwarmId || swarmCardId}`,
                        `swarm-live-model-${activeSwarmId || swarmCardId}`,
                      ],
                      related_task_ids: activeSwarmId ? [activeSwarmId] : [],
                      items: [
                        {
                          trace_id: `swarm-live-reasoning-${activeSwarmId || swarmCardId}`,
                          kind: 'reasoning',
                          subsystem: 'ReasoningCore',
                          icon_id: 'reasoning-core',
                          title: 'Razonamiento operativo en curso',
                          summary: lastSubmittedPrompt
                            ? `Evaluando la solicitud visible: "${lastSubmittedPrompt.length > 180 ? `${lastSubmittedPrompt.slice(0, 180).trimEnd()}…` : lastSubmittedPrompt}".`
                            : 'Evaluando el turno actual y preparando una respuesta útil.',
                          status: 'running',
                          duration_ms: swarmActionElapsedMs,
                          badge: 'live',
                          related_task_id: activeSwarmId || undefined,
                        },
                        {
                          trace_id: `swarm-live-model-${activeSwarmId || swarmCardId}`,
                          kind: 'model',
                          subsystem: 'ModelCore',
                          icon_id: 'model-core',
                          title: 'Modelo generando respuesta',
                          summary: `El modelo está trabajando en este turno. Se muestra un resumen operativo, no razonamiento privado paso a paso.`,
                          status: 'running',
                          duration_ms: swarmActionElapsedMs,
                          badge: 'running',
                          related_task_id: activeSwarmId || undefined,
                        },
                      ],
                      metadata: { source: 'swarm_live_action' },
                    }}
                    defaultExpanded={false}
                  />
                </Box>
              )}

              {swarmState.error && (
                <Box sx={{ alignSelf: 'flex-start', maxWidth: '86%', bgcolor: `${c.status.error}12`, border: `1px solid ${c.status.error}66`, borderRadius: 1.25, px: 1.5, py: 1 }}>
                  <Typography sx={{ fontSize: '0.78rem', color: c.status.error, fontWeight: 650 }}>
                    Error de implementación
                  </Typography>
                  <Typography sx={{ fontSize: '0.74rem', color: c.text.secondary, mt: 0.35, lineHeight: 1.4 }}>
                    {swarmState.error}
                  </Typography>
                </Box>
              )}

              <Box ref={chatEndRef} />
            </Box>
          </Box>

          <Box sx={{ flexShrink: 0, p: cardTokens.density.inputPadding, borderTop: `1px solid ${cardTokens.surface.border}`, bgcolor: cardTokens.surface.background }}>
            {pendingPreviewRefinementDraft && (
              <Box
                sx={{
                  mb: 1,
                  px: 1.1,
                  py: 0.8,
                  borderRadius: 1,
                  border: `1px solid ${c.status.info}44`,
                  bgcolor: `${c.status.info}0A`,
                }}
              >
                <Typography sx={{ color: c.status.info, fontSize: '0.76rem', fontWeight: 650 }}>
                  Refinando Preview
                </Typography>
                <Typography sx={{ color: c.text.secondary, fontSize: '0.72rem', lineHeight: 1.35, mt: 0.25 }}>
                  Escribí el cambio que querés aplicar a {(pendingPreviewRefinementDraft.outputName || 'esta app').slice(0, 72)}{(pendingPreviewRefinementDraft.outputName || '').length > 72 ? '…' : ''}. El historial del Swarm se mantiene.
                </Typography>
              </Box>
            )}
            <SwarmPromptInput
              value={prompt}
              onChange={setPrompt}
              onSend={handleStart}
              mode={activeSwarmMode}
              onModeChange={handleSwarmModeChange}
              loading={swarmState.actionLoading}
              canContinue={Boolean(activeSwarmId)}
              customIntakeMode={customIntakeMode}
              model={activeSwarmModel}
              onModelChange={handleSwarmModelChange}
              modelLabel={activeSwarmModel}
              contextEstimate={contextEstimate}
              inputRef={promptInputRef}
              placeholderOverride={pendingPreviewRefinementDraft ? 'Describí el cambio para esta Preview…' : undefined}
            />
          </Box>
        </Box>

        <Box
          onPointerDown={handleSideResizeDown}
          sx={{
            width: 8,
            ml: '-4px',
            cursor: 'ew-resize',
            zIndex: 20,
            bgcolor: 'transparent',
            '&:hover': { bgcolor: `${c.accent.primary}22` },
          }}
        />

        <Box sx={{ borderLeft: `1px solid ${cardTokens.surface.border}`, bgcolor: cardTokens.surface.background, overflow: 'auto', p: cardTokens.density.sidebarPadding }}>
          <Typography sx={{ color: c.text.muted, fontSize: '0.72rem', mb: 1 }}>
            Swarm {activeSwarmId ? `· ${activeSwarmId}` : '· not started'}
          </Typography>

          {renderPanelHeader('tasks', 'Tasks', tasks.length)}
          {openPanelSections.tasks && (tasks.length === 0 ? (
            <Typography sx={{ color: c.text.tertiary, fontSize: '0.78rem', mb: 1.5 }}>No tasks yet.</Typography>
          ) : tasks.slice(0, 6).map((task: any, idx: number) => (
            <Box
              key={task.id || idx}
              sx={{
                mb: 0.75,
                p: 1,
                border: `1px solid ${c.border.subtle}`,
                borderRadius: 1.25,
                bgcolor: c.bg.page,
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1 }}>
                <Typography sx={{ fontSize: '0.78rem', fontWeight: 650, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {renderText(task.title || task.name, `Task ${idx + 1}`)}
                </Typography>
                <Chip size="small" label={humanizeStatus(task.status, 'queued')} sx={{ height: 20, fontSize: '0.68rem' }} />
              </Box>
              {(task.agent || task.assignee || task.description) && (
                <Typography sx={{ color: c.text.muted, fontSize: '0.72rem', mt: 0.5, lineHeight: 1.45 }}>
                  {renderText(task.agent || task.assignee || task.description)}
                </Typography>
              )}

              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.65, mt: 0.85 }}>
                {buildMiniAgentInspectorProcessTraceItems(task, idx).map((item) => (
                  <ProcessTraceDropdown
                    key={item.trace_id || `${item.kind}-${item.title}`}
                    item={item}
                    compact
                    defaultExpanded={item.status === 'running' || item.status === 'blocked'}
                  />
                ))}
              </Box>
            </Box>
          )))}

          {renderPanelHeader('approvals', 'Approvals', approvals.length)}
          {openPanelSections.approvals && (approvals.length === 0 ? (
            <Typography sx={{ color: c.text.tertiary, fontSize: '0.78rem', mb: 1.5 }}>No approvals.</Typography>
          ) : approvals.map((approval: any) => {
            const approvalId = approval.id || approval.approval_id;
            const status = String(approval.status || '').toLowerCase();
            const canDecide = approvalId && ['pending', 'requested', 'requires_approval'].includes(status);
            const canResume = approvalId && ['allowed', 'approved', 'denied'].includes(status);

            return (
              <Box
                key={approvalId || approval.tool_name}
                sx={{
                  mb: 0.75,
                  p: 1,
                  border: `1px solid ${c.border.subtle}`,
                  borderRadius: 1.25,
                  bgcolor: c.bg.page,
                }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1, mb: 0.75 }}>
                  <Typography sx={{ fontSize: '0.78rem', fontWeight: 650, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {renderText(approval.tool_name, 'Tool approval')}
                  </Typography>
                  <Chip size="small" label={humanizeStatus(approval.status, 'pending')} sx={{ height: 20, fontSize: '0.68rem' }} />
                </Box>

                {approval.reason && (
                  <Typography sx={{ color: c.text.muted, fontSize: '0.72rem', mb: 0.75, lineHeight: 1.45 }}>
                    {renderText(approval.reason)}
                  </Typography>
                )}

                {(canDecide || canResume) && (
                  <Box sx={{ display: 'flex', gap: 0.75, flexWrap: 'wrap' }}>
                    {canDecide && (
                      <>
                        <Button
                          size="small"
                          variant="contained"
                          disabled={swarmState.actionLoading}
                          onClick={() => handleApprovalAction(approvalId, 'allow')}
                          sx={{ minHeight: 26, px: 1, py: 0.25, fontSize: '0.72rem', textTransform: 'none' }}
                        >
                          Allow
                        </Button>
                        <Button
                          size="small"
                          variant="outlined"
                          disabled={swarmState.actionLoading}
                          onClick={() => handleApprovalAction(approvalId, 'deny')}
                          sx={{ minHeight: 26, px: 1, py: 0.25, fontSize: '0.72rem', textTransform: 'none' }}
                        >
                          Deny
                        </Button>
                      </>
                    )}
                    {canResume && (
                      <Button
                        size="small"
                        variant="outlined"
                        disabled={swarmState.actionLoading}
                        onClick={() => handleApprovalAction(approvalId, 'resume')}
                        sx={{ minHeight: 26, px: 1, py: 0.25, fontSize: '0.72rem', textTransform: 'none' }}
                      >
                        Resume
                      </Button>
                    )}
                  </Box>
                )}
              </Box>
            );
          }))}

          {renderPanelHeader('events', 'Recent activity', events.length)}
          {openPanelSections.events && (events.length === 0 ? (
            <Typography sx={{ color: c.text.tertiary, fontSize: '0.78rem', mb: 1.5 }}>No events loaded.</Typography>
          ) : events.slice(0, 6).map((event: any, idx: number) => (
            <Box
              key={event.id || `${humanizeEvent(event)}-${event.created_at}-${idx}`}
              sx={{
                mb: 0.6,
                pl: 1,
                borderLeft: `2px solid ${c.border.subtle}`,
              }}
            >
              <Typography sx={{ color: c.text.primary, fontSize: '0.74rem', fontWeight: 600 }}>
                {humanizeEvent(event)}
              </Typography>
              {event.created_at && (
                <Typography sx={{ color: c.text.tertiary, fontSize: '0.68rem', lineHeight: 1.35 }}>
                  {new Date(event.created_at).toLocaleTimeString()}
                </Typography>
              )}
            </Box>
          )))}

          {renderPanelHeader('artifacts', 'Artifacts', artifacts.length)}
          {openPanelSections.artifacts && (artifacts.length === 0 ? (
            <Typography sx={{ color: c.text.tertiary, fontSize: '0.78rem', mb: 1.5 }}>No artifacts.</Typography>
          ) : swarmState.artifacts.slice(0, 4).map((artifact: any, idx: number) => (
            <Box
              key={artifact.id || idx}
              sx={{
                mb: 0.75,
                p: 1,
                border: `1px solid ${c.border.subtle}`,
                borderRadius: 1.25,
                bgcolor: c.bg.page,
              }}
            >
              <Typography sx={{ color: c.text.primary, fontSize: '0.76rem', fontWeight: 650 }}>
                {humanizeArtifact(artifact, `Artifact ${idx + 1}`)}
              </Typography>
              <Typography sx={{ color: c.text.muted, fontSize: '0.7rem' }}>
                {humanizeStatus(artifact.kind || artifact.type, 'artifact')}
              </Typography>
              {(artifact.evidence_id || artifact.evidence_ref) && (
                <Typography sx={{ color: c.text.tertiary, fontSize: '0.66rem', mt: 0.35 }} noWrap>
                  {artifact.evidence_id ? `evidence: ${artifact.evidence_id}` : `legacy ref: ${artifact.evidence_ref}`}
                </Typography>
              )}
            </Box>
          )))}

          {renderPanelHeader('evidence', 'Evidence', finalEvidence.length)}
          {openPanelSections.evidence && (finalEvidence.length === 0 ? (
            <Typography sx={{ color: c.text.tertiary, fontSize: '0.78rem', mb: 1.5 }}>No final evidence.</Typography>
          ) : finalEvidence.slice(0, 6).map((evidence: any, idx: number) => (
            <Box
              key={evidence.id || evidence.evidence_id || `${evidence.kind || evidence.type || 'evidence'}-${idx}`}
              sx={{
                mb: 0.75,
                p: 1,
                border: `1px solid ${c.border.subtle}`,
                borderRadius: 1.25,
                bgcolor: c.bg.page,
              }}
            >
              <Typography sx={{ color: c.text.primary, fontSize: '0.74rem', fontWeight: 650 }} noWrap>
                {humanizeEvidence(evidence, `Evidence ${idx + 1}`)}
              </Typography>
              {(evidence.id || evidence.task_id || evidence.tool_call_id) && (
                <Typography sx={{ color: c.text.tertiary, fontSize: '0.66rem', mt: 0.35 }} noWrap>
                  {[evidence.id ? `id: ${evidence.id}` : '', evidence.task_id ? `task: ${evidence.task_id}` : '', evidence.tool_call_id ? `tool call: ${evidence.tool_call_id}` : ''].filter(Boolean).join(' · ')}
                </Typography>
              )}
            </Box>
          )))}

          {renderPanelHeader('finalResult', 'Final result')}
          {openPanelSections.finalResult && (
            <Box
              sx={{
                p: 1,
                border: `1px solid ${c.border.subtle}`,
                borderRadius: 1.25,
                bgcolor: c.bg.page,
              }}
            >
              {(implementationStatus === 'completed' || implementationStatus === 'failed' || claimGuardStatus) && (
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 1 }}>
                  {implementationStatus === 'failed' ? (
                    <Chip
                      size="small"
                      label="Implementación fallida"
                      sx={{ color: c.status.error, bgcolor: `${c.status.error}18`, border: `1px solid ${c.status.error}55`, fontWeight: 650 }}
                    />
                  ) : implementationStatus === 'completed' && claimGuardStatus === 'verified' ? (
                    <Chip
                      size="small"
                      label="Implementación completada · Verificada"
                      sx={{ color: c.status.success, bgcolor: `${c.status.success}18`, border: `1px solid ${c.status.success}55`, fontWeight: 650 }}
                    />
                  ) : implementationStatus === 'completed' ? (
                    <Chip
                      size="small"
                      label="Completada · Evidencia no verificada"
                      sx={{ color: c.status.warning, bgcolor: `${c.status.warning}18`, border: `1px solid ${c.status.warning}55`, fontWeight: 650 }}
                    />
                  ) : null}
                  {evidenceLinked && (
                    <Chip size="small" label="evidencia vinculada" />
                  )}
                </Box>
              )}
              {showFinalResultDebugMetadata && finalResult && typeof finalResult === 'object' && (
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 1 }}>
                  {(finalResult as any).route && (
                    <Chip size="small" label={`route: ${(finalResult as any).route}`} />
                  )}
                  {(finalResult as any).route && (
                    <Chip
                      size="small"
                      label={(finalResult as any).route === 'normal_chat' ? 'source: model' : 'source: local'}
                    />
                  )}
                  {(finalResult as any).answer_guard_applied && (
                    <Chip size="small" label="guard applied" />
                  )}
                  {(finalResult as any).claim_guard?.status && (
                    <Chip
                      size="small"
                      label={`claim guard: ${(finalResult as any).claim_guard.status}`}
                    />
                  )}
                  {Array.isArray((finalResult as any).claim_guard?.unsupported_claims)
                    && (finalResult as any).claim_guard.unsupported_claims.length > 0 && (
                    <Chip
                      size="small"
                      label={`unsupported: ${(finalResult as any).claim_guard.unsupported_claims.length}`}
                    />
                  )}
                </Box>
              )}
              <Typography sx={{ color: finalResult ? c.text.primary : c.text.tertiary, fontSize: '0.78rem', lineHeight: 1.45 }}>
                {renderText(finalResult?.summary || finalResult, 'Pending')}
              </Typography>
            </Box>
          )}
        </Box>
      </Box>
      )}

      {!collapsed && HANDLE_DEFS.map(({ dir, sx }) => (
        <Box
          key={dir}
          onPointerDown={handleResizeDown(dir)}
          sx={{
            position: 'absolute',
            zIndex: 30,
            cursor: CURSOR_MAP[dir],
            ...sx,
          }}
        />
      ))}
    </Box>
  );
};

export default ExperimentalSwarmCanvasCard;
