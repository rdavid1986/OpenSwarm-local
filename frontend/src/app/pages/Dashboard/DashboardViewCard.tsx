import React, { useState, useRef, useCallback, useEffect, useMemo } from 'react';
import { createPortal } from 'react-dom';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import CircularProgress from '@mui/material/CircularProgress';
import Button from '@mui/material/Button';
import RefreshIcon from '@mui/icons-material/Refresh';
import BoltIcon from '@mui/icons-material/Bolt';
import CloseIcon from '@mui/icons-material/Close';
import GridViewRoundedIcon from '@mui/icons-material/GridViewRounded';
import OpenInFullIcon from '@mui/icons-material/OpenInFull';
import CloseFullscreenIcon from '@mui/icons-material/CloseFullscreen';
import DifferenceIcon from '@mui/icons-material/Difference';
import { Output, OutputIterationRecord, acceptOutputIteration, autoRunOutput, autoRunAgentOutput, discardOutputIteration, executeOutput, OutputExecuteResult, fetchOutputIterations, getBackendCode, SERVE_BASE, workspaceIdFromPath } from '@/shared/state/outputsSlice';
import { addViewCard, GRID_GAP, setViewCardPosition, setViewCardSize, removeViewCard, setViewCardDevicePreset } from '@/shared/state/dashboardLayoutSlice';
import { useAppDispatch } from '@/shared/hooks';
import { useClaudeTokens } from '@/shared/styles/ThemeContext';
import ViewPreview, { ViewPreviewHandle } from '@/app/pages/Views/ViewPreview';
import { getDefault } from '@/app/pages/Views/InputSchemaForm';
import { useOverlayScrollPassthrough } from './useOverlayScrollPassthrough';
import OutputDiffPanel, { OutputDiffRow } from './OutputDiffPanel';
import EditableOutputSurface from '@/app/components/EditableOutputSurface';

type ResizeDir = 'n' | 's' | 'e' | 'w' | 'ne' | 'nw' | 'se' | 'sw';

const EDGE_THICKNESS = 6;
const CORNER_SIZE = 14;
const MIN_W = 320;
const MIN_H = 200;
const PREVIEW_HEADER_H = 40;
const PREVIEW_BODY_PAD = 16;
const MAX_PRESET_FRAME_W = 960;
const MAX_PRESET_FRAME_H = 680;

type DevicePresetKey = 'desktop-full-hd' | 'desktop' | 'laptop' | 'tablet' | 'mobile' | 'custom';

type DevicePreset = { label: string; width: number; height: number };

function buildOutputDiffRows(iteration: OutputIterationRecord | null): OutputDiffRow[] {
  if (!iteration) return [];
  const before = iteration.files_before || {};
  const after = iteration.files_after || {};
  const paths = Array.from(new Set([...Object.keys(before), ...Object.keys(after)])).sort();

  return paths.map((path) => {
    const beforeContent = before[path] ?? '';
    const afterContent = after[path] ?? '';
    let status: OutputDiffRow['status'] = 'unchanged';
    if (!(path in before)) status = 'added';
    else if (!(path in after)) status = 'removed';
    else if (beforeContent !== afterContent) status = 'modified';

    return { path, status, before: beforeContent, after: afterContent };
  });
}

function countChangedDiffRows(rows: OutputDiffRow[]): number {
  return rows.filter((row) => row.status !== 'unchanged').length;
}

const DEVICE_PRESETS: Record<DevicePresetKey, DevicePreset> = {
  'desktop-full-hd': { label: 'Desktop Full HD', width: 1920, height: 1080 },
  desktop: { label: 'Desktop', width: 1440, height: 900 },
  laptop: { label: 'Laptop', width: 1366, height: 768 },
  tablet: { label: 'Tablet', width: 768, height: 1024 },
  mobile: { label: 'Mobile', width: 390, height: 844 },
  // Apps-3.D can add editable custom dimensions; keep it visible now without persistence.
  custom: { label: 'Custom', width: 1440, height: 900 },
};

const getPresetCardSize = (preset: DevicePreset) => {
  const frameScale = Math.min(
    1,
    MAX_PRESET_FRAME_W / preset.width,
    MAX_PRESET_FRAME_H / preset.height,
  );
  return {
    width: Math.round(preset.width * frameScale + PREVIEW_BODY_PAD * 2),
    height: Math.round(preset.height * frameScale + PREVIEW_BODY_PAD * 2 + PREVIEW_HEADER_H),
  };
};

const CURSOR_MAP: Record<ResizeDir, string> = {
  n: 'ns-resize', s: 'ns-resize', e: 'ew-resize', w: 'ew-resize',
  nw: 'nwse-resize', se: 'nwse-resize', ne: 'nesw-resize', sw: 'nesw-resize',
};

function isPreviewHeaderInteractiveTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return Boolean(target.closest('button, select, input, textarea, a, [role="button"], [data-preview-control="true"]'));
}

const HANDLE_DEFS: { dir: ResizeDir; sx: Record<string, any> }[] = [
  { dir: 'n',  sx: { top: -EDGE_THICKNESS / 2, left: CORNER_SIZE, right: CORNER_SIZE, height: EDGE_THICKNESS } },
  { dir: 's',  sx: { bottom: -EDGE_THICKNESS / 2, left: CORNER_SIZE, right: CORNER_SIZE, height: EDGE_THICKNESS } },
  { dir: 'w',  sx: { left: -EDGE_THICKNESS / 2, top: CORNER_SIZE, bottom: CORNER_SIZE, width: EDGE_THICKNESS } },
  { dir: 'e',  sx: { right: -EDGE_THICKNESS / 2, top: CORNER_SIZE, bottom: CORNER_SIZE, width: EDGE_THICKNESS } },
  { dir: 'nw', sx: { top: -EDGE_THICKNESS / 2, left: -EDGE_THICKNESS / 2, width: CORNER_SIZE, height: CORNER_SIZE } },
  { dir: 'ne', sx: { top: -EDGE_THICKNESS / 2, right: -EDGE_THICKNESS / 2, width: CORNER_SIZE, height: CORNER_SIZE } },
  { dir: 'sw', sx: { bottom: -EDGE_THICKNESS / 2, left: -EDGE_THICKNESS / 2, width: CORNER_SIZE, height: CORNER_SIZE } },
  { dir: 'se', sx: { bottom: -EDGE_THICKNESS / 2, right: -EDGE_THICKNESS / 2, width: CORNER_SIZE, height: CORNER_SIZE } },
];

interface Props {
  viewCardId: string;
  output: Output;
  previewKind?: 'stable' | 'candidate' | 'iteration';
  iterationId?: string | null;
  candidateWorkspacePath?: string | null;
  title?: string | null;
  devicePreset?: DevicePresetKey | null;
  cardX: number;
  cardY: number;
  cardWidth: number;
  cardHeight: number;
  zoom?: number;
  panX?: number;
  panY?: number;
  cmdHeld?: boolean;
  isSelected?: boolean;
  isHighlighted?: boolean;
  multiDragDelta?: { dx: number; dy: number } | null;
  onCardSelect?: (id: string, type: 'agent' | 'view', shiftKey: boolean) => void;
  onDragStart?: (id: string, type: 'agent' | 'view') => void;
  onDragMove?: (dx: number, dy: number, mouseX?: number, mouseY?: number) => void;
  onDragEnd?: (dx: number, dy: number, didDrag: boolean) => void;
  cardZOrder?: number;
  onDoubleClick?: (id: string, type: 'agent' | 'view' | 'browser') => void;
  onBringToFront?: (id: string, type: 'agent' | 'view' | 'browser') => void;
  onFocusViewCard?: (id: string) => void;
  onRefineOutput?: (output: Output, preset: DevicePresetKey) => void;
}

const DashboardViewCard: React.FC<Props> = ({
  viewCardId, output, previewKind = 'stable', iterationId = null, candidateWorkspacePath = null, title = null, devicePreset = null,
  cardX, cardY, cardWidth, cardHeight, zoom = 1, panX = 0, panY = 0, cmdHeld = false,
  isSelected = false, isHighlighted = false, multiDragDelta, onCardSelect, onDragStart, onDragMove, onDragEnd,
  cardZOrder = 0, onDoubleClick, onBringToFront, onFocusViewCard, onRefineOutput,
}) => {
  const c = useClaudeTokens();
  const dispatch = useAppDispatch();
  const scrollOverlayRef = useOverlayScrollPassthrough(isSelected);
  const previewRef = useRef<ViewPreviewHandle>(null);

  const [inputData, setInputData] = useState<Record<string, any>>(() => getDefault(output.input_schema));
  const [backendResult, setBackendResult] = useState<Record<string, any> | null>(null);
  const [autoRunning, setAutoRunning] = useState(false);
  const [selectedPreset, setSelectedPreset] = useState<DevicePresetKey>(devicePreset || 'desktop');
  const [isMaximized, setIsMaximized] = useState(false);
  const [bodySize, setBodySize] = useState({ width: 0, height: 0 });
  const previewBodyRef = useRef<HTMLDivElement>(null);

  const [previewMode, setPreviewMode] = useState<'stable' | 'candidate'>(previewKind === 'stable' ? 'stable' : 'candidate');
  const [candidateIteration, setCandidateIteration] = useState<OutputIterationRecord | null>(null);
  const [latestCandidateIteration, setLatestCandidateIteration] = useState<OutputIterationRecord | null>(null);
  const [previewRevision, setPreviewRevision] = useState(0);
  const [seenCompareIterationKey, setSeenCompareIterationKey] = useState<string | null>(previewKind === 'stable' ? null : iterationId);

  const [showDiffPanel, setShowDiffPanel] = useState(false);
  const [iterationActionLoading, setIterationActionLoading] = useState<'accept' | 'discard' | null>(null);
  const [iterationActionError, setIterationActionError] = useState<string | null>(null);


  const hasAutoRun = !!(output.auto_run_config?.enabled && output.auto_run_config?.prompt);
  const selectedDevice = DEVICE_PRESETS[selectedPreset];

  const refreshCandidateIterations = useCallback(async () => {
    const iterations = await dispatch(fetchOutputIterations(output.id)).unwrap();
    const candidates = iterations.filter((iteration) => iteration.status === 'candidate' && iteration.candidate_workspace_path);
    const selectedCandidate = iterationId
      ? candidates.find((iteration) => iteration.iteration_id === iterationId)
      : [...candidates].reverse()[0];
    const latestCandidate = [...candidates].reverse()[0];
    setCandidateIteration(selectedCandidate ?? null);
    setLatestCandidateIteration(latestCandidate ?? null);
    setPreviewRevision((value) => value + 1);
    if (selectedCandidate) {
      setPreviewMode(previewKind === 'stable' ? 'stable' : 'candidate');
      setIterationActionError(null);
    } else {
      setPreviewMode('stable');
      setShowDiffPanel(false);
    }
    return selectedCandidate ?? null;
  }, [dispatch, iterationId, output.id, previewKind]);

  useEffect(() => {
    let cancelled = false;
    refreshCandidateIterations().catch(() => {
      if (!cancelled) {
        setCandidateIteration(null);
        setLatestCandidateIteration(null);
        setPreviewMode('stable');
        setShowDiffPanel(false);
      }
    });
    return () => { cancelled = true; };
  }, [refreshCandidateIterations]);

  useEffect(() => {
    const handleOutputIterationsUpdated = (event: Event) => {
      const detail = (event as CustomEvent<{ outputId?: string }>).detail;
      if (detail?.outputId && detail.outputId !== output.id) return;
      void refreshCandidateIterations();
    };
    window.addEventListener('openswarm:output-iterations-updated', handleOutputIterationsUpdated);
    return () => window.removeEventListener('openswarm:output-iterations-updated', handleOutputIterationsUpdated);
  }, [output.id, refreshCandidateIterations]);

  const candidateWorkspaceId = workspaceIdFromPath(candidateIteration?.candidate_workspace_path || candidateWorkspacePath);
  const compareCandidateIteration = latestCandidateIteration || candidateIteration;
  const compareCandidateWorkspaceId = workspaceIdFromPath(compareCandidateIteration?.candidate_workspace_path);
  const stableServeUrl = `${SERVE_BASE}/${output.id}/serve/index.html`;
  const candidateVersionKey = [
    candidateIteration?.iteration_id || '',
    candidateIteration?.updated_at || '',
    String(previewRevision),
  ].join(':');
  const candidateServeUrl = candidateWorkspaceId
    ? `${SERVE_BASE}/workspace/${candidateWorkspaceId}/serve/index.html?_candidate_rev=${encodeURIComponent(candidateVersionKey)}`
    : null;
  const compareCandidateServeUrl = compareCandidateWorkspaceId
    ? `${SERVE_BASE}/workspace/${compareCandidateWorkspaceId}/serve/index.html?_candidate_rev=${encodeURIComponent([
      compareCandidateIteration?.iteration_id || '',
      compareCandidateIteration?.updated_at || '',
      String(previewRevision),
    ].join(':'))}`
    : null;
  const activeServeUrl = useMemo(() => {
    if (previewMode === 'candidate' && candidateServeUrl) {
      return candidateServeUrl;
    }
    return stableServeUrl;
  }, [candidateServeUrl, previewMode, stableServeUrl]);

  const handleAcceptCandidate = useCallback(async () => {
    if (!candidateIteration || iterationActionLoading) return;
    const shouldCloseAfterIterationAction = previewKind !== 'stable' || viewCardId !== output.id;
    const stableViewCardId = output.id;
    setIterationActionLoading('accept');
    setIterationActionError(null);
    try {
      await dispatch(acceptOutputIteration(candidateIteration.iteration_id)).unwrap();
      window.dispatchEvent(new CustomEvent('openswarm:output-iterations-updated', { detail: { outputId: output.id } }));
      if (shouldCloseAfterIterationAction) {
        dispatch(removeViewCard(viewCardId));
        window.setTimeout(() => {
          onFocusViewCard?.(stableViewCardId);
        }, 80);
        return;
      }
      await refreshCandidateIterations();
      setPreviewMode('stable');
      setShowDiffPanel(false);
      previewRef.current?.reload();
      window.setTimeout(() => {
        onFocusViewCard?.(stableViewCardId);
      }, 80);
    } catch (error: any) {
      setIterationActionError(error?.message || 'Accept candidate failed');
    } finally {
      setIterationActionLoading(null);
    }
  }, [candidateIteration, dispatch, iterationActionLoading, onFocusViewCard, output.id, previewKind, refreshCandidateIterations, viewCardId]);

  const handleDiscardCandidate = useCallback(async () => {
    if (!candidateIteration || iterationActionLoading) return;
    const shouldCloseAfterIterationAction = previewKind !== 'stable' || viewCardId !== output.id;
    setIterationActionLoading('discard');
    setIterationActionError(null);
    try {
      await dispatch(discardOutputIteration(candidateIteration.iteration_id)).unwrap();
      window.dispatchEvent(new CustomEvent('openswarm:output-iterations-updated', { detail: { outputId: output.id } }));
      if (shouldCloseAfterIterationAction) {
        dispatch(removeViewCard(viewCardId));
        return;
      }
      await refreshCandidateIterations();
      setPreviewMode('stable');
      setShowDiffPanel(false);
      previewRef.current?.reload();
    } catch (error: any) {
      setIterationActionError(error?.message || 'Discard candidate failed');
    } finally {
      setIterationActionLoading(null);
    }
  }, [candidateIteration, dispatch, iterationActionLoading, output.id, previewKind, refreshCandidateIterations, viewCardId]);

  const showCandidateIterationControls = previewKind !== 'stable' && Boolean(candidateIteration);
  const outputDiffRows = useMemo(() => buildOutputDiffRows(candidateIteration), [candidateIteration]);
  const changedDiffCount = useMemo(() => countChangedDiffRows(outputDiffRows), [outputDiffRows]);
  const compareDiffRows = useMemo(() => buildOutputDiffRows(compareCandidateIteration), [compareCandidateIteration]);
  const compareChangedDiffCount = useMemo(() => countChangedDiffRows(compareDiffRows), [compareDiffRows]);
  const compareIterationSeenKey = compareCandidateIteration
    ? [
        compareCandidateIteration.iteration_id || '',
        compareCandidateIteration.updated_at || '',
        String(compareChangedDiffCount),
      ].join(':')
    : null;
  const shouldHighlightCompare = Boolean(
    previewKind === 'stable'
    && compareCandidateIteration
    && compareIterationSeenKey !== seenCompareIterationKey
    && compareChangedDiffCount > 0
  );

  // ---- Drag via header ----
  const DRAG_THRESHOLD = 3;
  const dragState = useRef<{ startX: number; startY: number; origX: number; origY: number; startPanX: number; startPanY: number } | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [localDragPos, setLocalDragPos] = useState<{ x: number; y: number } | null>(null);
  const didDrag = useRef(false);
  const justDraggedRef = useRef(false);
  const lastPointerRef = useRef<{ clientX: number; clientY: number }>({ clientX: 0, clientY: 0 });

  const panRef = useRef({ panX, panY });
  panRef.current = { panX, panY };
  const zoomRef = useRef(zoom);
  zoomRef.current = zoom;

  useEffect(() => {
    const el = previewBodyRef.current;
    if (!el) return;

    const updateBodySize = () => {
      const rect = el.getBoundingClientRect();
      setBodySize({ width: rect.width, height: rect.height });
    };

    updateBodySize();
    const observer = new ResizeObserver(updateBodySize);
    observer.observe(el);
    return () => observer.disconnect();
  }, [isMaximized]);

  const handleDragPointerDown = useCallback((e: React.PointerEvent) => {
    if (isMaximized) return;
    if (e.button !== 0) return;
    if (isPreviewHeaderInteractiveTarget(e.target)) return;
    e.preventDefault();
    e.stopPropagation();
    dragState.current = { startX: e.clientX, startY: e.clientY, origX: cardX, origY: cardY, startPanX: panRef.current.panX, startPanY: panRef.current.panY };
    lastPointerRef.current = { clientX: e.clientX, clientY: e.clientY };
    didDrag.current = false;
    setIsDragging(true);
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    onDragStart?.(viewCardId, 'view');
  }, [cardX, cardY, isMaximized, onDragStart, viewCardId]);

  const recomputeDragPos = useCallback(() => {
    const ds = dragState.current;
    if (!ds || !didDrag.current) return;
    const { clientX, clientY } = lastPointerRef.current;
    const rawDx = clientX - ds.startX;
    const rawDy = clientY - ds.startY;
    const z = zoomRef.current;
    const panDx = (panRef.current.panX - ds.startPanX) / z;
    const panDy = (panRef.current.panY - ds.startPanY) / z;
    const dx = rawDx / z - panDx;
    const dy = rawDy / z - panDy;
    setLocalDragPos({ x: ds.origX + dx, y: ds.origY + dy });
    onDragMove?.(dx, dy, clientX, clientY);
  }, [onDragMove]);

  useEffect(() => {
    if (isDragging && didDrag.current) recomputeDragPos();
  }, [panX, panY, isDragging, recomputeDragPos]);

  const handleDragPointerMove = useCallback((e: React.PointerEvent) => {
    if (!dragState.current) return;
    const rawDx = e.clientX - dragState.current.startX;
    const rawDy = e.clientY - dragState.current.startY;
    if (!didDrag.current && Math.sqrt(rawDx * rawDx + rawDy * rawDy) < DRAG_THRESHOLD) return;
    didDrag.current = true;
    lastPointerRef.current = { clientX: e.clientX, clientY: e.clientY };
    recomputeDragPos();
  }, [recomputeDragPos]);

  const handleDragPointerUp = useCallback((e: React.PointerEvent) => {
    if (!dragState.current) return;
    const z = zoomRef.current;
    const panDx = (panRef.current.panX - dragState.current.startPanX) / z;
    const panDy = (panRef.current.panY - dragState.current.startPanY) / z;
    const dx = (e.clientX - dragState.current.startX) / z - panDx;
    const dy = (e.clientY - dragState.current.startY) / z - panDy;
    if (didDrag.current) {
      let finalX = dragState.current.origX + dx;
      let finalY = dragState.current.origY + dy;
      // Snap to 24px grid (hold Shift to bypass)
      if (!e.shiftKey) {
        finalX = Math.round(finalX / 24) * 24;
        finalY = Math.round(finalY / 24) * 24;
      }
      dispatch(setViewCardPosition({
        outputId: output.id,
        viewCardId,
        x: finalX,
        y: finalY,
      }));
      justDraggedRef.current = true;
      requestAnimationFrame(() => { justDraggedRef.current = false; });
    }
    onDragEnd?.(dx, dy, didDrag.current);
    dragState.current = null;
    didDrag.current = false;
    setLocalDragPos(null);
    setIsDragging(false);
    (e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId);
  }, [dispatch, output.id, viewCardId, onDragEnd]);

  // ---- Resize ----
  const resizeRef = useRef<{
    dir: ResizeDir; startX: number; startY: number;
    origX: number; origY: number; origW: number; origH: number;
  } | null>(null);
  const [isResizing, setIsResizing] = useState(false);
  const [localResize, setLocalResize] = useState<{ x: number; y: number; w: number; h: number } | null>(null);

  const handleResizeDown = useCallback(
    (dir: ResizeDir) => (e: React.PointerEvent) => {
      if (isMaximized) return;
      if (e.button !== 0) return;
      e.preventDefault();
      e.stopPropagation();
      resizeRef.current = {
        dir, startX: e.clientX, startY: e.clientY,
        origX: cardX, origY: cardY, origW: cardWidth, origH: cardHeight,
      };
      setIsResizing(true);
      (e.target as HTMLElement).setPointerCapture(e.pointerId);
    },
    [cardX, cardY, cardWidth, cardHeight, isMaximized],
  );

  const computeResize = useCallback(
    (e: React.PointerEvent) => {
      if (!resizeRef.current) return null;
      const { dir, startX, startY, origX, origY, origW, origH } = resizeRef.current;
      const dx = (e.clientX - startX) / zoom;
      const dy = (e.clientY - startY) / zoom;
      let newX = origX, newY = origY, newW = origW, newH = origH;
      if (dir.includes('e')) newW = origW + dx;
      if (dir.includes('w')) { newW = origW - dx; newX = origX + dx; }
      if (dir.includes('s')) newH = origH + dy;
      if (dir.includes('n')) { newH = origH - dy; newY = origY + dy; }
      if (newW < MIN_W) { if (dir.includes('w')) newX = origX + origW - MIN_W; newW = MIN_W; }
      if (newH < MIN_H) { if (dir.includes('n')) newY = origY + origH - MIN_H; newH = MIN_H; }
      return { x: newX, y: newY, w: newW, h: newH };
    },
    [zoom],
  );

  const handleResizeMove = useCallback(
    (e: React.PointerEvent) => {
      const result = computeResize(e);
      if (result) setLocalResize(result);
    },
    [computeResize],
  );

  const handleResizeUp = useCallback((e: React.PointerEvent) => {
    if (!resizeRef.current) return;
    const result = computeResize(e);
    if (result) {
      dispatch(setViewCardPosition({ outputId: output.id, viewCardId, x: result.x, y: result.y }));
      dispatch(setViewCardSize({ outputId: output.id, viewCardId, width: result.w, height: result.h }));
    }
    resizeRef.current = null;
    setLocalResize(null);
    setIsResizing(false);
    (e.target as HTMLElement).releasePointerCapture(e.pointerId);
  }, [computeResize, dispatch, output.id, viewCardId]);

  const handleRemove = (e: React.MouseEvent) => {
    e.stopPropagation();
    dispatch(removeViewCard(viewCardId));
  };

  const handleRefresh = (e: React.MouseEvent) => {
    e.stopPropagation();
    previewRef.current?.reload();
  };

  const handlePresetChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    e.stopPropagation();
    const nextPresetKey = e.target.value as DevicePresetKey;
    setSelectedPreset(nextPresetKey);
    if (!isMaximized) {
      const { width, height } = getPresetCardSize(DEVICE_PRESETS[nextPresetKey]);
      dispatch(setViewCardSize({ outputId: output.id, viewCardId, width, height }));
    }
    dispatch(setViewCardDevicePreset({ outputId: output.id, viewCardId, devicePreset: nextPresetKey }));
  };


  const handleMaximizeToggle = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsMaximized((prev) => !prev);
  };

  const handleRefineOutput = (e: React.MouseEvent) => {
    e.stopPropagation();
    onRefineOutput?.(output, selectedPreset);
  };

  const handleOpenCandidatePreview = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!compareCandidateIteration || !compareCandidateServeUrl) return;
    const candidateViewCardId = `${output.id}::candidate::${compareCandidateIteration.iteration_id}`;
    setSeenCompareIterationKey(compareIterationSeenKey);
    dispatch(addViewCard({
      outputId: output.id,
      viewCardId: candidateViewCardId,
      previewKind: 'candidate',
      iterationId: compareCandidateIteration.iteration_id,
      candidateWorkspacePath: compareCandidateIteration.candidate_workspace_path || null,
      parentViewCardId: viewCardId,
      title: 'Candidate Preview',
      x: cardX + cardWidth + GRID_GAP,
      y: cardY,
      width: cardWidth,
      height: cardHeight,
    }));
    window.setTimeout(() => {
      onBringToFront?.(candidateViewCardId, 'view');
      onCardSelect?.(candidateViewCardId, 'view', false);
      onFocusViewCard?.(candidateViewCardId);
    }, 80);
  };

  const handleAutoRun = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!output.auto_run_config?.prompt) return;
    setAutoRunning(true);

    const config = output.auto_run_config;
    const forcedToolNames = config.forced_tools?.flatMap((ft) => ft.tools) ?? [];

    try {
      if (forcedToolNames.length > 0) {
        const res = await dispatch(autoRunAgentOutput({
          prompt: config.prompt,
          input_schema: output.input_schema,
          output_id: output.id,
          model: config.model,
          forced_tools: forcedToolNames,
          context_paths: config.context_paths,
        })).unwrap();

        // For agent-based auto-run, we execute with default input for now
        // since the agent session result flow is complex for dashboard cards
        const execRes = await dispatch(executeOutput({
          output_id: output.id,
          input_data: inputData,
        })).unwrap();
        setInputData(execRes.input_data);
        setBackendResult(execRes.backend_result);
      } else {
        const res = await dispatch(autoRunOutput({
          prompt: config.prompt,
          input_schema: output.input_schema,
          backend_code: getBackendCode(output) ?? undefined,
          context_paths: config.context_paths,
          forced_tools: forcedToolNames.length > 0 ? forcedToolNames : undefined,
          model: config.model,
        })).unwrap();
        if (res.input_data) {
          setInputData(res.input_data);
          setBackendResult(res.backend_result);
        }
      }
    } catch {
      // Silently handle errors on dashboard
    } finally {
      setAutoRunning(false);
    }
  };

  const mdDx = (!isDragging && isSelected && multiDragDelta) ? multiDragDelta.dx : 0;
  const mdDy = (!isDragging && isSelected && multiDragDelta) ? multiDragDelta.dy : 0;
  const displayX = localResize?.x ?? localDragPos?.x ?? (cardX + mdDx);
  const displayY = localResize?.y ?? localDragPos?.y ?? (cardY + mdDy);
  const displayW = localResize?.w ?? cardWidth;
  const displayH = localResize?.h ?? cardHeight;
  const noTransition = isDragging || isResizing || (isSelected && !!multiDragDelta);
  const fallbackBodyW = isMaximized ? window.innerWidth - 24 : displayW;
  const fallbackBodyH = isMaximized ? window.innerHeight - 24 - PREVIEW_HEADER_H : displayH - PREVIEW_HEADER_H;
  const measuredBodyW = bodySize.width || fallbackBodyW;
  const measuredBodyH = bodySize.height || fallbackBodyH;
  const availableW = Math.max(1, (isMaximized ? measuredBodyW : displayW) - PREVIEW_BODY_PAD * 2);
  const availableH = Math.max(1, (isMaximized ? measuredBodyH : displayH - PREVIEW_HEADER_H) - PREVIEW_BODY_PAD * 2);
  const previewScale = isMaximized
    ? 1
    : Math.min(
      1,
      availableW / selectedDevice.width,
      availableH / selectedDevice.height,
    );
  const scaledFrameW = selectedDevice.width * previewScale;
  const scaledFrameH = selectedDevice.height * previewScale;

  const card = (
    <Box
      data-select-type="view-card"
      data-select-id={viewCardId}
      data-select-meta={JSON.stringify({ name: output.name, description: output.description })}
      onPointerDownCapture={() => onBringToFront?.(viewCardId, 'view')}
      onClick={(e: React.MouseEvent) => {
        if (justDraggedRef.current) return;
        onCardSelect?.(viewCardId, 'view', e.shiftKey);
      }}
      onDoubleClick={(e: React.MouseEvent) => {
        e.stopPropagation();
        onDoubleClick?.(viewCardId, 'view');
      }}
      sx={{
        position: isMaximized ? 'fixed' : 'absolute',
        // contain: iframe app repaints don't shake the rest of the dashboard.
        contain: 'layout style',
        ...(isMaximized
          ? { inset: 12, width: 'auto', height: 'auto' }
          : { left: displayX, top: displayY, width: displayW, height: displayH }),
        borderRadius: `${c.radius.lg}px`,
        border: isHighlighted
          ? `2px solid ${c.accent.primary}`
          : isSelected ? '2px solid #3b82f6' : `1px solid ${c.border.medium}`,
        bgcolor: c.bg.surface,
        boxShadow: isHighlighted
          ? `0 0 0 3px ${c.accent.primary}50, 0 0 20px ${c.accent.primary}35, 0 0 40px ${c.accent.primary}15`
          : isDragging || isResizing
            ? c.shadow.lg
            : isSelected
              ? `0 0 0 1px #3b82f6, ${c.shadow.md}`
              : c.shadow.md,
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        zIndex: isMaximized ? 999999 : ((isDragging || isResizing) ? 999999 : cardZOrder),
        transition: noTransition ? 'none' : 'box-shadow 0.2s',
        '&:hover .resize-handle': { opacity: 1 },
        ...(isHighlighted && {
          animation: 'card-highlight-pulse 2s ease-out forwards',
          '@keyframes card-highlight-pulse': {
            '0%': {
              boxShadow: `0 0 0 3px ${c.accent.primary}70, 0 0 24px ${c.accent.primary}50, 0 0 48px ${c.accent.primary}25`,
            },
            '25%': {
              boxShadow: `0 0 0 4px ${c.accent.primary}55, 0 0 30px ${c.accent.primary}40, 0 0 56px ${c.accent.primary}20`,
            },
            '50%': {
              boxShadow: `0 0 0 3px ${c.accent.primary}45, 0 0 22px ${c.accent.primary}30, 0 0 44px ${c.accent.primary}15`,
            },
            '75%': {
              boxShadow: `0 0 0 2px ${c.accent.primary}25, 0 0 14px ${c.accent.primary}18, 0 0 28px ${c.accent.primary}08`,
            },
            '100%': {
              boxShadow: c.shadow.md,
            },
          },
        }),
      }}
    >
      {/* Selection overlay removed for ViewCard interaction: preview controls and iframe must remain immediately clickable. */}

      {/* Browser/devtools header */}
      <Box
        onPointerDown={handleDragPointerDown}
        onPointerMove={handleDragPointerMove}
        onPointerUp={handleDragPointerUp}
        sx={{
          position: 'relative',
          zIndex: 20,
          display: 'flex',
          alignItems: 'center',
          gap: 0.75,
          px: 1.5,
          py: 0.5,
          bgcolor: c.bg.secondary,
          borderBottom: `1px solid ${c.border.subtle}`,
          cursor: isMaximized ? 'default' : (isDragging ? 'grabbing' : 'grab'),
          flexShrink: 0,
          minHeight: PREVIEW_HEADER_H,
          userSelect: 'none',
        }}
      >
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            minWidth: 0,
            maxWidth: '35%',
            gap: 0.75,
          }}
        >
          <GridViewRoundedIcon sx={{ fontSize: 16, color: c.accent.primary, flexShrink: 0 }} />
          <Typography
            sx={{
              fontSize: '0.8rem',
              fontWeight: 600,
              color: c.text.primary,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {title || (previewKind === 'stable' ? output.name : 'Candidate Preview')}
          </Typography>
        </Box>

        <Box
          component="select"
          data-preview-control="true"
          value={selectedPreset}
          onChange={handlePresetChange}
          onClick={(e: React.MouseEvent) => e.stopPropagation()}
          onPointerDown={(e: React.PointerEvent) => e.stopPropagation()}
          aria-label="Preview device preset"
          sx={{
            position: 'absolute',
            left: '50%',
            transform: 'translateX(-50%)',
            maxWidth: '38%',
            height: 26,
            px: 1,
            borderRadius: `${c.radius.md}px`,
            border: `1px solid ${c.border.subtle}`,
            bgcolor: c.bg.surface,
            color: c.text.secondary,
            fontSize: '0.72rem',
            fontFamily: c.font.mono,
            outline: 'none',
            cursor: 'pointer',
          }}
        >
          {(Object.keys(DEVICE_PRESETS) as DevicePresetKey[]).map((key) => (
            <option key={key} value={key}>
              {DEVICE_PRESETS[key].label} · {DEVICE_PRESETS[key].width}×{DEVICE_PRESETS[key].height}
            </option>
          ))}
        </Box>

        <Box sx={{ flex: 1 }} />

        {candidateIteration && (
          <Tooltip title={`Candidate iteration ${candidateIteration.iteration_id}`} placement="top">
            <Box
              data-preview-control="true"
              onPointerDown={(e) => e.stopPropagation()}
              sx={{
                px: 0.75,
                py: 0.2,
                borderRadius: `${c.radius.md}px`,
                color: c.status.warning,
                border: `1px solid ${c.status.warning}55`,
                bgcolor: `${c.status.warning}10`,
                fontSize: '0.68rem',
                fontWeight: 600,
                fontFamily: c.font.mono,
                whiteSpace: 'nowrap',
              }}
            >
              Candidate
            </Box>
          </Tooltip>
        )}

        {showCandidateIterationControls && (
          <Tooltip title="Accept candidate changes" placement="top">
            <span>
              <Button
                size="small"
                data-preview-control="true"
                onClick={handleAcceptCandidate}
                onPointerDown={(e) => e.stopPropagation()}
                disabled={!!iterationActionLoading}
                sx={{
                  minWidth: 0,
                  px: 0.85,
                  py: 0.25,
                  borderRadius: `${c.radius.md}px`,
                  color: c.status.success,
                  border: `1px solid ${c.status.success}55`,
                  bgcolor: `${c.status.success}08`,
                  fontSize: '0.68rem',
                  textTransform: 'none',
                  cursor: 'pointer',
                  '&:hover': { bgcolor: `${c.status.success}18`, borderColor: c.status.success },
                }}
              >
                {iterationActionLoading === 'accept' ? 'Accepting' : 'Accept'}
              </Button>
            </span>
          </Tooltip>
        )}

        {showCandidateIterationControls && (
          <Tooltip title="Discard candidate changes" placement="top">
            <span>
              <Button
                size="small"
                data-preview-control="true"
                onClick={handleDiscardCandidate}
                onPointerDown={(e) => e.stopPropagation()}
                disabled={!!iterationActionLoading}
                sx={{
                  minWidth: 0,
                  px: 0.85,
                  py: 0.25,
                  borderRadius: `${c.radius.md}px`,
                  color: c.status.error,
                  border: `1px solid ${c.status.error}55`,
                  bgcolor: `${c.status.error}08`,
                  fontSize: '0.68rem',
                  textTransform: 'none',
                  cursor: 'pointer',
                  '&:hover': { bgcolor: `${c.status.error}18`, borderColor: c.status.error },
                }}
              >
                {iterationActionLoading === 'discard' ? 'Discarding' : 'Discard'}
              </Button>
            </span>
          </Tooltip>
        )}

        {compareCandidateIteration && compareCandidateServeUrl && `${output.id}::candidate::${compareCandidateIteration.iteration_id}` !== viewCardId && (
          <Tooltip title="Open candidate preview card beside this preview" placement="top">
            <Button
              size="small"
              data-preview-control="true"
              onClick={handleOpenCandidatePreview}
              onPointerDown={(e) => e.stopPropagation()}
              startIcon={<DifferenceIcon sx={{ fontSize: 14 }} />}
              sx={{
                minWidth: 0,
                px: 0.9,
                py: 0.25,
                borderRadius: `${c.radius.md}px`,
                color: c.text.muted,
                border: `1px solid ${shouldHighlightCompare ? c.accent.primary : c.border.medium}`,
                bgcolor: c.bg.surface,
                boxShadow: shouldHighlightCompare ? `0 0 0 1px ${c.accent.primary}22, 0 0 10px ${c.accent.primary}12` : 'none',
                animation: shouldHighlightCompare ? 'previewAttentionBreath 2.25s ease-in-out infinite' : 'none',
                '@keyframes previewAttentionBreath': {
                  '0%': { boxShadow: `0 0 0 1px ${c.accent.primary}10, 0 0 4px ${c.accent.primary}08` },
                  '50%': { boxShadow: `0 0 0 1px ${c.accent.primary}77, 0 0 18px ${c.accent.primary}38` },
                  '100%': { boxShadow: `0 0 0 1px ${c.accent.primary}10, 0 0 4px ${c.accent.primary}08` },
                },
                fontSize: '0.68rem',
                textTransform: 'none',
                cursor: 'pointer',
                '& .MuiButton-startIcon': { mr: 0.35 },
                '&:hover': { bgcolor: c.bg.muted },
              }}
            >
              Compare
            </Button>
          </Tooltip>
        )}

        {candidateIteration && (
          <Tooltip title="View candidate file diff" placement="top">
            <Button
              size="small"
              data-preview-control="true"
              onClick={() => setShowDiffPanel((value) => !value)}
              onPointerDown={(e) => e.stopPropagation()}
              startIcon={<DifferenceIcon sx={{ fontSize: 14 }} />}
              sx={{
                minWidth: 0,
                px: 0.9,
                py: 0.25,
                borderRadius: `${c.radius.md}px`,
                color: showDiffPanel ? c.text.primary : c.text.muted,
                border: `1px solid ${showDiffPanel ? c.border.strong : c.border.medium}`,
                bgcolor: showDiffPanel ? c.bg.muted : c.bg.surface,
                fontSize: '0.68rem',
                textTransform: 'none',
                cursor: 'pointer',
                '& .MuiButton-startIcon': { mr: 0.35 },
                '&:hover': { bgcolor: c.bg.muted },
              }}
            >
              Diff {changedDiffCount > 0 ? `(${changedDiffCount})` : ''}
            </Button>
          </Tooltip>
        )}

        {output.source_swarm_id && (
          <Tooltip title="Refine this app in the source Swarm" placement="top">
            <Button
              size="small"
              data-preview-control="true"
              onClick={handleRefineOutput}
              onPointerDown={(e) => e.stopPropagation()}
              sx={{
                minWidth: 0,
                px: 1,
                py: 0.25,
                borderRadius: `${c.radius.md}px`,
                color: c.status.info,
                border: `1px solid ${c.status.info}55`,
                bgcolor: `${c.status.info}08`,
                fontSize: '0.7rem',
                textTransform: 'none',
                cursor: 'pointer',
                '&:hover': {
                  bgcolor: `${c.status.info}18`,
                  borderColor: c.status.info,
                  color: c.status.info,
                },
              }}
            >
              Refine
            </Button>
          </Tooltip>
        )}

        {hasAutoRun && (
          <Tooltip title={autoRunning ? 'Running output automation...' : 'Run output automation'} placement="top">
            <span>
              <IconButton
                size="small"
                data-preview-control="true"
                onClick={handleAutoRun}
                onPointerDown={(e) => e.stopPropagation()}
                disabled={autoRunning}
                sx={{ color: '#f59e0b', p: 0.5, '&:hover': { color: '#d97706' } }}
              >
                {autoRunning ? <CircularProgress size={14} sx={{ color: '#f59e0b' }} /> : <BoltIcon sx={{ fontSize: 16 }} />}
              </IconButton>
            </span>
          </Tooltip>
        )}

        <Tooltip title="Reload iframe preview" placement="top">
          <IconButton
            size="small"
            data-preview-control="true"
            onClick={handleRefresh}
            onPointerDown={(e) => e.stopPropagation()}
            sx={{ color: c.text.muted, p: 0.5, '&:hover': { color: c.text.primary } }}
          >
            <RefreshIcon sx={{ fontSize: 16 }} />
          </IconButton>
        </Tooltip>

        <Tooltip title={isMaximized ? 'Restore canvas preview' : 'Open full-screen preview'} placement="top">
          <IconButton
            size="small"
            data-preview-control="true"
            onClick={handleMaximizeToggle}
            onPointerDown={(e) => e.stopPropagation()}
            sx={{ color: c.text.muted, p: 0.5, '&:hover': { color: c.text.primary } }}
          >
            {isMaximized ? <CloseFullscreenIcon sx={{ fontSize: 16 }} /> : <OpenInFullIcon sx={{ fontSize: 16 }} />}
          </IconButton>
        </Tooltip>


        <Tooltip title="Close preview card" placement="top">
          <IconButton
            size="small"
            data-preview-control="true"
            onClick={handleRemove}
            onPointerDown={(e) => e.stopPropagation()}
            sx={{ color: c.text.ghost, p: 0.5, '&:hover': { color: c.status.error } }}
          >
            <CloseIcon sx={{ fontSize: 16 }} />
          </IconButton>
        </Tooltip>
      </Box>

      {/* Preview body */}
      <Box
        ref={previewBodyRef}
        sx={{
          flex: 1,
          position: 'relative',
          overflow: 'auto',
          bgcolor: c.bg.page,
          p: `${PREVIEW_BODY_PAD}px`,
        }}
      >
        {iterationActionError && (
          <Box
            data-preview-control="true"
            onPointerDown={(e) => e.stopPropagation()}
            sx={{
              position: 'absolute',
              top: 12,
              left: 12,
              maxWidth: 420,
              zIndex: 8,
              px: 1,
              py: 0.65,
              borderRadius: `${c.radius.md}px`,
              color: c.status.error,
              bgcolor: `${c.status.error}12`,
              border: `1px solid ${c.status.error}44`,
              fontSize: '0.72rem',
              fontFamily: c.font.mono,
            }}
          >
            {iterationActionError}
          </Box>
        )}
        <OutputDiffPanel
          open={showDiffPanel && Boolean(candidateIteration)}
          rows={outputDiffRows}
          changedCount={changedDiffCount}
          onClose={() => setShowDiffPanel(false)}
          c={c}
        />
        <EditableOutputSurface
          output={output}
          previewMode={previewMode}
          candidateIteration={candidateIteration}
          changedCount={changedDiffCount}
          actionLoading={Boolean(iterationActionLoading)}
          onRefine={output.source_swarm_id ? () => onRefineOutput?.(output, selectedPreset) : undefined}
          onCompare={compareCandidateIteration && compareCandidateServeUrl && `${output.id}::candidate::${compareCandidateIteration.iteration_id}` !== viewCardId ? () => {
            const syntheticEvent = { stopPropagation: () => {} } as React.MouseEvent;
            handleOpenCandidatePreview(syntheticEvent);
          } : undefined}
          onOpenDiff={candidateIteration ? () => setShowDiffPanel(true) : undefined}
          onAccept={candidateIteration ? handleAcceptCandidate : undefined}
          onDiscard={candidateIteration ? handleDiscardCandidate : undefined}
        />

        <Box
            sx={{
              width: isMaximized ? 'max-content' : scaledFrameW,
              height: isMaximized ? 'max-content' : scaledFrameH,
              minWidth: isMaximized ? '100%' : scaledFrameW,
              minHeight: isMaximized ? '100%' : scaledFrameH,
              display: 'flex',
              alignItems: isMaximized && scaledFrameH < availableH ? 'center' : 'flex-start',
              justifyContent: isMaximized && scaledFrameW < availableW ? 'center' : 'flex-start',
            }}
          >
            <Box
              sx={{
                width: scaledFrameW,
                height: scaledFrameH,
                flex: '0 0 auto',
                position: 'relative',
              }}
            >
              <Box
                sx={{
                  width: selectedDevice.width,
                  height: selectedDevice.height,
                  transform: `scale(${previewScale})`,
                  transformOrigin: 'top left',
                  bgcolor: c.bg.surface,
                  border: `1px solid ${c.border.medium}`,
                  borderRadius: `${c.radius.md}px`,
                  boxShadow: c.shadow.md,
                  overflow: 'hidden',
                }}
              >
                <ViewPreview
                  key={`${previewMode}-${activeServeUrl}-${previewRevision}`}
                  ref={previewRef}
                  serveUrl={activeServeUrl}
                  frontendCode={output.files?.['index.html'] ?? ''}
                  inputData={inputData}
                  backendResult={backendResult}
                />
              </Box>
            </Box>
          </Box>

      </Box>

      {/* Resize handles */}
      {!isMaximized && HANDLE_DEFS.map(({ dir, sx }) => (
        <Box
          key={dir}
          className="resize-handle"
          onPointerDown={handleResizeDown(dir)}
          onPointerMove={handleResizeMove}
          onPointerUp={handleResizeUp}
          sx={{
            position: 'absolute',
            cursor: CURSOR_MAP[dir],
            opacity: 0,
            zIndex: 10,
            ...sx,
          }}
        />
      ))}
    </Box>
  );

  return isMaximized ? createPortal(card, document.body) : card;
};

export default React.memo(DashboardViewCard);
