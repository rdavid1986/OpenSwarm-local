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
} from '@/shared/state/dashboardLayoutSlice';
import {
  allowExperimentalApproval,
  chatExperimentalSwarm,
  createExperimentalSwarm,
  denyExperimentalApproval,
  fetchExperimentalSwarm,
  resumeExperimentalApproval,
  runExperimentalDag,
} from '@/shared/state/experimentalSwarmsSlice';
import { useAppDispatch, useAppSelector } from '@/shared/hooks';
import { useClaudeTokens } from '@/shared/styles/ThemeContext';
import type { CardType } from './useDashboardSelection';

type ResizeDir = 'n' | 's' | 'e' | 'w' | 'ne' | 'nw' | 'se' | 'sw';

interface Props {
  swarmCardId: string;
  swarmId?: string | null;
  cardX: number;
  cardY: number;
  cardWidth: number;
  cardHeight: number;
  cardZOrder?: number;
  zoom?: number;
  isSelected?: boolean;
  isHighlighted?: boolean;
  multiDragDelta?: { dx: number; dy: number } | null;
  onCardSelect?: (id: string, type: CardType, shiftKey: boolean) => void;
  onDragStart?: (id: string, type: CardType) => void;
  onDragMove?: (dx: number, dy: number, mouseX?: number, mouseY?: number) => void;
  onDragEnd?: (dx: number, dy: number, didDrag: boolean) => void;
  onBringToFront?: (id: string, type: CardType) => void;
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
  zoom = 1,
  isSelected = false,
  isHighlighted = false,
  multiDragDelta,
  onCardSelect,
  onDragStart,
  onDragMove,
  onDragEnd,
  onBringToFront,
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

  const didDrag = useRef(false);
  const [isDragging, setIsDragging] = useState(false);
  const [localPos, setLocalPos] = useState<{ x: number; y: number } | null>(null);
  const [localSize, setLocalSize] = useState<{ x: number; y: number; w: number; h: number } | null>(null);
  const [sideWidth, setSideWidth] = useState(280);
  const [localSideWidth, setLocalSideWidth] = useState<number | null>(null);
  const [prompt, setPrompt] = useState('');
  const [lastSubmittedPrompt, setLastSubmittedPrompt] = useState('');
  const [openPanelSections, setOpenPanelSections] = useState<Record<string, boolean>>({
    tasks: false,
    approvals: false,
    events: false,
    artifacts: false,
    finalResult: true,
  });

  const activeSwarmId = swarmId || swarmState.selectedSwarmId;
  const events = swarmState.events.slice(-8).reverse();
  const approvals = swarmState.approvals.slice(0, 5);
  const tasks = swarmState.swarm?.tasks || [];
  const chatMessages = (swarmState.messages || []).filter((message: any) => getSwarmMessageText(message));
  const lastSubmittedAlreadyPersisted = !!lastSubmittedPrompt && chatMessages.some((message: any) => {
    const role = getSwarmMessageRole(message);
    return (role === 'user' || role === 'human') && getSwarmMessageText(message) === lastSubmittedPrompt;
  });

  useEffect(() => {
    if (!activeSwarmId) return;
    dispatch(fetchExperimentalSwarm(activeSwarmId));
  }, [activeSwarmId, dispatch]);

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
      }
    }

    if (!swarmIdToRun) return;

    if (intent === 'chat') {
      await dispatch(chatExperimentalSwarm({ swarmId: swarmIdToRun, message: cleanPrompt || lastSubmittedPrompt || 'Continue' }));
      dispatch(fetchExperimentalSwarm(swarmIdToRun));
      return;
    }

    await dispatch(runExperimentalDag({ swarmId: swarmIdToRun }));
    dispatch(fetchExperimentalSwarm(swarmIdToRun));
  }, [activeSwarmId, dashboardId, dispatch, lastSubmittedPrompt, prompt, swarmCardId, swarmState.swarm?.intent]);

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
    e.preventDefault();
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
      }
      onDragEnd?.(dx, dy, didDrag.current);
      dragRef.current = null;
      didDrag.current = false;
      setLocalPos(null);
      setIsDragging(false);
    }

    if (resizeRef.current && localSize) {
      dispatch(setSwarmCardPosition({ swarmCardId, x: Math.round(localSize.x), y: Math.round(localSize.y) }));
      dispatch(setSwarmCardSize({ swarmCardId, width: Math.round(localSize.w), height: Math.round(localSize.h) }));
      resizeRef.current = null;
      setLocalSize(null);
    }

    if (sideResizeRef.current && localSideWidth != null) {
      setSideWidth(localSideWidth);
      sideResizeRef.current = null;
      setLocalSideWidth(null);
    }

    try { (e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId); } catch {}
  }, [dispatch, localSideWidth, localSize, onDragEnd, swarmCardId, zoom]);

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
  const displayH = localSize?.h ?? cardHeight;
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
          borderBottom: `1px solid ${c.border.subtle}`,
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
        <Chip size="small" label={activeSwarmId ? 'Ready' : 'New'} />
        <IconButton size="small"><MoreHorizIcon fontSize="small" /></IconButton>
        <IconButton size="small" onClick={() => dispatch(removeSwarmCard(swarmCardId))}>
          <CloseIcon fontSize="small" />
        </IconButton>
      </Box>

      <Box
        sx={{
          flex: 1,
          overflow: 'hidden',
          display: 'grid',
          gridTemplateColumns: `minmax(0, 1fr) 8px ${displaySideW}px`,
        }}
      >
        <Box sx={{ minWidth: 0, display: 'flex', flexDirection: 'column', bgcolor: c.bg.page }}>
          <Box ref={chatScrollRef} sx={{ flex: 1, overflow: 'auto', p: 2, minHeight: 0 }}>
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

              <Box ref={chatEndRef} />
            </Box>
          </Box>

          <Box sx={{ p: 1.5, borderTop: `1px solid ${c.border.subtle}`, bgcolor: c.bg.surface }}>
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
                  placeholder="Message Swarm…"
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

          {renderPanelHeader('artifacts', 'Artifacts', swarmState.artifacts.length)}
          {openPanelSections.artifacts && (swarmState.artifacts.length === 0 ? (
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
              <Typography sx={{ color: swarmState.swarm?.final_result ? c.text.primary : c.text.tertiary, fontSize: '0.78rem', lineHeight: 1.45 }}>
                {renderText(swarmState.swarm?.final_result?.summary || swarmState.swarm?.final_result, 'Pending')}
              </Typography>
            </Box>
          )}
        </Box>
      </Box>

      {HANDLE_DEFS.map(({ dir, sx }) => (
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
