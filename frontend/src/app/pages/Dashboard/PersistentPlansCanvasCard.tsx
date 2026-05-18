import React, { useCallback, useEffect, useRef, useState } from 'react';
import Box from '@mui/material/Box';
import {
  setPlansCardPosition,
  setPlansCardSize,
  togglePlansCardCollapsed,
} from '@/shared/state/dashboardLayoutSlice';
import { useAppDispatch } from '@/shared/hooks';
import { useClaudeTokens } from '@/shared/styles/ThemeContext';
import PersistentPlansCard from './PersistentPlansCard';
import type { CardType } from './useDashboardSelection';

type ResizeDir = 'n' | 's' | 'e' | 'w' | 'ne' | 'nw' | 'se' | 'sw';

const EDGE_THICKNESS = 6;
const CORNER_SIZE = 14;
const MIN_W = 420;
const MIN_H = 320;

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

interface Props {
  plansCardId: string;
  cardX: number;
  cardY: number;
  cardWidth: number;
  cardHeight: number;
  cardZOrder?: number;
  collapsed?: boolean;
  dashboardId?: string;
  zoom?: number;
  panX?: number;
  panY?: number;
  isSelected?: boolean;
  isHighlighted?: boolean;
  multiDragDelta?: { dx: number; dy: number } | null;
  onClose: () => void;
  onCardSelect?: (id: string, type: CardType, shiftKey: boolean) => void;
  onDragStart?: (id: string, type: CardType) => void;
  onDragMove?: (dx: number, dy: number, mouseX?: number, mouseY?: number) => void;
  onDragEnd?: (dx: number, dy: number, didDrag: boolean) => void;
  onBringToFront?: (id: string, type: CardType) => void;
  onGoToAgent?: (sessionId: string) => void;
}

const PersistentPlansCanvasCard: React.FC<Props> = ({
  plansCardId,
  cardX,
  cardY,
  cardWidth,
  cardHeight,
  cardZOrder = 0,
  collapsed = false,
  dashboardId,
  zoom = 1,
  panX = 0,
  panY = 0,
  isSelected = false,
  isHighlighted = false,
  multiDragDelta,
  onClose,
  onCardSelect,
  onDragStart,
  onDragMove,
  onDragEnd,
  onBringToFront,
  onGoToAgent,
}) => {
  const c = useClaudeTokens();
  const dispatch = useAppDispatch();

  const dragState = useRef<{
    startX: number;
    startY: number;
    origX: number;
    origY: number;
    startPanX: number;
    startPanY: number;
  } | null>(null);

  const resizeRef = useRef<{
    dir: ResizeDir;
    startX: number;
    startY: number;
    origX: number;
    origY: number;
    origW: number;
    origH: number;
  } | null>(null);

  const didDrag = useRef(false);
  const panRef = useRef({ panX, panY });
  const zoomRef = useRef(zoom);
  const lastPointerRef = useRef({ clientX: 0, clientY: 0 });

  const [isDragging, setIsDragging] = useState(false);
  const [localDragPos, setLocalDragPos] = useState<{ x: number; y: number } | null>(null);
  const [localResize, setLocalResize] = useState<{ x: number; y: number; w: number; h: number } | null>(null);

  panRef.current = { panX, panY };
  zoomRef.current = zoom;

  const recomputeDragPos = useCallback(() => {
    const ds = dragState.current;
    if (!ds || !didDrag.current) return;

    const { clientX, clientY } = lastPointerRef.current;
    const z = zoomRef.current;
    const rawDx = clientX - ds.startX;
    const rawDy = clientY - ds.startY;
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

  const handlePointerDown = useCallback((e: React.PointerEvent) => {
    if (e.button !== 0) return;

    const target = e.target as HTMLElement | null;
    if (!target?.closest('.drag-handle')) return;
    if (target.closest('button, [role="button"], input, textarea, .MuiSelect-root')) return;

    e.preventDefault();
    e.stopPropagation();

    dragState.current = {
      startX: e.clientX,
      startY: e.clientY,
      origX: cardX,
      origY: cardY,
      startPanX: panRef.current.panX,
      startPanY: panRef.current.panY,
    };

    lastPointerRef.current = { clientX: e.clientX, clientY: e.clientY };
    didDrag.current = false;
    setIsDragging(true);
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    onDragStart?.(plansCardId, 'plans');
  }, [cardX, cardY, plansCardId, onDragStart]);

  const handlePointerMove = useCallback((e: React.PointerEvent) => {
    if (!dragState.current) return;

    const rawDx = e.clientX - dragState.current.startX;
    const rawDy = e.clientY - dragState.current.startY;

    if (!didDrag.current && Math.sqrt(rawDx * rawDx + rawDy * rawDy) < 3) return;

    didDrag.current = true;
    lastPointerRef.current = { clientX: e.clientX, clientY: e.clientY };
    recomputeDragPos();
  }, [recomputeDragPos]);

  const handlePointerUp = useCallback((e: React.PointerEvent) => {
    if (!dragState.current) return;

    const z = zoomRef.current;
    const panDx = (panRef.current.panX - dragState.current.startPanX) / z;
    const panDy = (panRef.current.panY - dragState.current.startPanY) / z;
    const dx = (e.clientX - dragState.current.startX) / z - panDx;
    const dy = (e.clientY - dragState.current.startY) / z - panDy;

    if (didDrag.current) {
      let finalX = dragState.current.origX + dx;
      let finalY = dragState.current.origY + dy;

      if (!e.shiftKey) {
        finalX = Math.round(finalX / 24) * 24;
        finalY = Math.round(finalY / 24) * 24;
      }

      dispatch(setPlansCardPosition({ plansCardId, x: finalX, y: finalY }));
    } else {
      dispatch(togglePlansCardCollapsed(plansCardId));
    }

    onDragEnd?.(dx, dy, didDrag.current);

    dragState.current = null;
    didDrag.current = false;
    setLocalDragPos(null);
    setIsDragging(false);
    (e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId);
  }, [dispatch, plansCardId, onDragEnd]);

  const handleResizeDown = useCallback((dir: ResizeDir) => (e: React.PointerEvent) => {
    if (e.button !== 0) return;

    e.preventDefault();
    e.stopPropagation();

    resizeRef.current = {
      dir,
      startX: e.clientX,
      startY: e.clientY,
      origX: cardX,
      origY: cardY,
      origW: cardWidth,
      origH: cardHeight,
    };

    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  }, [cardX, cardY, cardWidth, cardHeight]);

  const computeResize = useCallback((e: React.PointerEvent) => {
    if (!resizeRef.current) return null;

    const { dir, startX, startY, origX, origY, origW, origH } = resizeRef.current;
    const dx = (e.clientX - startX) / zoom;
    const dy = (e.clientY - startY) / zoom;

    let newX = origX;
    let newY = origY;
    let newW = origW;
    let newH = origH;

    if (dir.includes('e')) newW = origW + dx;
    if (dir.includes('w')) {
      newW = origW - dx;
      newX = origX + dx;
    }
    if (dir.includes('s')) newH = origH + dy;
    if (dir.includes('n')) {
      newH = origH - dy;
      newY = origY + dy;
    }

    if (newW < MIN_W) {
      if (dir.includes('w')) newX = origX + origW - MIN_W;
      newW = MIN_W;
    }
    if (newH < MIN_H) {
      if (dir.includes('n')) newY = origY + origH - MIN_H;
      newH = MIN_H;
    }

    return { x: newX, y: newY, w: newW, h: newH };
  }, [zoom]);

  const handleResizeMove = useCallback((e: React.PointerEvent) => {
    const result = computeResize(e);
    if (result) setLocalResize(result);
  }, [computeResize]);

  const handleResizeUp = useCallback((e: React.PointerEvent) => {
    if (!resizeRef.current) return;

    const result = computeResize(e);
    if (result) {
      dispatch(setPlansCardPosition({ plansCardId, x: result.x, y: result.y }));
      dispatch(setPlansCardSize({ plansCardId, width: result.w, height: result.h }));
    }

    resizeRef.current = null;
    setLocalResize(null);
    (e.target as HTMLElement).releasePointerCapture(e.pointerId);
  }, [computeResize, dispatch, plansCardId]);

  const mdDx = (!isDragging && isSelected && multiDragDelta) ? multiDragDelta.dx : 0;
  const mdDy = (!isDragging && isSelected && multiDragDelta) ? multiDragDelta.dy : 0;
  const displayX = localResize?.x ?? localDragPos?.x ?? (cardX + mdDx);
  const displayY = localResize?.y ?? localDragPos?.y ?? (cardY + mdDy);
  const displayW = localResize?.w ?? cardWidth;
  const displayH = collapsed ? 64 : (localResize?.h ?? cardHeight);

  return (
    <Box
      data-select-type="plans-card"
      data-select-id={plansCardId}
      data-select-meta={JSON.stringify({ name: 'Planes persistentes' })}
      onPointerDownCapture={() => onBringToFront?.(plansCardId, 'plans')}
      onClick={(e: React.MouseEvent) => {
        onCardSelect?.(plansCardId, 'plans', e.shiftKey);
      }}
      onDoubleClick={(e: React.MouseEvent) => e.stopPropagation()}
      sx={{
        position: 'absolute',
        left: displayX,
        top: displayY,
        width: displayW,
        height: displayH,
        zIndex: cardZOrder,
        border: `1px solid ${isSelected ? c.accent.primary : c.border.default}`,
        borderRadius: 1,
        overflow: 'hidden',
        bgcolor: c.bg.surface,
        boxShadow: isHighlighted ? c.shadow.lg : c.shadow.md,
        outline: isSelected ? `1px solid ${c.accent.primary}` : 'none',
      }}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
    >
      <PersistentPlansCard onClose={onClose} collapsed={collapsed} dashboardId={dashboardId} onGoToAgent={onGoToAgent} />

      {!collapsed && HANDLE_DEFS.map(({ dir, sx }) => (
        <Box
          key={dir}
          onPointerDown={handleResizeDown(dir)}
          onPointerMove={handleResizeMove}
          onPointerUp={handleResizeUp}
          sx={{
            position: 'absolute',
            zIndex: 10,
            cursor: CURSOR_MAP[dir],
            ...sx,
          }}
        />
      ))}
    </Box>
  );
};

export default PersistentPlansCanvasCard;
