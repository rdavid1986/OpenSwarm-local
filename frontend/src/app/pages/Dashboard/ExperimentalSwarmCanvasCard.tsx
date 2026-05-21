import React, { useCallback, useEffect, useRef, useState } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import IconButton from '@mui/material/IconButton';
import Chip from '@mui/material/Chip';
import Button from '@mui/material/Button';
import CloseIcon from '@mui/icons-material/Close';
import InputBase from '@mui/material/InputBase';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import HourglassEmptyIcon from '@mui/icons-material/HourglassEmpty';
import MoreHorizIcon from '@mui/icons-material/MoreHoriz';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import {
  removeSwarmCard,
  setSwarmCardPosition,
  setSwarmCardSize,
  setSwarmCardSwarmId,
  toggleSwarmCardCollapsed,
} from '@/shared/state/dashboardLayoutSlice';
import {
  allowExperimentalApproval,
  chatExperimentalSwarm,
  createExperimentalSwarm,
  denyExperimentalApproval,
  fetchExperimentalSwarm,
  resumeExperimentalApproval,
  runExperimentalDag,
  startExperimentalImplementation,
} from '@/shared/state/experimentalSwarmsSlice';
import { useAppDispatch, useAppSelector } from '@/shared/hooks';
import { useClaudeTokens } from '@/shared/styles/ThemeContext';
import type { CardType } from './useDashboardSelection';

type ResizeDir = 'n' | 's' | 'e' | 'w' | 'ne' | 'nw' | 'se' | 'sw';
type ImplementationVisualState = 'idle' | 'running' | 'completed' | 'failed' | 'verified' | 'unverified';

interface Props {
  swarmCardId: string;
  swarmId?: string | null;
  cardX: number;
  cardY: number;
  cardWidth: number;
  cardHeight: number;
  cardZOrder?: number;
  collapsed?: boolean;
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
    x?: number;
    y?: number;
    width?: number;
    height?: number;
  }) => void;
  dashboardId?: string;
}

const MIN_W = 520;
const MIN_H = 380;
const EDGE_THICKNESS = 6;
const CORNER_SIZE = 14;
const MIN_SIDE_W = 220;
const MAX_SIDE_W = 520;

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

function getSwarmMessageMetadata(message: any): { route: string; source: string; guard: boolean; reason: string } {
  const payload = message?.payload || {};
  const route = renderText(payload.route ?? payload.message?.route ?? payload.response?.route, '').trim();
  const source = renderText(payload.source ?? payload.message?.source ?? payload.response?.source, '').trim();
  const guard = Boolean(payload.answer_guard_applied ?? payload.message?.answer_guard_applied ?? payload.response?.answer_guard_applied);
  const reason = renderText(payload.answer_guard_reason ?? payload.message?.answer_guard_reason ?? payload.response?.answer_guard_reason, '').trim();

  return { route, source, guard, reason };
}

function getSwarmProjectIntake(message: any): {
  question: any | null;
  options: any[];
  action: any | null;
} {
  const payload = message?.payload || {};
  return {
    question: payload.project_intake_question || null,
    options: Array.isArray(payload.project_intake_options) ? payload.project_intake_options : [],
    action: payload.project_intake_action || null,
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
  return normalizeStatusValue(swarm?.implementation?.status || swarm?.status);
}

function isTerminalImplementationState(status: string): boolean {
  return status === 'completed' || status === 'failed';
}

function getImplementationVisualState(params: {
  hasSwarm: boolean;
  isRunning: boolean;
  implementationStatus: string;
  claimGuardStatus: string;
  hasError: boolean;
}): ImplementationVisualState {
  if (params.isRunning) return 'running';
  if (params.hasError || params.implementationStatus === 'failed') return 'failed';
  if (params.implementationStatus === 'completed') {
    return params.claimGuardStatus === 'verified' ? 'verified' : 'unverified';
  }
  return params.hasSwarm ? 'idle' : 'idle';
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
  dashboardId,
}) => {
  const c = useClaudeTokens();
  const dispatch = useAppDispatch();
  const swarmState = useAppSelector((s) => s.experimentalSwarms);

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
  const [openPanelSections, setOpenPanelSections] = useState<Record<string, boolean>>({
    tasks: false,
    approvals: false,
    events: false,
    artifacts: false,
    evidence: false,
    finalResult: true,
  });

  const activeSwarmId = swarmId || null;
  const activeSwarm = activeSwarmId && swarmState.swarm?.id === activeSwarmId ? swarmState.swarm : null;
  const events = activeSwarmId ? swarmState.events.slice(-8).reverse() : [];
  const approvals = activeSwarmId ? swarmState.approvals.slice(0, 5) : [];
  const tasks = activeSwarm ? (activeSwarm.tasks || []) : [];
  const artifacts = activeSwarm ? (swarmState.artifacts || []) : [];
  const finalEvidence = activeSwarm && Array.isArray((activeSwarm as any).final_evidence)
    ? (activeSwarm as any).final_evidence
    : [];
  const finalResult = activeSwarm ? activeSwarm.final_result : null;
  const implementationStatus = getImplementationStatus(activeSwarm);
  const claimGuardStatus = getClaimGuardStatus(finalResult);
  const evidenceLinked = Boolean((activeSwarm as any)?.orchestration_canvas_state?.evidence_linked);
  const implementationVisualState = getImplementationVisualState({
    hasSwarm: Boolean(activeSwarmId),
    isRunning: isStartingImplementation,
    implementationStatus,
    claimGuardStatus,
    hasError: Boolean(swarmState.error),
  });
  const implementationStateMeta: Record<ImplementationVisualState, { label: string; color: string; message: string }> = {
    idle: {
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
    failed: {
      label: 'Falló',
      color: c.status.error,
      message: 'La implementación falló. Revisá el error visible y la actividad reciente.',
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
  const chatMessages = activeSwarmId
    ? (swarmState.messages || []).filter((message: any) => getSwarmMessageText(message))
    : [];
  const finalRoute = typeof finalResult === 'object' && finalResult ? (finalResult as any).route : null;
  const finalAnswerGuardApplied = typeof finalResult === 'object' && finalResult ? (finalResult as any).answer_guard_applied : null;
  const finalResponseSource = finalRoute && finalRoute !== 'normal_chat' ? 'local' : finalRoute === 'normal_chat' ? 'model' : null;
  const lastSubmittedAlreadyPersisted = !!activeSwarmId && !!lastSubmittedPrompt && chatMessages.some((message: any) => {
    const role = getSwarmMessageRole(message);
    return (role === 'user' || role === 'human') && getSwarmMessageText(message) === lastSubmittedPrompt;
  });

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

    if (cleanPrompt) {
      setLastSubmittedPrompt(cleanPrompt);
      setPrompt('');
    }

    let swarmIdToRun = activeSwarmId;
    let intent = swarmState.swarm?.intent || 'task';

    if (!swarmIdToRun) {
      const action = await dispatch(createExperimentalSwarm({ userPrompt: cleanPrompt || 'Experimental swarm', dashboardId }));
      if (createExperimentalSwarm.fulfilled.match(action)) {
        swarmIdToRun = action.payload.id;
        intent = action.payload.intent || 'task';
        dispatch(setSwarmCardSwarmId({ swarmCardId, swarmId: swarmIdToRun }));
        window.setTimeout(() => onSwarmBound?.({ swarmCardId, swarmId: swarmIdToRun }), 0);
      }
    }

    if (!swarmIdToRun) return;

    await dispatch(chatExperimentalSwarm({ swarmId: swarmIdToRun, message: cleanPrompt || lastSubmittedPrompt || 'Continue' }));
    dispatch(fetchExperimentalSwarm(swarmIdToRun));
  }, [activeSwarmId, dashboardId, dispatch, lastSubmittedPrompt, onSwarmBound, prompt, swarmCardId, swarmState.swarm?.intent]);

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
    await dispatch(chatExperimentalSwarm({ swarmId: activeSwarmId, message: label }));
    dispatch(fetchExperimentalSwarm(activeSwarmId));
  }, [activeSwarmId, dispatch, swarmState.actionLoading]);

  const handleStartImplementation = useCallback(async () => {
    if (!activeSwarmId || swarmState.actionLoading || startImplementationInFlightRef.current) return;

    startImplementationInFlightRef.current = true;
    setIsStartingImplementation(true);
    startImplementationPolling(activeSwarmId);
    try {
      await dispatch(startExperimentalImplementation({ swarmId: activeSwarmId })).unwrap();
      await dispatch(fetchExperimentalSwarm(activeSwarmId));
    } catch {
      // Error state is stored by the slice matcher and rendered in this card.
    } finally {
      stopImplementationPolling();
      startImplementationInFlightRef.current = false;
      setIsStartingImplementation(false);
    }
  }, [activeSwarmId, dispatch, startImplementationPolling, stopImplementationPolling, swarmState.actionLoading]);

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
        bgcolor: c.bg.surface,
        border: `1px solid ${isSelected ? c.accent.primary : c.border.subtle}`,
        borderRadius: 1.25,
        overflow: 'hidden',
        boxShadow: isHighlighted ? c.shadow.lg : c.shadow.md,
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
          px: 2,
          py: 1.25,
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          borderBottom: collapsed ? 'none' : `1px solid ${c.border.subtle}`,
          cursor: isDragging ? 'grabbing' : 'grab',
          touchAction: 'none',
          userSelect: 'none',
        }}
      >
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography sx={{ fontWeight: 650, fontSize: '0.98rem' }}>Swarm</Typography>
          <Typography sx={{ color: c.text.muted, fontSize: '0.78rem' }}>
            Local-first experimental swarm runtime
          </Typography>
        </Box>
        <Chip
          size="small"
          label={implementationMeta.label}
          sx={{
            color: implementationMeta.color,
            bgcolor: `${implementationMeta.color}18`,
            border: `1px solid ${implementationMeta.color}55`,
            fontWeight: 650,
          }}
        />
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
        <Box sx={{ minWidth: 0, minHeight: 0, display: 'flex', flexDirection: 'column', bgcolor: c.bg.page, overflow: 'hidden' }}>
          <Box
            ref={chatScrollRef}
            onWheel={(e) => e.stopPropagation()}
            sx={{ flex: '1 1 0', height: 0, overflowY: 'auto', overflowX: 'hidden', p: 2, minHeight: 0 }}
          >
            <Box sx={{ maxWidth: 760, mx: 'auto', display: 'flex', flexDirection: 'column', gap: 1.5 }}>
              {chatMessages.length === 0 && events.length === 0 && (
                <Box sx={{ alignSelf: 'flex-start', maxWidth: '86%', bgcolor: c.bg.surface, border: `1px solid ${c.border.subtle}`, borderRadius: 1.25, px: 1.5, py: 1.25 }}>
                  <Typography sx={{ fontSize: '0.88rem', lineHeight: 1.55 }}>
                    Describe a large task. Swarm will plan and run an experimental orchestration for this dashboard.
                  </Typography>
                </Box>
              )}

              {chatMessages.map((message: any, idx: number) => {
                const role = getSwarmMessageRole(message);
                const isUser = role === 'user' || role === 'human';
                const body = getSwarmMessageText(message);
                const metadata = getSwarmMessageMetadata(message);
                const projectIntake = getSwarmProjectIntake(message);
                const isLatestChatMessage = idx === chatMessages.length - 1;
                const nextMessage = chatMessages[idx + 1];
                const nextRole = getSwarmMessageRole(nextMessage);
                const intakeAnswer = !isUser && projectIntake.options.length > 0 && (nextRole === 'user' || nextRole === 'human')
                  ? getSwarmMessageText(nextMessage)
                  : '';
                const metadataText = [
                  metadata.route,
                  metadata.source,
                  metadata.guard ? `guard${metadata.reason ? `: ${metadata.reason}` : ''}` : '',
                ].filter(Boolean).join(' · ');

                return (
                  <Box
                    key={message.id || idx}
                    sx={{
                      alignSelf: isUser ? 'flex-end' : 'flex-start',
                      maxWidth: '86%',
                      bgcolor: isUser ? c.accent.primary : c.bg.surface,
                      color: isUser ? c.text.inverse : c.text.primary,
                      border: isUser ? 'none' : `1px solid ${c.border.subtle}`,
                      borderRadius: 1.25,
                      px: 1.5,
                      py: 1.25,
                    }}
                  >
                    {!isUser && (
                      <Typography sx={{ color: c.text.muted, fontSize: '0.7rem', mb: 0.5 }}>
                        Swarm
                      </Typography>
                    )}
                    <Typography sx={{ fontSize: '0.88rem', lineHeight: 1.55, whiteSpace: 'pre-wrap' }}>
                      {body}
                    </Typography>
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
                              variant={isSelected ? 'contained' : isCustom ? 'outlined' : 'contained'}
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
                                borderWidth: isSelected ? 2 : undefined,
                              }}
                            >
                              {label}
                            </Button>
                          );
                        })}
                      </Box>
                    )}
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
                    {!isUser && projectIntake.action?.type === 'start_implementation' && (
                      <Box sx={{ mt: 1, display: 'flex', flexDirection: 'column', gap: 0.5, alignItems: 'flex-start' }}>
                        <Button
                          size="small"
                          variant="contained"
                          disabled={!projectIntake.action.enabled || swarmState.actionLoading || isImplementationActionRunning || !activeSwarmId}
                          onClick={(e) => {
                            e.stopPropagation();
                            handleStartImplementation();
                          }}
                          sx={{ minHeight: 28, px: 1.25, py: 0.35, fontSize: '0.74rem', textTransform: 'none' }}
                        >
                          {isImplementationActionRunning ? 'Ejecutando implementación…' : renderText(projectIntake.action.label, 'Start Swarm Implementation')}
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
                        {!projectIntake.action.enabled && (
                          <Typography sx={{ color: c.text.tertiary, fontSize: '0.68rem' }}>
                            La implementación se habilita cuando el intake queda listo.
                          </Typography>
                        )}
                      </Box>
                    )}
                    {!isUser && metadataText && (
                      <Typography sx={{ color: c.text.tertiary, fontSize: '0.68rem', mt: 0.75 }}>
                        {metadataText}
                      </Typography>
                    )}
                  </Box>
                );
              })}

              {lastSubmittedPrompt && !lastSubmittedAlreadyPersisted && (
                <Box sx={{ alignSelf: 'flex-end', maxWidth: '86%', bgcolor: c.accent.primary, color: c.text.inverse, borderRadius: 1.25, px: 1.5, py: 1.25 }}>
                  <Typography sx={{ fontSize: '0.88rem', lineHeight: 1.55, whiteSpace: 'pre-wrap' }}>
                    {lastSubmittedPrompt}
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

              {swarmState.actionLoading && (
                <Box sx={{ alignSelf: 'flex-start', maxWidth: '86%', bgcolor: c.bg.surface, border: `1px solid ${c.border.subtle}`, borderRadius: 1.25, px: 1.5, py: 1 }}>
                  <Typography sx={{ fontSize: '0.78rem', color: c.text.muted }}>
                    Swarm is working…
                  </Typography>
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

          <Box sx={{ flexShrink: 0, p: 1.5, borderTop: `1px solid ${c.border.subtle}`, bgcolor: c.bg.surface }}>
            <Box sx={{ maxWidth: 720, mx: 'auto', border: `1px solid ${c.border.subtle}`, borderRadius: 1.25, bgcolor: c.bg.surface, boxShadow: c.shadow.md }}>
              <Box
                onPointerDown={(e) => e.stopPropagation()}
                onClick={(e) => e.stopPropagation()}
                sx={{ px: 1.5, pt: 1.25, pb: 0.25 }}
              >
                <InputBase
                  multiline
                  fullWidth
                  minRows={1}
                  maxRows={5}
                  inputRef={promptInputRef}
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  onKeyDownCapture={(e) => {
                    e.stopPropagation();
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleStart();
                    }
                  }}
                  onKeyUpCapture={(e) => e.stopPropagation()}
                  onKeyDown={(e) => e.stopPropagation()}
                  placeholder={customIntakeMode ? 'Escribí tu respuesta personalizada…' : 'Message Swarm…'}
                  sx={{ fontSize: '0.95rem', color: c.text.primary, lineHeight: 1.55 }}
                />
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', px: 1, pb: 0.75 }}>
                <Typography sx={{ color: c.text.tertiary, fontSize: '0.75rem' }}>
                  Shift+Enter for new line
                </Typography>
                <IconButton
                  size="small"
                  onClick={handleStart}
                  disabled={swarmState.actionLoading || (!prompt.trim() && !activeSwarmId)}
                  sx={{
                    bgcolor: c.accent.primary,
                    color: c.text.inverse,
                    p: 0.5,
                    width: 28,
                    height: 28,
                    '&:hover': { bgcolor: c.accent.hover },
                    '&.Mui-disabled': { bgcolor: c.bg.secondary, color: c.text.ghost },
                  }}
                >
                  {swarmState.actionLoading ? <HourglassEmptyIcon sx={{ fontSize: 16 }} /> : <ArrowUpwardIcon sx={{ fontSize: 16 }} />}
                </IconButton>
              </Box>
            </Box>
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

        <Box sx={{ borderLeft: `1px solid ${c.border.subtle}`, bgcolor: c.bg.surface, overflow: 'auto', p: 1.5 }}>
          <Typography sx={{ color: c.text.muted, fontSize: '0.72rem', mb: 1 }}>
            Swarm {activeSwarmId ? `· ${activeSwarmId}` : '· not started'}
          </Typography>

          {renderPanelHeader('tasks', 'Tasks', tasks.length)}
          {openPanelSections.tasks && (tasks.length === 0 ? (
            <Typography sx={{ color: c.text.tertiary, fontSize: '0.78rem', mb: 1.5 }}>No tasks loaded.</Typography>
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
              {finalResult && typeof finalResult === 'object' && (
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
