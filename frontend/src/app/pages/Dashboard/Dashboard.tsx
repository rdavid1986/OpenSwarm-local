import React, { useEffect, useCallback, useRef, useState, useMemo } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import DashboardHeader from './DashboardHeader';
import { report } from '@/shared/serviceClient';
import { useAppDispatch, useAppSelector } from '@/shared/hooks';
import { store } from '@/shared/state/store';
import {
  fetchSessions,
  fetchHistory,
  createDraftSession,
  collapseSession,
  closeSession,
  duplicateSession,
  expandSession,
  launchAndSendFirstMessage,
  generateTitle,
  resumeSession,
  setExpandedSessionIds,
  toggleExpandSession,
} from '@/shared/state/agentsSlice';
import type { AgentConfig } from '@/shared/state/agentsSlice';
import {
  fetchLayout,
  saveLayout,
  reconcileSessions,
  ensureAgentCard,
  tidyLayout,
  addViewCard,
  addBrowserCard,
  moveCards,
  resetLayout,
  setGlowingBrowserCards,
  removeViewCard,
  removeBrowserCard,
  pasteBrowserCard,
  placeCard,
  setCardPosition,
  removeCard,
  bringToFront,
  setGlowingAgentCard,
  clearGlowingAgentCard,
  clearPendingFocusBrowserId,
  addNote,
  removeNote,
  addPlansCard,
  removePlansCard,
  togglePlansCardCollapsed,
  addSwarmCard,
  setSwarmCardSwarmId,
  clearPendingFocusNoteId,
  DEFAULT_CARD_W,
  DEFAULT_CARD_H,
  EXPANDED_CARD_MIN_H,
  GRID_GAP,
} from '@/shared/state/dashboardLayoutSlice';
import type { SwarmMode } from '@/shared/state/dashboardLayoutSlice';
import type { UnifiedComposerSubmitPayload } from '@/shared/types/unifiedComposer';
import { fetchOutputs } from '@/shared/state/outputsSlice';
import type { Output } from '@/shared/state/outputsSlice';
import {
  chatExperimentalSwarm,
  clearExperimentalSwarm,
  createExperimentalSwarm,
  fetchExperimentalSwarm,
  updateOrchestrationNodePosition,
} from '@/shared/state/experimentalSwarmsSlice';
import { generateDashboardName, renameDashboard, updateDashboardThumbnail } from '@/shared/state/dashboardsSlice';
import { dashboardWs } from '@/shared/ws/WebSocketManager';
import { initBrowserCommandHandler } from '@/shared/browserCommandHandler';
import { clearPendingBrowserUrl, clearPendingFocusAgentId } from '@/shared/state/tempStateSlice';
import AgentCard from './AgentCard';
import DashboardViewCard from './DashboardViewCard';
import BrowserCard from './BrowserCard';
import NoteCard from './NoteCard';
import PersistentPlansCanvasCard from './PersistentPlansCanvasCard';
import ExperimentalSwarmCanvasCard from './ExperimentalSwarmCanvasCard';
import SwarmOrchestrationPreview from './SwarmOrchestrationPreview';
import type { OrchestrationCanvasState } from './SwarmOrchestrationPreview';
import CanvasControls from './CanvasControls';
import CardSearchPalette from './CardSearchPalette';
import DirectionHints from './DirectionHints';
import OnboardingWalkthrough from '@/app/components/OnboardingWalkthrough';
import DashboardToolbar from './DashboardToolbar';
import { captureDashboardThumbnail } from './captureDashboardThumbnail';
import { useCanvasControls } from './useCanvasControls';
import { useDashboardSelection } from './useDashboardSelection';
import type { CardType } from './useDashboardSelection';
import { useClaudeTokens } from '@/shared/styles/ThemeContext';
import type { ContextPath } from '@/app/components/DirectoryBrowser';
import { ElementSelectionProvider, useElementSelection } from '@/app/components/ElementSelectionContext';
import { useDomElementSelector } from '@/app/components/useDomElementSelector';
import SelectionOverlay from '@/app/components/SelectionOverlay';
import { setClipboardCards, getClipboardCards, type ClipboardCard } from '@/shared/dashboardClipboard';
import { API_BASE } from '@/shared/config';

const SELECT_ATTR = 'data-select-type';

const DashboardSelectionOverlay: React.FC = () => {
  const { overlay, dragRect, dragPreview } = useDomElementSelector();
  return <SelectionOverlay overlay={overlay} dragRect={dragRect} dragPreview={dragPreview} />;
};

function isCardTarget(target: EventTarget | null, boundary: EventTarget | null): boolean {
  let el = target as HTMLElement | null;
  while (el && el !== boundary) {
    if (el.hasAttribute(SELECT_ATTR)) return true;
    el = el.parentElement;
  }
  return false;
}

interface DashboardProps {
  dashboardId: string;
  isActive?: boolean;
}

const DashboardInner: React.FC<DashboardProps> = ({ dashboardId, isActive = true }) => {
  const c = useClaudeTokens();
  const dispatch = useAppDispatch();
  const elementSelectionCtx = useElementSelection();
  const isElementSelectMode = elementSelectionCtx?.selectMode ?? false;
  const dashboard = useAppSelector((state) =>
    dashboardId ? state.dashboards.items[dashboardId] : undefined,
  );
  const dashboardName = dashboard?.name;
  const sessions = useAppSelector((state) => state.agents.sessions);
  const expandedSessionIds = useAppSelector((state) => state.agents.expandedSessionIds);
  const cards = useAppSelector((state) => state.dashboardLayout.cards);
  const viewCards = useAppSelector((state) => state.dashboardLayout.viewCards);
  const browserCards = useAppSelector((state) => state.dashboardLayout.browserCards);
  const notes = useAppSelector((state) => state.dashboardLayout.notes);
  const plansCards = useAppSelector((state) => state.dashboardLayout.plansCards);
  const swarmCards = useAppSelector((state) => state.dashboardLayout.swarmCards);
  const viewportState = useAppSelector((state) => state.dashboardLayout.viewportState);
  const pendingFocusNoteId = useAppSelector((state) => state.dashboardLayout.pendingFocusNoteId);
  const layoutInitialized = useAppSelector((state) => state.dashboardLayout.initialized);
  const layoutDashboardId = useAppSelector((state) => state.dashboardLayout.currentDashboardId);
  const persistedExpandedSessionIds = useAppSelector((state) => state.dashboardLayout.persistedExpandedSessionIds);
  const zoomSensitivity = useAppSelector((state) => state.settings.data.zoom_sensitivity);
  const newAgentShortcut = useAppSelector((state) => state.settings.data.new_agent_shortcut);
  const browserHomepage = useAppSelector((state) => state.settings.data.browser_homepage);
  const autoRevealSubAgents = useAppSelector((state) => state.settings.data.auto_reveal_sub_agents);
  const outputs = useAppSelector((state) => state.outputs.items);
  const outputsLoaded = useAppSelector((state) => state.outputs.loaded);
  const glowingAgentCards = useAppSelector((state) => state.dashboardLayout.glowingAgentCards);
  const glowingBrowserCards = useAppSelector((state) => state.dashboardLayout.glowingBrowserCards);
  const activeExperimentalSwarm = useAppSelector((state) => state.experimentalSwarms.swarm);
  // sessions is the top-level dict; useMemo on its identity so sessionList
  // is stable when sessions hasn't actually changed (RTK only swaps the dict
  // ref when one of its values changes, so this is the right granularity).
  const sessionList = useMemo(() => Object.values(sessions), [sessions]);

  const linkedSwarmIds = useMemo(
    () => new Set(Object.values(swarmCards).filter((sc) => sc.swarm_id).map((sc) => sc.swarm_id as string)),
    [swarmCards],
  );

  const dashboardSwarmId = useMemo(
    () => swarmCards['swarm-main']?.swarm_id || null,
    [swarmCards],
  );

  const orchestrationCanvasState = useMemo((): OrchestrationCanvasState | null => {
    if (!activeExperimentalSwarm?.id || !linkedSwarmIds.has(activeExperimentalSwarm.id)) return null;
    const state = activeExperimentalSwarm.orchestration_canvas_state;
    if (!state || !Array.isArray(state.nodes) || state.nodes.length === 0) return null;
    return state as OrchestrationCanvasState;
  }, [activeExperimentalSwarm, linkedSwarmIds]);

  const orchestrationRects = useMemo(() => {
    const nodes = Array.isArray(orchestrationCanvasState?.nodes) ? orchestrationCanvasState.nodes : [];
    return nodes.map((node) => ({
      x: node.x,
      y: node.y,
      width: node.width || 180,
      height: node.height || 96,
      type: 'orchestration' as const,
    }));
  }, [orchestrationCanvasState]);

  const contentBounds = useMemo(() => {
    const allRects = [
      ...Object.values(cards).map((c) => ({ x: c.x, y: c.y, w: c.width, h: c.height })),
      ...Object.values(viewCards).map((c) => ({ x: c.x, y: c.y, w: c.width, h: c.height })),
      ...Object.values(browserCards).map((c) => ({ x: c.x, y: c.y, w: c.width, h: c.height })),
      ...Object.values(plansCards).filter((c) => !c.hidden).map((c) => ({ x: c.x, y: c.y, w: c.width, h: c.height })),
      ...Object.values(swarmCards).filter((c) => !c.hidden).map((c) => ({ x: c.x, y: c.y, w: c.width, h: c.height })),
      ...Object.values(notes).map((c) => ({ x: c.x, y: c.y, w: c.width, h: c.height })),
      ...orchestrationRects.map((r) => ({ x: r.x, y: r.y, w: r.width, h: r.height })),
    ];
    if (allRects.length === 0) return undefined;
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const r of allRects) {
      minX = Math.min(minX, r.x);
      minY = Math.min(minY, r.y);
      maxX = Math.max(maxX, r.x + r.w);
      maxY = Math.max(maxY, r.y + r.h);
    }
    return { minX, minY, maxX, maxY };
  }, [cards, viewCards, browserCards, plansCards, swarmCards, notes, orchestrationRects]);

  const canvas = useCanvasControls(zoomSensitivity, contentBounds, isActive);
  const selection = useDashboardSelection(
    { panX: canvas.panX, panY: canvas.panY, zoom: canvas.zoom, viewportRef: canvas.viewportRef },
    cards,
    viewCards,
    browserCards,
    notes,
    plansCards,
    swarmCards,
  );
  const toolbarRef = useRef<HTMLDivElement>(null);

  const [toolbarComposer, setToolbarComposer] = useState<'agent' | 'swarm' | null>(null);
  const [searchPaletteOpen, setSearchPaletteOpen] = useState(false);
  const [highlightedCardId, setHighlightedCardId] = useState<string | null>(null);
  const highlightTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [autoFocusSessionId, setAutoFocusSessionId] = useState<string | null>(null);
  const [pendingSelectSessionId, setPendingSelectSessionId] = useState<string | null>(null);
  const [focusedCardId, setFocusedCardId] = useState<string | null>(null);
  const [swarmDraftPrompts, setSwarmDraftPrompts] = useState<Record<string, string>>({});
  const [dashboardWorkspacePath, setDashboardWorkspacePath] = useState<string | null>(null);
  const [dashboardWorkspaceLoading, setDashboardWorkspaceLoading] = useState(false);
  const [canvasViewportSize, setCanvasViewportSize] = useState({ width: 0, height: 0 });
  const [showWalkthrough, setShowWalkthrough] = useState(() => {
    if (localStorage.getItem('openswarm_walkthrough_pending') === 'true') {
      return true;
    }
    return false;
  });
  const [newAgentBounce, setNewAgentBounce] = useState(false);

  const handleWalkthroughComplete = useCallback(() => {
    setShowWalkthrough(false);
    localStorage.removeItem('openswarm_walkthrough_pending');
    localStorage.setItem('openswarm_walkthrough_seen', 'true');
    setNewAgentBounce(true);
  }, []);

  const handleHighlightCard = useCallback((cardId: string) => {
    if (highlightTimerRef.current) clearTimeout(highlightTimerRef.current);
    setHighlightedCardId(cardId);
    highlightTimerRef.current = setTimeout(() => {
      setHighlightedCardId(null);
      highlightTimerRef.current = null;
    }, 2000);
  }, []);

  useEffect(() => {
    let cancelled = false;
    setDashboardWorkspacePath(null);
    if (!dashboardSwarmId) {
      setDashboardWorkspaceLoading(false);
      return;
    }

    setDashboardWorkspaceLoading(true);
    fetch(`${API_BASE}/swarms/${dashboardSwarmId}`)
      .then(async (res) => {
        if (!res.ok) throw new Error(`swarm fetch failed: ${res.status}`);
        return await res.json();
      })
      .then((swarm) => {
        if (!cancelled) {
          const workspacePath = typeof swarm?.workspace_path === 'string' && swarm.workspace_path.trim()
            ? swarm.workspace_path
            : null;
          setDashboardWorkspacePath(workspacePath);
        }
      })
      .catch(() => {
        if (!cancelled) setDashboardWorkspacePath(null);
      })
      .finally(() => {
        if (!cancelled) setDashboardWorkspaceLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [dashboardSwarmId]);

  useEffect(() => {
    if (autoFocusSessionId) {
      const timer = setTimeout(() => setAutoFocusSessionId(null), 1500);
      return () => clearTimeout(timer);
    }
  }, [autoFocusSessionId]);

  useEffect(() => {
    if (!pendingSelectSessionId) return;
    if (!cards[pendingSelectSessionId]) return;
    setPendingSelectSessionId(null);
    selection.selectCard(pendingSelectSessionId, 'agent', false);
  }, [pendingSelectSessionId, cards, selection]);

  const spawnOriginsRef = useRef<Record<string, { x: number; y: number; type?: 'branch' }>>({});
  const measuredHeightsRef = useRef<Record<string, number>>({});
  const [measuredHeightsTick, setMeasuredHeightsTick] = useState(0);
  const handleMeasuredHeight = useCallback((sessionId: string, height: number) => {
    if (measuredHeightsRef.current[sessionId] !== height) {
      measuredHeightsRef.current[sessionId] = height;
      setMeasuredHeightsTick((t) => t + 1);
    }
  }, []);
  const revealSpawnedRef = useRef(new Set<string>());
  useEffect(() => {
    revealSpawnedRef.current.forEach((id) => {
      if (!cards[id]) revealSpawnedRef.current.delete(id);
    });
  }, [cards]);
  const hasFittedRef = useRef(false);
  const restoredExpandedRef = useRef(false);
  const restoredViewportRef = useRef(false);
  const canvasStateRef = useRef({ panX: canvas.panX, panY: canvas.panY, zoom: canvas.zoom });
  canvasStateRef.current = { panX: canvas.panX, panY: canvas.panY, zoom: canvas.zoom };
  const orchestrationFocusReturnRef = useRef<{
    nodeId: string;
    panX: number;
    panY: number;
    zoom: number;
  } | null>(null);
  const cardFocusReturnRef = useRef<{
    id: string;
    type: string;
    panX: number;
    panY: number;
    zoom: number;
  } | null>(null);

  // ---- Edge panning during card drag ----
  const EDGE_ZONE = 60;
  const EDGE_MAX_SPEED = 8;
  const edgePanFrameRef = useRef<number | null>(null);
  const lastMousePosRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  // Track pan at drag start so cards can compensate for edge-pan offset
  const dragStartPanRef = useRef<{ panX: number; panY: number }>({ panX: 0, panY: 0 });

  const stopEdgePan = useCallback(() => {
    if (edgePanFrameRef.current) {
      cancelAnimationFrame(edgePanFrameRef.current);
      edgePanFrameRef.current = null;
    }
  }, []);

  const tickEdgePan = useCallback(() => {
    const vp = canvas.viewportRef.current;
    if (!vp) return;
    const rect = vp.getBoundingClientRect();
    const { x: mx, y: my } = lastMousePosRef.current;

    let dx = 0;
    let dy = 0;

    if (mx < rect.left + EDGE_ZONE) {
      dx = EDGE_MAX_SPEED * ((rect.left + EDGE_ZONE - mx) / EDGE_ZONE);
    } else if (mx > rect.right - EDGE_ZONE) {
      dx = -EDGE_MAX_SPEED * ((mx - (rect.right - EDGE_ZONE)) / EDGE_ZONE);
    }
    if (my < rect.top + EDGE_ZONE) {
      dy = EDGE_MAX_SPEED * ((rect.top + EDGE_ZONE - my) / EDGE_ZONE);
    } else if (my > rect.bottom - EDGE_ZONE) {
      dy = -EDGE_MAX_SPEED * ((my - (rect.bottom - EDGE_ZONE)) / EDGE_ZONE);
    }

    if (dx !== 0 || dy !== 0) {
      canvas.actions.setState((prev: { panX: number; panY: number; zoom: number }) => ({
        ...prev,
        panX: prev.panX + dx,
        panY: prev.panY + dy,
      }));
    }

    edgePanFrameRef.current = requestAnimationFrame(tickEdgePan);
  }, [canvas.viewportRef, canvas.actions]);

  // ---- Multi-drag coordination ----
  const [multiDragDelta, setMultiDragDelta] = useState<{ dx: number; dy: number } | null>(null);
  const [liveDragInfo, setLiveDragInfo] = useState<{ cardId: string; dx: number; dy: number } | null>(null);
  const activeDragCardRef = useRef<string | null>(null);
  const isMultiDragRef = useRef(false);

  const edgePanStartedRef = useRef(false);

  const handleCardDragStart = useCallback((id: string, _type: CardType) => {
    activeDragCardRef.current = id;
    edgePanStartedRef.current = false;
    if (selection.isSelected(id)) {
      isMultiDragRef.current = true;
    } else {
      selection.deselectAll();
      isMultiDragRef.current = false;
    }
  }, [selection]);

  const handleCardDragMove = useCallback((dx: number, dy: number, mouseX?: number, mouseY?: number) => {
    if (mouseX !== undefined && mouseY !== undefined) {
      lastMousePosRef.current = { x: mouseX, y: mouseY };
    }
    // Start edge panning only once actual dragging begins
    if (!edgePanStartedRef.current) {
      edgePanStartedRef.current = true;
      edgePanFrameRef.current = requestAnimationFrame(tickEdgePan);
    }
    if (isMultiDragRef.current) {
      setMultiDragDelta({ dx, dy });
    }
    if (activeDragCardRef.current) {
      setLiveDragInfo({ cardId: activeDragCardRef.current, dx, dy });
    }
  }, [tickEdgePan]);

  const handleCardDragEnd = useCallback((dx: number, dy: number, didDrag: boolean) => {
    if (didDrag) report('dashboard', 'card_dragged');
    stopEdgePan();
    if (isMultiDragRef.current && didDrag) {
      const items = selection.selectedArray()
        .filter((s) => s.id !== activeDragCardRef.current);
      if (items.length > 0) {
        dispatch(moveCards({ items, dx, dy }));
      }
    }
    activeDragCardRef.current = null;
    isMultiDragRef.current = false;
    setMultiDragDelta(null);
    setLiveDragInfo(null);
  }, [selection, dispatch, stopEdgePan]);

  // Helper: get a card's rect from Redux state (uses collapsed height for zoom calculation)
  const getCardRect = useCallback((id: string, type: CardType) => {
    const layoutState = store.getState().dashboardLayout;
    if (type === 'agent') {
      const card = layoutState.cards[id];
      if (!card) return undefined;
      return { x: card.x, y: card.y, width: card.width, height: card.height };
    } else if (type === 'view') {
      const vc = layoutState.viewCards[id];
      if (!vc) return undefined;
      return { x: vc.x, y: vc.y, width: vc.width, height: vc.height };
    } else if (type === 'browser') {
      const bc = layoutState.browserCards[id];
      if (!bc) return undefined;
      return { x: bc.x, y: bc.y, width: bc.width, height: bc.height };
    } else if (type === 'note') {
      const n = layoutState.notes[id];
      if (!n) return undefined;
      return { x: n.x, y: n.y, width: n.width, height: n.height };
    } else if (type === 'plans') {
      const pc = layoutState.plansCards[id];
      if (!pc || pc.hidden) return undefined;
      return { x: pc.x, y: pc.y, width: pc.width, height: pc.height };
    } else if (type === 'swarm') {
      const sc = layoutState.swarmCards[id];
      if (!sc) return undefined;
      return { x: sc.x, y: sc.y, width: sc.width, height: sc.height };
    }
    return undefined;
  }, []);

  // Delay single-click collapse so double-click can override
  const clickTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const cardClickFocusTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Cancela movimientos de foco anteriores entre Plans/Agents.
  const navigationRequestRef = useRef(0);

  const handleCardSelect = useCallback((id: string, type: CardType, shiftKey: boolean) => {
    report('dashboard', 'card_clicked', { card_type: type, shift: shiftKey });
    if (shiftKey) {
      selection.selectCard(id, type, true);
      return;
    }

    selection.selectCard(id, type, false);
    dispatch(bringToFront({ id, type: type as any }));

    setFocusedCardId(id);

    if (cardClickFocusTimerRef.current) {
      clearTimeout(cardClickFocusTimerRef.current);
      cardClickFocusTimerRef.current = null;
    }

    if (type === 'agent') {
      if (clickTimerRef.current) {
        clearTimeout(clickTimerRef.current);
        clickTimerRef.current = null;
      }
      const alreadyExpanded = expandedSessionIds.includes(id);
      clickTimerRef.current = setTimeout(() => {
        clickTimerRef.current = null;
        if (alreadyExpanded) {
          dispatch(collapseSession(id));
        } else {
          dispatch(expandSession(id));
        }
      }, 340);
    }
  }, [selection, dispatch, expandedSessionIds]);

  const handleBringToFront = useCallback((id: string, type: CardType) => {
    dispatch(bringToFront({ id, type: type as any }));
  }, [dispatch]);

  // ---- Viewport event handlers (compose pan + marquee) ----
  const handleViewportMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button === 1) {
      canvas.handlers.onMouseDown(e);
      return;
    }

    if (e.button === 2) {
      e.preventDefault();
      canvas.handlers.onMouseDown(e);
      return;
    }

    if (e.button !== 0) return;
    if (isCardTarget(e.target, e.currentTarget)) return;

    // Canvas click — drop any lingering input focus so arrow-key nav
    // works immediately without the user having to press Escape first.
    const active = document.activeElement as HTMLElement | null;
    const activeTag = active?.tagName;
    if (activeTag === 'INPUT' || activeTag === 'TEXTAREA' || (active as any)?.isContentEditable) {
      active?.blur?.();
    }

    if (isElementSelectMode) {
      if (e.metaKey || e.ctrlKey) {
        canvas.handlers.onMouseDown(e);
      }
      return;
    }

    if (e.metaKey || e.ctrlKey || canvas.spaceHeld) {
      selection.deselectAll();
      canvas.handlers.onMouseDown(e);
    } else {
      selection.handleCanvasMouseDown(e.nativeEvent);
    }
  }, [canvas.handlers, canvas.spaceHeld, selection, isElementSelectMode]);

  const handleViewportMouseMove = useCallback((e: React.MouseEvent) => {
    canvas.handlers.onMouseMove(e);
    selection.handleCanvasMouseMove(e.nativeEvent);
  }, [canvas.handlers, selection]);

  const handleViewportMouseUp = useCallback((e: React.MouseEvent) => {
    canvas.handlers.onMouseUp();
    selection.handleCanvasMouseUp(e.nativeEvent);
  }, [canvas.handlers, selection]);

  // Double-click empty canvas → fit all cards
  const handleViewportDoubleClick = useCallback((e: React.MouseEvent) => {
    if (e.button !== 0) return;
    if (isCardTarget(e.target, e.currentTarget)) return;
    report('dashboard', 'canvas_double_clicked');
    canvas.actions.fitToView();
  }, [canvas.actions]);

  // Double-click a card → focus with fixed zoom; second double-click returns to previous view.
  const handleCardDoubleClick = useCallback((id: string, type: CardType) => {
    report('dashboard', 'card_double_clicked', { card_type: type });
    if (clickTimerRef.current) {
      clearTimeout(clickTimerRef.current);
      clickTimerRef.current = null;
    }
    if (cardClickFocusTimerRef.current) {
      clearTimeout(cardClickFocusTimerRef.current);
      cardClickFocusTimerRef.current = null;
    }

    const previousFocus = cardFocusReturnRef.current;
    if (previousFocus?.id === id && previousFocus?.type === type) {
      const returnView = {
        panX: previousFocus.panX,
        panY: previousFocus.panY,
        zoom: previousFocus.zoom,
      };
      cardFocusReturnRef.current = null;
      canvas.actions.setState(returnView);
      setTimeout(() => {
        canvas.actions.setState(returnView);
      }, 0);
      return;
    }

    const rect = getCardRect(id, type);
    const viewport = canvas.viewportRef.current;
    if (!rect || !viewport) return;

    const currentView = canvasStateRef.current;
    cardFocusReturnRef.current = {
      id,
      type,
      panX: currentView.panX,
      panY: currentView.panY,
      zoom: currentView.zoom,
    };

    const targetZoom =
      type === 'plans'
        ? 1.2
        : type === 'agent' || type === 'swarm'
          ? 1.1
          : 1.15;

    dispatch(bringToFront({ id, type: type as any }));
    setFocusedCardId(id);

    const targetPanX = (viewport.clientWidth - rect.width * targetZoom) / 2 - rect.x * targetZoom;
    const targetPanY = type === 'agent'
      ? 72 - rect.y * targetZoom
      : (viewport.clientHeight - rect.height * targetZoom) / 2 - rect.y * targetZoom;

    canvas.actions.setState({ panX: targetPanX, panY: targetPanY, zoom: targetZoom });
    setTimeout(() => (document.activeElement as HTMLElement)?.blur?.(), 150);
  }, [getCardRect, canvas.actions, canvas.viewportRef, dispatch]);

  // Track dashboard engagement time
  useEffect(() => {
    if (!dashboardId) return;
    const startTime = Date.now();
    report('dashboard', 'opened', { dashboard_id: dashboardId });
    return () => {
      report('dashboard', 'closed', {
        dashboard_id: dashboardId,
        time_spent_seconds: Math.round((Date.now() - startTime) / 1000),
      });
    };
  }, [dashboardId]);

  useEffect(() => {
    if (!dashboardId) return;
    hasFittedRef.current = false;
    restoredExpandedRef.current = false;
    restoredViewportRef.current = false;
    dispatch(resetLayout());
    dispatch(clearExperimentalSwarm());
    dispatch(fetchSessions({ dashboardId }));
    dispatch(fetchHistory({ dashboardId }));
    dispatch(fetchLayout(dashboardId));
    dispatch(fetchOutputs());
    dashboardWs.connect();
    const cleanupBrowserHandler = initBrowserCommandHandler();

    // Pre-warm Anthropic's prompt cache for sessions on this dashboard
    // ~250ms after mount (debounced; AbortController cancels on
    // dashboard switch). Fires a max_tokens=1 ping per session so the
    // user's first real message hits a warm cache instead of paying
    // cold-start TTFT. Cheap (~$0.0001/session) and non-blocking. Skips
    // for non-Anthropic sessions server-side.
    const warmAbort = new AbortController();
    const warmTimer = setTimeout(async () => {
      try {
        const sessionsState = store.getState().agents.sessions;
        const dashSessions = Object.values(sessionsState).filter(
          (s) => s.dashboard_id === dashboardId &&
                 s.status !== 'draft' &&
                 s.mode !== 'browser-agent' &&
                 s.mode !== 'sub-agent' &&
                 s.mode !== 'invoked-agent',
        );
        for (const s of dashSessions) {
          if (warmAbort.signal.aborted) break;
          // Fire-and-forget — the endpoint always 200s and the side
          // effect is invisible cache population.
          fetch(`${API_BASE}/agents/sessions/${s.id}/warm-cache`, {
            method: 'POST',
            signal: warmAbort.signal,
          }).catch(() => {});
        }
      } catch {
        /* best-effort */
      }
    }, 250);

    return () => {
      clearTimeout(warmTimer);
      warmAbort.abort();
      cleanupBrowserHandler();
      dashboardWs.disconnect();
    };
  }, [dispatch, dashboardId]);

  const pendingBrowserUrl = useAppSelector((state) => state.tempState.pendingBrowserUrl);
  const pendingFocusAgentId = useAppSelector((state) => state.tempState.pendingFocusAgentId);
  const pendingFocusBrowserId = useAppSelector((state) => state.dashboardLayout.pendingFocusBrowserId);

  useEffect(() => {
    if (!dashboardId) return;
    (window as any).__openswarm_last_dashboard_id = dashboardId;
  }, [dashboardId]);

  useEffect(() => {
    if (!pendingBrowserUrl || !layoutInitialized) return;
    dispatch(addBrowserCard({ url: pendingBrowserUrl, expandedSessionIds }));
    dispatch(clearPendingBrowserUrl());
  }, [pendingBrowserUrl, layoutInitialized, dispatch, expandedSessionIds]);

  // Capture a thumbnail screenshot of the dashboard.
  // Uses Electron's native capturePage for pixel-perfect results.
  // Captures current viewport as-is (no DOM mutation) to avoid visual flashes.
  // Re-captures when layout is saved (piggybacking on the save debounce).
  const pendingThumbnailRef = useRef<string | null>(null);
  const captureTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const captureNow = useCallback(() => {
    const viewportEl = canvas.viewportRef.current;
    const contentEl = canvas.contentRef.current;
    if (!viewportEl || !contentEl) return;
    const layoutState = store.getState().dashboardLayout;
    const allCards = {
      cards: layoutState.cards,
      viewCards: layoutState.viewCards,
      browserCards: layoutState.browserCards,
    };
    const hasCards = Object.keys(allCards.cards).length > 0
      || Object.keys(allCards.viewCards).length > 0
      || Object.keys(allCards.browserCards).length > 0;
    if (!hasCards) {
      // Empty dashboard — queue a thumbnail clear (sent on exit alongside
      // the existing capture-update path). Backend treats '' as "set to
      // empty"; null in PUT body means "don't update".
      pendingThumbnailRef.current = '';
      return;
    }
    captureDashboardThumbnail(viewportEl, contentEl, allCards)
      .then((thumbnail) => { if (thumbnail) pendingThumbnailRef.current = thumbnail; })
      .catch(() => {});
  }, [canvas.viewportRef, canvas.contentRef]);

  useEffect(() => {
    if (!isActive) return;  // Skip thumbnail capture when dashboard is hidden
    if (!dashboardId || !layoutInitialized) return;
    if (captureTimerRef.current) clearTimeout(captureTimerRef.current);
    captureTimerRef.current = setTimeout(captureNow, 2000);
    return () => { if (captureTimerRef.current) clearTimeout(captureTimerRef.current); };
  }, [isActive, dashboardId, layoutInitialized, captureNow]);

  // On exit, save the captured thumbnail to the backend
  useEffect(() => {
    if (!dashboardId) return;
    const exitingId = dashboardId;
    return () => {
      const thumbnail = pendingThumbnailRef.current;
      // null = no pending change; '' = pending clear; other = pending update.
      if (thumbnail !== null) {
        store.dispatch(updateDashboardThumbnail({ id: exitingId, thumbnail }));
        pendingThumbnailRef.current = null;
      }
    };
  }, [dashboardId]);

  useEffect(() => {
    if (!isActive) return;
    if (!layoutInitialized || restoredViewportRef.current) return;
    restoredViewportRef.current = true;
    if (!viewportState) return;
    hasFittedRef.current = true;
    canvas.actions.setState({
      panX: viewportState.panX,
      panY: viewportState.panY,
      zoom: viewportState.zoom,
    });
  }, [isActive, layoutInitialized, viewportState, canvas.actions]);

  useEffect(() => {
    if (!isActive) return;  // Don't auto-fit while dashboard is hidden
    if (!layoutInitialized || hasFittedRef.current) return;
    if (pendingFocusAgentId) return;
    hasFittedRef.current = true;
    const timer = setTimeout(() => canvas.actions.fitToView(), 150);
    return () => clearTimeout(timer);
  }, [isActive, layoutInitialized, canvas.actions, pendingFocusAgentId]);

  const focusAgentCardWithRetry = useCallback((agentId: string, attempts = 10) => {
    const card = store.getState().dashboardLayout.cards[agentId];
    if (card) {
      hasFittedRef.current = true;
      canvas.actions.fitToCards([{ x: card.x, y: card.y, width: card.width, height: card.height }], 1.15, true);
      handleHighlightCard(agentId);
      dispatch(bringToFront({ id: agentId, type: 'agent' }));
      selection.selectCard(agentId, 'agent', false);
      return;
    }
    if (attempts > 0) {
      window.setTimeout(() => focusAgentCardWithRetry(agentId, attempts - 1), 120);
    }
  }, [canvas.actions, dispatch, handleHighlightCard, selection]);

  useEffect(() => {
    if (!isActive) return;  // Defer focus animation until dashboard is visible
    if (!pendingFocusAgentId || !layoutInitialized) return;
    const agentId = pendingFocusAgentId;
    dispatch(clearPendingFocusAgentId());
    window.setTimeout(() => focusAgentCardWithRetry(agentId), 120);
  }, [isActive, pendingFocusAgentId, layoutInitialized, dispatch, focusAgentCardWithRetry]);

  // Auto-focus a newly created browser card. The reducer that handles
  // addBrowserCard sets pendingFocusBrowserId to the new card's id; this
  // effect picks it up, pans/zooms the canvas to center on it, briefly
  // highlights it, then clears the signal. Mirrors the pendingFocusAgentId
  // pattern above so link clicks (intercepted in AppShell) get the same
  // auto-focus behavior as the "+ Browser" toolbar button.
  //
  // Uses zoom=0.8 (the same value handleCardClick uses for browser cards
  // at line ~344) instead of letting fitToCards auto-derive a zoom from
  // padding. Browser cards are large (1280x800), so the auto-derived zoom
  // would land around ~58% which feels too far back; 0.8 matches the
  // "click on a browser to focus" experience the user expects.
  useEffect(() => {
    if (!isActive) return;
    if (!pendingFocusBrowserId || !layoutInitialized) return;
    const browserId = pendingFocusBrowserId;
    dispatch(clearPendingFocusBrowserId());
    hasFittedRef.current = true;
    setTimeout(() => {
      const card = store.getState().dashboardLayout.browserCards[browserId];
      if (card) {
        canvas.actions.fitToCards(
          [{ x: card.x, y: card.y, width: card.width, height: card.height }],
          1.15,
          true,
          0.8,
        );
        handleHighlightCard(browserId);
      }
    }, 200);
  }, [isActive, pendingFocusBrowserId, layoutInitialized, dispatch, canvas.actions, handleHighlightCard]);

  useEffect(() => {
    if (!layoutInitialized || restoredExpandedRef.current) return;
    restoredExpandedRef.current = true;
    dispatch(setExpandedSessionIds(persistedExpandedSessionIds));
  }, [layoutInitialized, persistedExpandedSessionIds, dispatch]);

  const prevSessionIdsRef = useRef<string>('');

  useEffect(() => {
    if (!layoutInitialized) return;
    const dashboardSessionIds = Object.values(sessions)
      .filter((s) => s.dashboard_id === dashboardId && s.mode !== 'browser-agent' && s.mode !== 'invoked-agent' && s.mode !== 'sub-agent')
      .map((s) => s.id);
    const liveIds = dashboardSessionIds.sort().join(',');
    if (liveIds === prevSessionIdsRef.current) return;
    prevSessionIdsRef.current = liveIds;
    dispatch(reconcileSessions({ sessionIds: dashboardSessionIds, expandedSessionIds }));
  }, [sessions, layoutInitialized, dispatch, dashboardId, expandedSessionIds]);

  // Prune orphan view cards whose underlying output was deleted (e.g. via
  // the Views page). Without this, the layout entry persists in the
  // minimap and contentBounds even though DashboardViewCard renders
  // nothing. Gated on outputsLoaded so we don't wipe valid cards during
  // the brief window between fetchLayout returning and outputs finishing.
  useEffect(() => {
    if (!layoutInitialized || !outputsLoaded) return;
    for (const [viewCardId, viewCard] of Object.entries(viewCards)) {
      if (!outputs[viewCard.output_id]) dispatch(removeViewCard(viewCardId));
    }
  }, [layoutInitialized, outputsLoaded, viewCards, outputs, dispatch]);

  // ---- Auto-reveal / collapse / unreveal sub-agent cards ----
  const autoRevealedRef = useRef(new Set<string>());
  const prevSubStatusRef = useRef<Record<string, string>>({});
  const prevParentStatusRef = useRef<Record<string, string>>({});

  useEffect(() => {
    if (!isActive) return;  // Heavy logic — pause when dashboard is hidden
    if (!layoutInitialized || !autoRevealSubAgents) return;

    const subSessions = Object.values(sessions).filter(
      (s) => (s.mode === 'sub-agent' || s.mode === 'invoked-agent') && s.parent_session_id,
    );

    // 1) Auto-reveal newly spawned sub-agents (skip already-terminal ones on load)
    for (const sub of subSessions) {
      if (autoRevealedRef.current.has(sub.id)) continue;
      if (cards[sub.id]) {
        autoRevealedRef.current.add(sub.id);
        continue;
      }
      const parentCard = cards[sub.parent_session_id!];
      if (!parentCard) continue;

      const isTerminal = sub.status === 'completed' || sub.status === 'error' || sub.status === 'stopped';
      const parentSession = sessions[sub.parent_session_id!];
      const parentTerminal = parentSession &&
        (parentSession.status === 'completed' || parentSession.status === 'error' || parentSession.status === 'stopped');
      if (isTerminal && parentTerminal) {
        autoRevealedRef.current.add(sub.id);
        continue;
      }

      autoRevealedRef.current.add(sub.id);

      const targetX = parentCard.x + parentCard.width + GRID_GAP * 12;
      let targetY = parentCard.y;
      const columnCards = Object.values(cards).filter(
        (c) => Math.abs(c.x - targetX) < 50 && c.session_id !== sub.id,
      );
      if (columnCards.length > 0) {
        const lowestBottom = Math.max(
          ...columnCards.map((c) => c.y + Math.max(EXPANDED_CARD_MIN_H, c.height)),
        );
        targetY = lowestBottom + GRID_GAP;
      }

      dispatch(placeCard({ sessionId: sub.id, x: targetX, y: targetY, width: DEFAULT_CARD_W, height: DEFAULT_CARD_H }));
      dispatch(expandSession(sub.id));
      const label = sub.mode === 'sub-agent' ? 'Create Agent' : 'Invoke Agent';
      dispatch(setGlowingAgentCard({ sessionId: sub.id, sourceId: sub.parent_session_id!, label }));

      if (sub.status === 'completed' || sub.status === 'error' || sub.status === 'stopped') {
        const subId = sub.id;
        setTimeout(() => dispatch(collapseSession(subId)), 2000);
      }
    }

    // 2) Auto-collapse sub-agents when they complete
    const TERMINAL = new Set(['completed', 'error', 'stopped']);
    for (const sub of subSessions) {
      const prev = prevSubStatusRef.current[sub.id];
      if (prev !== sub.status && TERMINAL.has(sub.status) && cards[sub.id]) {
        dispatch(collapseSession(sub.id));
      }
    }
    const newSubStatuses: Record<string, string> = {};
    for (const sub of subSessions) { newSubStatuses[sub.id] = sub.status; }
    prevSubStatusRef.current = newSubStatuses;

    // 3) Unreveal all sub-agent cards when parent finishes output
    const parentIds = new Set(subSessions.map((s) => s.parent_session_id!));
    for (const pid of parentIds) {
      const parent = sessions[pid];
      if (!parent) continue;
      const prev = prevParentStatusRef.current[pid];
      if (prev !== parent.status && TERMINAL.has(parent.status)) {
        const children = subSessions.filter((s) => s.parent_session_id === pid);
        for (const child of children) {
          if (!cards[child.id]) continue;
          dispatch(collapseSession(child.id));
          dispatch(removeCard(child.id));
          setTimeout(() => {
            dispatch(clearGlowingAgentCard(child.id));
          }, 500);
        }
      }
    }
    const newParentStatuses: Record<string, string> = {};
    for (const pid of parentIds) {
      const parent = sessions[pid];
      if (parent) newParentStatuses[pid] = parent.status;
    }
    prevParentStatusRef.current = newParentStatuses;
  }, [isActive, sessions, cards, layoutInitialized, autoRevealSubAgents, dispatch]);

  const skipInitialSave = useRef(true);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingSaveRef = useRef<Parameters<typeof saveLayout>[0] | null>(null);
  const latestSavePayloadRef = useRef<Parameters<typeof saveLayout>[0] | null>(null);

  const flushLatestLayoutSave = useCallback(() => {
    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current);
      saveTimerRef.current = null;
    }

    const payload = pendingSaveRef.current ?? latestSavePayloadRef.current;
    if (payload) {
      dispatch(saveLayout({
        ...payload,
        viewportState: canvasStateRef.current,
      }));
    }

    pendingSaveRef.current = null;
  }, [dispatch]);

  useEffect(() => {
    if (!isActive) return;  // Don't persist layout while dashboard is hidden — save buffers in pendingSaveRef and flushes on resume
    if (!layoutInitialized || !dashboardId || layoutDashboardId !== dashboardId) return;
    const payload = {
      dashboardId,
      cards,
      viewCards,
      browserCards,
      plansCards,
      swarmCards,
      notes,
      expandedSessionIds,
      viewportState: { panX: canvas.panX, panY: canvas.panY, zoom: canvas.zoom },
    };
    latestSavePayloadRef.current = payload;
    if (skipInitialSave.current) {
      skipInitialSave.current = false;
      return;
    }
    pendingSaveRef.current = payload;
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => {
      dispatch(saveLayout(payload));
      pendingSaveRef.current = null;
      saveTimerRef.current = null;
      captureNow();
    }, 500);
  }, [isActive, cards, viewCards, browserCards, plansCards, swarmCards, notes, expandedSessionIds, canvas.panX, canvas.panY, canvas.zoom, layoutInitialized, layoutDashboardId, dashboardId, dispatch, captureNow]);

  useEffect(() => {
    if (!isActive) {
      flushLatestLayoutSave();
    }
  }, [isActive, flushLatestLayoutSave]);

  useEffect(() => () => {
    flushLatestLayoutSave();
  }, [flushLatestLayoutSave]);

  useEffect(() => {
    const parts = newAgentShortcut.toLowerCase().split('+');
    const key = parts[parts.length - 1];
    const needsMeta = parts.includes('meta');
    const needsCtrl = parts.includes('ctrl');
    const needsShift = parts.includes('shift');
    const needsAlt = parts.includes('alt');

    const handleShortcut = (e: KeyboardEvent) => {
      if (!isActive) return;  // Don't fire shortcuts when dashboard is hidden
      if (e.key.toLowerCase() !== key) return;
      if (needsMeta !== e.metaKey) return;
      if (needsCtrl !== e.ctrlKey) return;
      if (needsShift !== e.shiftKey) return;
      if (needsAlt !== e.altKey) return;
      e.preventDefault();
      setToolbarComposer('agent');
    };
    window.addEventListener('keydown', handleShortcut);
    return () => window.removeEventListener('keydown', handleShortcut);
  }, [newAgentShortcut]);

  useEffect(() => {
    const handleEnter = (e: KeyboardEvent) => {
      if (!isActive) return;  // Don't fire shortcuts when dashboard is hidden
      if (e.key !== 'Enter') return;
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || (e.target as HTMLElement)?.isContentEditable) return;
      if (selection.selectedIds.size !== 1) return;
      const [id, type] = selection.selectedIds.entries().next().value!;
      if (type !== 'agent') return;
      e.preventDefault();
      dispatch(toggleExpandSession(id));
    };
    window.addEventListener('keydown', handleEnter);
    return () => window.removeEventListener('keydown', handleEnter);
  }, [selection.selectedIds, dispatch]);

  useEffect(() => {
    const handleDelete = (e: KeyboardEvent) => {
      if (!isActive) return;  // Don't fire shortcuts when dashboard is hidden
      if (e.key !== 'Backspace' && e.key !== 'Delete') return;
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || (e.target as HTMLElement)?.isContentEditable) return;
      if (selection.selectedIds.size === 0) return;
      e.preventDefault();
      for (const [id, type] of selection.selectedIds) {
        if (type === 'agent') {
          dispatch(closeSession({ sessionId: id }));
        } else if (type === 'view') {
          dispatch(removeViewCard(id));
        } else if (type === 'browser') {
          dispatch(removeBrowserCard(id));
        } else if (type === 'note') {
          dispatch(removeNote(id));
        }
      }
      selection.deselectAll();
    };
    window.addEventListener('keydown', handleDelete);
    return () => window.removeEventListener('keydown', handleDelete);
  }, [selection, dispatch]);

  // Cmd+F to open card search palette
  useEffect(() => {
    const handleSearch = (e: KeyboardEvent) => {
      if (!isActive) return;  // Don't fire shortcuts when dashboard is hidden
      if (!(e.metaKey || e.ctrlKey) || e.key.toLowerCase() !== 'f') return;
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || (e.target as HTMLElement)?.isContentEditable) return;
      e.preventDefault();
      setSearchPaletteOpen(true);
      report('dashboard', 'search_opened');
    };
    window.addEventListener('keydown', handleSearch);
    return () => window.removeEventListener('keydown', handleSearch);
  }, []);

  useEffect(() => {
    const handleCopy = (e: KeyboardEvent) => {
      if (!isActive) return;  // Don't fire shortcuts when dashboard is hidden
      if (!(e.metaKey || e.ctrlKey) || e.key.toLowerCase() !== 'c') return;
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || (e.target as HTMLElement)?.isContentEditable) return;
      if (selection.selectedIds.size === 0) return;

      e.preventDefault();
      const copied: ClipboardCard[] = [];
      const names: string[] = [];
      for (const [id, type] of selection.selectedIds) {
        if (type === 'agent') {
          const session = sessions[id];
          const card = cards[id];
          if (!session || !card) continue;
          copied.push({
            type, id, name: session.name || id,
            meta: { name: session.name, status: session.status, model: session.model, mode: session.mode },
            x: card.x, y: card.y, width: card.width, height: card.height,
            expanded: expandedSessionIds.includes(id),
          });
          names.push(session.name || id);
        } else if (type === 'view') {
          const output = outputs[id];
          const vc = viewCards[id];
          if (!output || !vc) continue;
          copied.push({
            type, id, name: output.name,
            meta: { name: output.name, description: output.description },
            x: vc.x, y: vc.y, width: vc.width, height: vc.height,
          });
          names.push(output.name);
        } else if (type === 'browser') {
          const bc = browserCards[id];
          if (!bc) continue;
          const activeTab = bc.tabs.find((t) => t.id === bc.activeTabId);
          const title = activeTab?.title || 'Browser';
          copied.push({
            type, id, name: title,
            meta: { name: title, url: activeTab?.url || bc.url, tabs: bc.tabs },
            x: bc.x, y: bc.y, width: bc.width, height: bc.height,
          });
          names.push(title);
        }
      }
      setClipboardCards(copied);
      navigator.clipboard.writeText(names.join(', ')).catch(() => {});
    };
    window.addEventListener('keydown', handleCopy);
    return () => window.removeEventListener('keydown', handleCopy);
  }, [selection.selectedIds, sessions, cards, viewCards, browserCards, outputs, expandedSessionIds]);

  useEffect(() => {
    const PASTE_OFFSET = 40;
    const handlePaste = async (e: KeyboardEvent) => {
      if (!isActive) return;  // Don't fire shortcuts when dashboard is hidden
      if (!(e.metaKey || e.ctrlKey) || e.key.toLowerCase() !== 'v') return;
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || (e.target as HTMLElement)?.isContentEditable) return;

      const copied = getClipboardCards();
      if (copied.length === 0) return;
      e.preventDefault();

      selection.deselectAll();
      const newSelection = new Map<string, CardType>();

      for (const card of copied) {
        const px = card.x + PASTE_OFFSET;
        const py = card.y - PASTE_OFFSET;

        if (card.type === 'agent') {
          const action = await dispatch(duplicateSession({ sessionId: card.id, dashboardId }));
          if (duplicateSession.fulfilled.match(action)) {
            const newId = action.payload.id;
            dispatch(placeCard({ sessionId: newId, x: px, y: py, width: card.width, height: card.height }));
            if (card.expanded) {
              dispatch(expandSession(newId));
            }
            newSelection.set(newId, 'agent');
          }
        } else if (card.type === 'view') {
          dispatch(addViewCard({ outputId: card.id, expandedSessionIds, x: px, y: py, width: card.width, height: card.height }));
          newSelection.set(card.id, 'view');
        } else if (card.type === 'browser') {
          const browserId = `browser-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;
          dispatch(pasteBrowserCard({
            id: browserId, tabs: card.meta.tabs || [], url: card.meta.url || '',
            x: px, y: py, width: card.width, height: card.height,
          }));
          newSelection.set(browserId, 'browser');
        }
      }

      if (newSelection.size > 0) {
        for (const [id, type] of newSelection) {
          selection.selectCard(id, type, true);
        }
      }
    };
    window.addEventListener('keydown', handlePaste);
    return () => window.removeEventListener('keydown', handlePaste);
  }, [dispatch, dashboardId, expandedSessionIds, selection]);

  // ---- Arrow key card navigation (when zoomed in on a card) ----
  const findNearestCard = useCallback((
    currentId: string,
    direction: 'left' | 'right' | 'up' | 'down',
  ): { id: string; type: CardType } | null => {
    const allCardEntries: Array<{ id: string; type: CardType; cx: number; cy: number }> = [];
    for (const card of Object.values(cards)) {
      allCardEntries.push({ id: card.session_id, type: 'agent', cx: card.x + card.width / 2, cy: card.y + card.height / 2 });
    }
    for (const [viewCardId, vc] of Object.entries(viewCards)) {
      allCardEntries.push({ id: vc.view_card_id || viewCardId, type: 'view', cx: vc.x + vc.width / 2, cy: vc.y + vc.height / 2 });
    }
    for (const bc of Object.values(browserCards)) {
      allCardEntries.push({ id: bc.browser_id, type: 'browser', cx: bc.x + bc.width / 2, cy: bc.y + bc.height / 2 });
    }

    const current = allCardEntries.find((c) => c.id === currentId);
    if (!current) return null;

    let best: typeof allCardEntries[0] | null = null;
    let bestScore = Infinity;

    for (const card of allCardEntries) {
      if (card.id === currentId) continue;
      const dx = card.cx - current.cx;
      const dy = card.cy - current.cy;

      // Filter to the correct half-plane
      let inDirection = false;
      let primary = 0;
      let secondary = 0;
      switch (direction) {
        case 'right': inDirection = dx > 20; primary = dx; secondary = Math.abs(dy); break;
        case 'left':  inDirection = dx < -20; primary = -dx; secondary = Math.abs(dy); break;
        case 'down':  inDirection = dy > 20; primary = dy; secondary = Math.abs(dx); break;
        case 'up':    inDirection = dy < -20; primary = -dy; secondary = Math.abs(dx); break;
      }
      if (!inDirection) continue;

      const score = primary + secondary * 0.3;
      if (score < bestScore) {
        bestScore = score;
        best = card;
      }
    }

    return best ? { id: best.id, type: best.type } : null;
  }, [cards, viewCards, browserCards]);

  // Compute which directions have neighbors from the focused card
  const neighborDirections = useMemo(() => {
    // Lowered the zoom floor from 0.9 to 0.4 so arrow nav still works
    // when users zoom out to see the whole canvas. Below 0.4 the cards
    // are too small to be a useful navigation target.
    if (!focusedCardId || canvas.zoom < 0.4) return { left: false, right: false, up: false, down: false };
    return {
      left: !!findNearestCard(focusedCardId, 'left'),
      right: !!findNearestCard(focusedCardId, 'right'),
      up: !!findNearestCard(focusedCardId, 'up'),
      down: !!findNearestCard(focusedCardId, 'down'),
    };
  }, [focusedCardId, canvas.zoom, findNearestCard]);

  // Shake animation state: direction + timer
  const [shakeDirection, setShakeDirection] = useState<'left' | 'right' | 'up' | 'down' | null>(null);
  const shakeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Use refs for values read inside the keydown handler to avoid stale closures
  const focusedCardIdRef = useRef(focusedCardId);
  focusedCardIdRef.current = focusedCardId;
  const canvasZoomRef = useRef(canvas.zoom);
  canvasZoomRef.current = canvas.zoom;

  useEffect(() => {
    // Helper: is the currently-focused element a text-entry field the
    // user is actively editing? We only want to suppress dashboard
    // navigation when the user is genuinely typing, not just because an
    // input somewhere happens to have focus from a click long ago.
    const isActivelyEditing = (target: EventTarget | null): boolean => {
      const el = (target as HTMLElement) || (document.activeElement as HTMLElement | null);
      if (!el) return false;
      const tag = el.tagName;
      const editable = (el as any).isContentEditable;
      if (tag !== 'INPUT' && tag !== 'TEXTAREA' && !editable) return false;
      // Only suppress when the input actually has content to navigate
      // within. An empty input doesn't need arrow keys for cursor
      // movement, so we can safely repurpose arrows for dashboard nav.
      const val = (el as HTMLInputElement | HTMLTextAreaElement).value;
      if (typeof val === 'string' && val.length === 0) return false;
      if (editable && (el.textContent ?? '').length === 0) return false;
      return true;
    };

    const handleKey = (e: KeyboardEvent) => {
      if (!isActive) return;  // Don't fire shortcuts when dashboard is hidden

      // Escape blurs any active input and restores focus to the canvas —
      // so you can quickly "unstick" keyboard focus and start navigating.
      if (e.key === 'Escape') {
        const active = document.activeElement as HTMLElement | null;
        const tag = active?.tagName;
        if (tag === 'INPUT' || tag === 'TEXTAREA' || (active as any)?.isContentEditable) {
          active?.blur?.();
        }
        return;
      }

      let direction: 'left' | 'right' | 'up' | 'down' | null = null;
      switch (e.key) {
        case 'ArrowLeft': direction = 'left'; break;
        case 'ArrowRight': direction = 'right'; break;
        case 'ArrowUp': direction = 'up'; break;
        case 'ArrowDown': direction = 'down'; break;
        default: return;
      }

      // Don't hijack arrows when the user is actually typing
      if (isActivelyEditing(e.target)) return;

      // Lowered zoom floor from 0.9 → 0.4 so nav still works zoomed out
      if (canvasZoomRef.current < 0.4) return;

      // If no card is focused, pick the front-most one as a fallback so
      // nav works after the user clicked on empty canvas.
      let currentFocused = focusedCardIdRef.current;
      if (!currentFocused) {
        const anyCardId = Object.keys(cards)[0] || Object.keys(viewCards)[0] || Object.keys(browserCards)[0];
        if (!anyCardId) return;
        currentFocused = anyCardId;
        setFocusedCardId(anyCardId);
      }

      e.preventDefault();
      const target = findNearestCard(currentFocused, direction);

      if (!target) {
        // No card in that direction — shake
        if (shakeTimerRef.current) clearTimeout(shakeTimerRef.current);
        setShakeDirection(direction);
        shakeTimerRef.current = setTimeout(() => {
          setShakeDirection(null);
          shakeTimerRef.current = null;
        }, 400);
        return;
      }

      // Expand + navigate to target + bring to front
      report('dashboard', 'arrow_navigated', { direction, from_card: currentFocused, to_card: target.id });
      if (target.type === 'agent') {
        dispatch(expandSession(target.id));
      }
      dispatch(bringToFront({ id: target.id, type: target.type as any }));
      setFocusedCardId(target.id);

      setTimeout(() => {
        const rect = getCardRect(target.id, target.type);
        if (rect) canvas.actions.fitToCards([rect], 1.15, true);
        setTimeout(() => (document.activeElement as HTMLElement)?.blur?.(), 150);
      }, 100);
    };

    // Capture phase so we beat MUI Menus/Selects that also listen for
    // arrows. We still bail early on isActivelyEditing, so this doesn't
    // interfere with typing.
    window.addEventListener('keydown', handleKey, true);
    return () => window.removeEventListener('keydown', handleKey, true);
  }, [findNearestCard, getCardRect, canvas.actions, dispatch, isActive, cards, viewCards, browserCards]);

  const handleBranchFromCard = useCallback(
    (sourceSessionId: string, newSessionId: string) => {
      const sourceCard = cards[sourceSessionId];
      if (!sourceCard) return;

      const targetX = sourceCard.x + sourceCard.width + GRID_GAP * 12;
      let targetY = sourceCard.y;

      const columnCards = Object.values(cards).filter(
        (c) => Math.abs(c.x - targetX) < 50 && c.session_id !== newSessionId,
      );
      if (columnCards.length > 0) {
        const lowestBottom = Math.max(
          ...columnCards.map((c) => c.y + Math.max(EXPANDED_CARD_MIN_H, c.height)),
        );
        targetY = lowestBottom + GRID_GAP;
      }

      spawnOriginsRef.current[newSessionId] = {
        x: sourceCard.x,
        y: sourceCard.y,
        type: 'branch' as const,
      };

      dispatch(placeCard({
        sessionId: newSessionId,
        x: targetX,
        y: targetY,
        width: DEFAULT_CARD_W,
        height: DEFAULT_CARD_H,
      }));

      if (expandedSessionIds.includes(sourceSessionId)) {
        dispatch(expandSession(newSessionId));
      }

      dispatch(setGlowingAgentCard({ sessionId: newSessionId, sourceId: sourceSessionId, label: 'Branch' }));
    },
    [cards, dispatch, expandedSessionIds],
  );

  const handleNewAgent = useCallback(() => {
    setToolbarComposer('agent');
  }, []);

  const handleToolbarCancel = useCallback(() => {
    setToolbarComposer(null);
  }, []);

  const handleToolbarSend = useCallback(
    (
      prompt: string,
      mode: string,
      model: string,
      images?: Array<{ data: string; media_type: string }>,
      contextPaths?: ContextPath[],
      forcedTools?: string[],
      attachedSkills?: Array<{ id: string; name: string; content: string }>,
      selectedBrowserIds?: string[],
    ) => {
      setToolbarComposer(null);
      report('dashboard', 'agent_created', { mode, model, has_images: !!images?.length, has_context: !!contextPaths?.length, has_browser: !!selectedBrowserIds?.length });

      const draftId = `draft-${Date.now().toString(36)}`;

      const toolbarEl = toolbarRef.current;
      const vpEl = canvas.viewportRef.current;
      if (toolbarEl && vpEl) {
        const tr = toolbarEl.getBoundingClientRect();
        const vr = vpEl.getBoundingClientRect();
        const toolbarCenterX = tr.left + tr.width / 2;
        const toolbarTopY = tr.top;
        const { panX, panY, zoom } = canvasStateRef.current;
        spawnOriginsRef.current[draftId] = {
          x: (toolbarCenterX - vr.left - panX) / zoom,
          y: (toolbarTopY - vr.top - panY) / zoom,
        };
      }

      const config: AgentConfig = { name: 'New chat', model, mode, dashboard_id: dashboardId };

      dispatch(createDraftSession({ draftId, mode, model, setActive: true }));
      dispatch(ensureAgentCard({ sessionId: draftId, expandedSessionIds: [...expandedSessionIds, draftId] }));
      window.setTimeout(() => focusAgentCardWithRetry(draftId), 20);

      dispatch(
        launchAndSendFirstMessage({
          draftId,
          config,
          prompt,
          mode,
          model,
          images,
          contextPaths: contextPaths?.map((cp) => ({ path: cp.path, type: cp.type })),
          forcedTools,
          attachedSkills,
          expand: true,
        }),
      ).then((action) => {
        if (launchAndSendFirstMessage.fulfilled.match(action)) {
          const realId = action.payload.session.id;
          dispatch(generateTitle({ sessionId: realId, prompt }));
          if (selectedBrowserIds?.length) {
            dispatch(setGlowingBrowserCards({ browserIds: selectedBrowserIds, sessionId: realId, label: 'Use Browser' }));

            if (selectedBrowserIds.length === 1) {
              const bc = store.getState().dashboardLayout.browserCards[selectedBrowserIds[0]];
              if (bc) {
                dispatch(setCardPosition({
                  sessionId: realId,
                  x: bc.x - DEFAULT_CARD_W - GRID_GAP * 12,
                  y: bc.y,
                }));
              }
            }
          }
          spawnOriginsRef.current[realId] = spawnOriginsRef.current[draftId];
          delete spawnOriginsRef.current[draftId];

          setAutoFocusSessionId(realId);
          dispatch(expandSession(realId));
          dispatch(ensureAgentCard({ sessionId: realId, expandedSessionIds: store.getState().agents.expandedSessionIds }));

          window.setTimeout(() => focusAgentCardWithRetry(realId), 80);

          if (dashboardId) {
            const currentSessions = store.getState().agents.sessions;
            const agentCount = Object.values(currentSessions).filter(
              (s) => s.status !== 'draft' && s.dashboard_id === dashboardId,
            ).length;
            const NAME_GEN_TRIGGERS = [1, 3, 6];
            const currentDash = store.getState().dashboards.items[dashboardId];
            const canAutoName =
              currentDash &&
              (currentDash.auto_named || currentDash.name === 'Untitled Dashboard');

            if (NAME_GEN_TRIGGERS.includes(agentCount) && canAutoName) {
              dispatch(generateDashboardName(dashboardId));
            }
          }
        } else {
          delete spawnOriginsRef.current[draftId];
        }
      });
    },
    [canvas.viewportRef, dispatch, dashboardId, expandedSessionIds, focusAgentCardWithRetry],
  );

  const handleAddView = useCallback((outputId: string) => {
    dispatch(addViewCard({ outputId, expandedSessionIds }));
    setTimeout(() => {
      const card = store.getState().dashboardLayout.viewCards[outputId];
      const viewport = canvas.viewportRef.current;
      if (card && viewport) {
        const targetZoom = 0.9;
        const targetPanX = (viewport.clientWidth - card.width * targetZoom) / 2 - card.x * targetZoom;
        const visualCardH = card.height * targetZoom;
        const preferredTop = (viewport.clientHeight - visualCardH) / 2;
        const safeTop = Math.max(96, preferredTop);
        const targetPanY = safeTop - card.y * targetZoom;
        dispatch(bringToFront({ id: outputId, type: 'view' }));
        selection.deselectAll();
        setFocusedCardId(outputId);
        document.body.classList.remove('dashboard-marquee-active');
        document.body.style.userSelect = '';
        canvas.actions.setState({ panX: targetPanX, panY: targetPanY, zoom: targetZoom });
        handleHighlightCard(outputId);
      }
    }, 200);
  }, [dispatch, expandedSessionIds, canvas.actions, canvas.viewportRef, handleHighlightCard, selection]);

  const handleAddBrowser = useCallback(() => {
    report('dashboard', 'browser_added');
    const prevIds = new Set(Object.keys(store.getState().dashboardLayout.browserCards));
    dispatch(addBrowserCard({ url: browserHomepage, expandedSessionIds }));
    setTimeout(() => {
      const allBrowserCards = store.getState().dashboardLayout.browserCards;
      const newId = Object.keys(allBrowserCards).find((id) => !prevIds.has(id));
      if (newId) {
        const card = allBrowserCards[newId];
        canvas.actions.fitToCards([{ x: card.x, y: card.y, width: card.width, height: card.height }], 1.15, true);
        handleHighlightCard(newId);
      }
    }, 200);
  }, [dispatch, browserHomepage, expandedSessionIds, canvas.actions, handleHighlightCard]);

  const handleAddNote = useCallback(() => {
    report('dashboard', 'note_added');
    const prevIds = new Set(Object.keys(store.getState().dashboardLayout.notes));
    dispatch(addNote({ expandedSessionIds }));
    setTimeout(() => {
      const allNotes = store.getState().dashboardLayout.notes;
      const newId = Object.keys(allNotes).find((id) => !prevIds.has(id));
      if (newId) {
        const note = allNotes[newId];
        canvas.actions.fitToCards([{ x: note.x, y: note.y, width: note.width, height: note.height }], 1.15, true);
        handleHighlightCard(newId);
      }
    }, 200);
  }, [dispatch, expandedSessionIds, canvas.actions, handleHighlightCard]);


  const persistLayoutNow = useCallback((swarmPatch?: {
    swarmCardId: string;
    swarmId?: string | null;
    previewOutputId?: string | null;
    skillWorkspaceId?: string | null;
    skillWorkspacePath?: string | null;
    x?: number;
    y?: number;
    width?: number;
    height?: number;
  }) => {
    if (!layoutInitialized || !dashboardId) return;
    const state = store.getState().dashboardLayout;
    if (state.currentDashboardId !== dashboardId) return;
    const swarmCardsSnapshot = { ...state.swarmCards };

    if (swarmPatch) {
      const current = swarmCardsSnapshot[swarmPatch.swarmCardId];
      if (current) {
        swarmCardsSnapshot[swarmPatch.swarmCardId] = {
          ...current,
          swarm_id: 'swarmId' in swarmPatch ? swarmPatch.swarmId ?? null : current.swarm_id,
          preview_output_id: 'previewOutputId' in swarmPatch ? swarmPatch.previewOutputId ?? null : current.preview_output_id ?? null,
          skill_workspace_id: 'skillWorkspaceId' in swarmPatch ? swarmPatch.skillWorkspaceId ?? null : current.skill_workspace_id ?? null,
          skill_workspace_path: 'skillWorkspacePath' in swarmPatch ? swarmPatch.skillWorkspacePath ?? null : current.skill_workspace_path ?? null,
          x: swarmPatch.x ?? current.x,
          y: swarmPatch.y ?? current.y,
          width: swarmPatch.width ?? current.width,
          height: swarmPatch.height ?? current.height,
        };
      }
    }

    const payload = {
      dashboardId,
      cards: state.cards,
      viewCards: state.viewCards,
      browserCards: state.browserCards,
      plansCards: state.plansCards,
      swarmCards: swarmCardsSnapshot,
      notes: state.notes,
      expandedSessionIds,
      viewportState: canvasStateRef.current,
    };

    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current);
      saveTimerRef.current = null;
    }
    pendingSaveRef.current = null;
    dispatch(saveLayout(payload));
  }, [dashboardId, dispatch, expandedSessionIds, layoutInitialized]);

  const focusSwarmCard = useCallback((swarmCardId = 'swarm-main') => {
    const card = store.getState().dashboardLayout.swarmCards[swarmCardId];
    const viewport = canvas.viewportRef.current;
    if (!card || card.hidden || !viewport) return;

    const targetZoom = 1.1;
    const targetPanX = (viewport.clientWidth - card.width * targetZoom) / 2 - card.x * targetZoom;
    const targetPanY = (viewport.clientHeight - card.height * targetZoom) / 2 - card.y * targetZoom;

    dispatch(bringToFront({ id: card.swarm_card_id, type: 'swarm' }));
    selection.selectCard(card.swarm_card_id, 'swarm', false);
    setFocusedCardId(card.swarm_card_id);
    canvas.actions.setState({ panX: targetPanX, panY: targetPanY, zoom: targetZoom });
    handleHighlightCard(card.swarm_card_id);
  }, [canvas.actions, canvas.viewportRef, dispatch, handleHighlightCard, selection]);

  const focusViewCard = useCallback((viewCardId: string) => {
    const card = store.getState().dashboardLayout.viewCards[viewCardId];
    const viewport = canvas.viewportRef.current;
    if (!card || !viewport) return;

    const targetZoom = 1.1;
    const targetPanX = (viewport.clientWidth - card.width * targetZoom) / 2 - card.x * targetZoom;
    const visualCardH = card.height * targetZoom;
    const preferredTop = (viewport.clientHeight - visualCardH) / 2;
    const safeTop = Math.max(96, preferredTop);
    const targetPanY = safeTop - card.y * targetZoom;

    dispatch(bringToFront({ id: viewCardId, type: 'view' }));
    selection.selectCard(viewCardId, 'view', false);
    setFocusedCardId(viewCardId);
    canvas.actions.setState({ panX: targetPanX, panY: targetPanY, zoom: targetZoom });
    handleHighlightCard(viewCardId);
  }, [canvas.actions, canvas.viewportRef, dispatch, handleHighlightCard, selection]);


  const buildRefinementDraft = useCallback((output: Output, preset: string, sourceSwarmId: string) => {
    const presetLabel = preset || 'current';
    const artifactRefs = (output.artifact_refs || []).join(', ') || 'none';
    const evidenceRefs = (output.evidence_refs || []).join(', ') || 'none';

    return [
      'Quiero refinar la app generada desde esta Preview.',
      '',
      `Output ID: ${output.id}`,
      `Output name: ${output.name}`,
      `Preset actual: ${presetLabel}`,
      `Source swarm: ${sourceSwarmId}`,
      `Source task: ${output.source_task_id || 'unknown'}`,
      `Validation status: ${output.validation_status || 'unknown'}`,
      `Artifacts: ${artifactRefs}`,
      `Evidence: ${evidenceRefs}`,
      '',
      'Cambio solicitado:',
    ].join('\n');
  }, []);

  const handleRefineOutput = useCallback((output: Output, preset: string) => {
    const sourceSwarmId = output.source_swarm_id;
    if (!sourceSwarmId) return;

    const draft = buildRefinementDraft(output, preset, sourceSwarmId);
    const swarmCards = store.getState().dashboardLayout.swarmCards;
    const sourceSwarmCard = Object.values(swarmCards)
      .find((card) => card.swarm_id === sourceSwarmId);

    if (sourceSwarmCard) {
      dispatch(addSwarmCard({
        expandedSessionIds,
        swarmCardId: sourceSwarmCard.swarm_card_id,
        swarmId: sourceSwarmId,
        swarmMode: sourceSwarmCard.swarm_mode,
        swarmModel: sourceSwarmCard.swarm_model,
      }));
      persistLayoutNow({
        swarmCardId: sourceSwarmCard.swarm_card_id,
        swarmId: sourceSwarmId,
        previewOutputId: output.id,
      });
      setSwarmDraftPrompts((prev) => ({ ...prev, [sourceSwarmCard.swarm_card_id]: draft }));
      window.setTimeout(() => focusSwarmCard(sourceSwarmCard.swarm_card_id), 80);
      return;
    }

    dispatch(addSwarmCard({
      expandedSessionIds,
      swarmCardId: 'swarm-main',
      swarmId: sourceSwarmId,
      swarmMode: 'app_builder',
      swarmModel: null,
    }));
    window.setTimeout(() => {
      const nextCards = store.getState().dashboardLayout.swarmCards;
      const fallbackCard = nextCards['swarm-main'] || Object.values(nextCards).find((card) => !card.hidden);
      if (!fallbackCard) return;
      dispatch(setSwarmCardSwarmId({ swarmCardId: fallbackCard.swarm_card_id, swarmId: sourceSwarmId }));
      persistLayoutNow({
        swarmCardId: fallbackCard.swarm_card_id,
        swarmId: sourceSwarmId,
        previewOutputId: output.id,
      });
      setSwarmDraftPrompts((prev) => ({ ...prev, [fallbackCard.swarm_card_id]: draft }));
      focusSwarmCard(fallbackCard.swarm_card_id);
    }, 80);
  }, [buildRefinementDraft, dispatch, expandedSessionIds, focusSwarmCard, persistLayoutNow]);

  const handleToolbarSwarmSend = useCallback(async (
    prompt: string,
    swarmMode: SwarmMode,
    swarmModel: string,
    composerPayload?: UnifiedComposerSubmitPayload | null,
  ) => {
    const cleanPrompt = (composerPayload?.prompt || prompt).trim();
    if (!cleanPrompt) return;

    setToolbarComposer(null);
    report('dashboard', 'swarm_created', { swarm_mode: swarmMode, model: swarmModel });

    const swarmCardId = 'swarm-main';
    dispatch(addSwarmCard({ expandedSessionIds, swarmMode, swarmModel }));
    window.setTimeout(() => focusSwarmCard(swarmCardId), 120);

    let swarmIdToRun = store.getState().dashboardLayout.swarmCards[swarmCardId]?.swarm_id || null;
    const loadedSwarm = store.getState().experimentalSwarms.swarm;
    if (swarmIdToRun && loadedSwarm?.id === swarmIdToRun && loadedSwarm?.intent && loadedSwarm.intent !== 'chat') {
      swarmIdToRun = null;
    }

    if (!swarmIdToRun) {
      const createAction = await dispatch(createExperimentalSwarm({
        userPrompt: cleanPrompt,
        dashboardId,
        intent: 'chat',
        swarmMode,
        swarmModel,
      }));

      if (!createExperimentalSwarm.fulfilled.match(createAction)) return;
      swarmIdToRun = createAction.payload.id;
      dispatch(setSwarmCardSwarmId({ swarmCardId, swarmId: swarmIdToRun }));
    }

    await dispatch(chatExperimentalSwarm({
      swarmId: swarmIdToRun,
      message: cleanPrompt,
      swarmMode,
      model: swarmModel,
      composerPayload: composerPayload || null,
    }));
    dispatch(fetchExperimentalSwarm(swarmIdToRun));
    window.setTimeout(() => focusSwarmCard(swarmCardId), 160);
  }, [dashboardId, dispatch, expandedSessionIds, focusSwarmCard]);

  const handleAddSwarm = useCallback(() => {
    report('dashboard', 'swarm_toggled');
    const existing = store.getState().dashboardLayout.swarmCards['swarm-main'];

    if (existing?.swarm_id) {
      dispatch(addSwarmCard({
        expandedSessionIds,
        swarmCardId: 'swarm-main',
        swarmId: existing.swarm_id,
        swarmMode: existing.swarm_mode,
        swarmModel: existing.swarm_model ?? null,
      }));
      setToolbarComposer(null);
      window.setTimeout(() => focusSwarmCard('swarm-main'), 120);
      return;
    }

    if (existing && !existing.hidden) {
      focusSwarmCard('swarm-main');
      return;
    }

    setToolbarComposer('swarm');
  }, [dispatch, expandedSessionIds, focusSwarmCard]);

  const focusPlansCard = useCallback((plansCardId: string) => {
    const card = store.getState().dashboardLayout.plansCards[plansCardId];
    const viewport = canvas.viewportRef.current;
    if (!card || card.hidden || !viewport) return;

    if (card.collapsed) {
      dispatch(togglePlansCardCollapsed(plansCardId));
    }

    const targetZoom = 1.2;
    const targetPanX = (viewport.clientWidth - card.width * targetZoom) / 2 - card.x * targetZoom;
    const targetPanY = (viewport.clientHeight - card.height * targetZoom) / 2 - card.y * targetZoom;

    dispatch(bringToFront({ id: card.plans_card_id, type: 'plans' }));
    selection.selectCard(card.plans_card_id, 'plans', false);
    setFocusedCardId(card.plans_card_id);
    canvas.actions.setState({ panX: targetPanX, panY: targetPanY, zoom: targetZoom });
    handleHighlightCard(card.plans_card_id);
  }, [canvas.actions, canvas.viewportRef, dispatch, handleHighlightCard, selection]);

  const handleAddPlans = useCallback(() => {
    const requestId = ++navigationRequestRef.current;
    const existingPlansCard = store.getState().dashboardLayout.plansCards['plans-main'];

    if (existingPlansCard && !existingPlansCard.hidden) {
      const vp = canvas.viewportRef.current;
      const { panX, panY, zoom } = canvasStateRef.current;
      const cardLeft = existingPlansCard.x * zoom + panX;
      const cardTop = existingPlansCard.y * zoom + panY;
      const cardRight = (existingPlansCard.x + existingPlansCard.width) * zoom + panX;
      const cardBottom = (existingPlansCard.y + existingPlansCard.height) * zoom + panY;
      const margin = 80;
      const isVisible = !!vp
        && cardRight > margin
        && cardBottom > margin
        && cardLeft < vp.clientWidth - margin
        && cardTop < vp.clientHeight - margin;

      if (isVisible) {
        dispatch(removePlansCard(existingPlansCard.plans_card_id));
        return;
      }

      focusPlansCard(existingPlansCard.plans_card_id);
      return;
    }

    dispatch(addPlansCard({ expandedSessionIds }));

    window.setTimeout(() => {
      if (navigationRequestRef.current !== requestId) return;
      focusPlansCard('plans-main');
    }, 120);
  }, [canvas.viewportRef, dispatch, expandedSessionIds, focusPlansCard]);

  // Auto-clear pendingFocusNoteId after the note has had a chance to mount + autofocus.
  useEffect(() => {
    if (!pendingFocusNoteId) return;
    const t = setTimeout(() => dispatch(clearPendingFocusNoteId()), 800);
    return () => clearTimeout(t);
  }, [pendingFocusNoteId, dispatch]);

  const handleHistoryResume = useCallback((sessionId: string) => {
    dispatch(resumeSession({ sessionId })).then((action) => {
      if (!resumeSession.fulfilled.match(action) || !action.payload?.id) {
        return;
      }

      const resumedSessionId = action.payload.id;
      dispatch(expandSession(resumedSessionId));
      setAutoFocusSessionId(resumedSessionId);
      setTimeout(() => {
        const card = store.getState().dashboardLayout.cards[resumedSessionId];
        if (card) {
          canvas.actions.fitToCards([{ x: card.x, y: card.y, width: card.width, height: card.height }], 1.15, true);
          handleHighlightCard(resumedSessionId);
        }
      }, 200);
    });
  }, [dispatch, canvas.actions, handleHighlightCard, setAutoFocusSessionId]);


  const focusAgentFromPlans = useCallback((sessionId: string, requestId?: number) => {
    const activeRequestId = requestId ?? ++navigationRequestRef.current;

    dispatch(expandSession(sessionId));
    dispatch(bringToFront({ id: sessionId, type: 'agent' }));
    selection.selectCard(sessionId, 'agent', false);
    setFocusedCardId(sessionId);
    setAutoFocusSessionId(sessionId);

    window.setTimeout(() => {
      if (navigationRequestRef.current !== activeRequestId) return;

      const card = store.getState().dashboardLayout.cards[sessionId];
      if (!card) return;

      canvas.actions.fitToCards(
        [{ x: card.x, y: card.y, width: card.width, height: card.height }],
        1.15,
        true,
      );
      handleHighlightCard(sessionId);
    }, 140);
  }, [dispatch, selection, canvas.actions, handleHighlightCard, setAutoFocusSessionId]);

  const handleGoToAgentFromPlans = useCallback((sessionId: string) => {
    const requestId = ++navigationRequestRef.current;
    const state = store.getState();
    const session = state.agents.sessions[sessionId];

    if (session) {
      const expanded = Array.from(new Set([...state.agents.expandedSessionIds, sessionId]));

      dispatch(ensureAgentCard({
        sessionId,
        expandedSessionIds: expanded,
      }));
      dispatch(expandSession(sessionId));

      window.setTimeout(() => {
        if (navigationRequestRef.current !== requestId) return;
        focusAgentFromPlans(sessionId, requestId);
      }, 120);
      return;
    }

    dispatch(resumeSession({ sessionId })).then((action) => {
      if (navigationRequestRef.current !== requestId) return;
      if (!resumeSession.fulfilled.match(action) || !action.payload?.id) return;

      const resumedSessionId = action.payload.id;
      const nextState = store.getState();
      const expanded = Array.from(new Set([...nextState.agents.expandedSessionIds, resumedSessionId]));

      dispatch(ensureAgentCard({
        sessionId: resumedSessionId,
        expandedSessionIds: expanded,
      }));
      dispatch(expandSession(resumedSessionId));

      window.setTimeout(() => {
        if (navigationRequestRef.current !== requestId) return;
        focusAgentFromPlans(resumedSessionId, requestId);
      }, 120);
    });
  }, [dispatch, focusAgentFromPlans]);


  // Context-aware fit: if a card is selected, zoom to it; otherwise fit all
  const handleFitToView = useCallback(() => {
    report('dashboard', 'fit_to_view', { has_selection: selection.selectedIds.size > 0 });
    if (selection.selectedIds.size === 1) {
      const [[id, type]] = selection.selectedIds;
      const rect = getCardRect(id, type);
      if (rect) {
        canvas.actions.fitToCards([rect], 1.15, true);
        return;
      }
    }
    canvas.actions.fitToView();
  }, [selection.selectedIds, getCardRect, canvas.actions]);

  const handleTidy = useCallback(() => {
    report('dashboard', 'tidy_layout');
    const currentExpanded = store.getState().agents.expandedSessionIds;
    dispatch(tidyLayout({ expandedSessionIds: currentExpanded }));

    const expandedSet = new Set(currentExpanded);
    const { cards: tidied, viewCards: tidiedViews, browserCards: tidiedBrowsers } = store.getState().dashboardLayout;
    const allRects = [
      ...Object.values(tidied).map((c) => ({
        x: c.x, y: c.y, width: c.width,
        height: expandedSet.has(c.session_id) ? Math.max(EXPANDED_CARD_MIN_H, c.height) : c.height,
      })),
      ...Object.values(tidiedViews).map((c) => ({ x: c.x, y: c.y, width: c.width, height: c.height })),
      ...Object.values(tidiedBrowsers).map((c) => ({ x: c.x, y: c.y, width: c.width, height: c.height })),
    ];
    canvas.actions.fitToCards(allRects);
  }, [dispatch, canvas.actions]);

  useEffect(() => {
    if (!isActive) return;  // Heavy geometry recalculation — pause when dashboard is hidden
    const DRIFT_THRESHOLD = 60;

    // Group tethered sub-agent cards by source, only including those still in the spawn column
    const sourceToSiblings = new Map<string, string[]>();
    for (const [id, glow] of Object.entries(glowingAgentCards)) {
      const card = cards[id];
      if (!card) continue;
      const sourceCard = cards[glow.sourceId];
      if (!sourceCard) continue;
      const expectedX = sourceCard.x + sourceCard.width + GRID_GAP * 12;
      if (Math.abs(card.x - expectedX) > DRIFT_THRESHOLD) continue;
      const list = sourceToSiblings.get(glow.sourceId) ?? [];
      list.push(id);
      sourceToSiblings.set(glow.sourceId, list);
    }

    for (const siblings of sourceToSiblings.values()) {
      if (siblings.length < 2) continue;
      siblings.sort((a, b) => cards[a].y - cards[b].y);

      let cursor = cards[siblings[0]].y;
      for (const id of siblings) {
        const card = cards[id];
        const dy = cursor - card.y;
        if (Math.abs(dy) > 1) {
          dispatch(moveCards({ items: [{ id, type: 'agent' as const }], dx: 0, dy }));
        }
        const isExpanded = expandedSessionIds.includes(id);
        const h = isExpanded
          ? Math.max(EXPANDED_CARD_MIN_H, card.height)
          : (measuredHeightsRef.current[id] ?? card.height);
        cursor += h + GRID_GAP * 2;
      }
    }
  // measuredHeightsTick in deps ensures we re-run once ResizeObserver reports
  // the new height after a collapse (avoids stale-height no-ops)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isActive, expandedSessionIds, glowingAgentCards, cards, dispatch, measuredHeightsTick]);

  useEffect(() => {
    if (!isActive) return;  // Heavy geometry recalculation — pause when dashboard is hidden
    const DRIFT_THRESHOLD = 60;

    const sourceToSiblings = new Map<string, string[]>();
    for (const [browserId, glow] of Object.entries(glowingBrowserCards)) {
      const bc = browserCards[browserId];
      if (!bc) continue;
      const sourceCard = cards[glow.sourceId];
      if (!sourceCard) continue;
      const expectedX = sourceCard.x + sourceCard.width + GRID_GAP * 12;
      if (Math.abs(bc.x - expectedX) > DRIFT_THRESHOLD) continue;
      const list = sourceToSiblings.get(glow.sourceId) ?? [];
      list.push(browserId);
      sourceToSiblings.set(glow.sourceId, list);
    }

    for (const siblings of sourceToSiblings.values()) {
      if (siblings.length < 2) continue;
      siblings.sort((a, b) => browserCards[a].y - browserCards[b].y);

      let cursor = browserCards[siblings[0]].y;
      for (const id of siblings) {
        const bc = browserCards[id];
        const dy = cursor - bc.y;
        if (Math.abs(dy) > 1) {
          dispatch(moveCards({ items: [{ id, type: 'browser' as const }], dx: 0, dy }));
        }
        cursor += bc.height + GRID_GAP * 2;
      }
    }
  }, [isActive, glowingBrowserCards, browserCards, cards, dispatch]);

  const TETHER_FADE_MS = 2500;

  const tethers = useMemo(() => {
    const ELBOW_RADIUS = 16;

    function elbowPath(x1: number, y1: number, x2: number, y2: number): string {
      const dx = x2 - x1;
      const dy = y2 - y1;
      const midX = x1 + dx / 2;
      const r = (Math.abs(dy) < 1 || Math.abs(dx) < ELBOW_RADIUS * 2)
        ? 0
        : Math.min(ELBOW_RADIUS, Math.abs(dy) / 2, Math.abs(dx) / 4);
      const sy = dy >= 0 ? 1 : -1;
      const sx = dx >= 0 ? 1 : -1;

      return [
        `M ${x1},${y1}`,
        `H ${midX - sx * r}`,
        `Q ${midX},${y1} ${midX},${y1 + sy * r}`,
        `V ${y2 - sy * r}`,
        `Q ${midX},${y2} ${midX + sx * r},${y2}`,
        `H ${x2}`,
      ].join(' ');
    }

    const agentTethers = Object.entries(glowingAgentCards).map(([copyId, { sourceId, fading, sourceYRatio, label }]) => {
      const src = cards[sourceId];
      const dst = cards[copyId];
      if (!src || !dst) return null;

      let srcX = src.x, srcY = src.y;
      let dstX = dst.x, dstY = dst.y;
      if (liveDragInfo) {
        if (liveDragInfo.cardId === sourceId) { srcX += liveDragInfo.dx; srcY += liveDragInfo.dy; }
        if (liveDragInfo.cardId === copyId) { dstX += liveDragInfo.dx; dstY += liveDragInfo.dy; }
      }

      const srcMeasured = measuredHeightsRef.current[sourceId];
      const srcH = srcMeasured ?? (expandedSessionIds.includes(sourceId)
        ? Math.max(EXPANDED_CARD_MIN_H, src.height)
        : src.height);
      const dstMeasured = measuredHeightsRef.current[copyId];
      const dstH = dstMeasured ?? (expandedSessionIds.includes(copyId)
        ? Math.max(EXPANDED_CARD_MIN_H, dst.height)
        : dst.height);

      const x1 = srcX + src.width;
      const y1 = srcY + srcH * 0.54;
      const x2 = dstX;
      const y2 = dstY + dstH * (expandedSessionIds.includes(copyId) ? 0.54 : 0.79);
      const midX = x1 + (x2 - x1) / 2;
      const labelX = midX + (x2 - midX) * 0.15;
      const labelY = y2;

      return {
        key: copyId,
        path: elbowPath(x1, y1, x2, y2),
        labelX,
        labelY,
        label: label || '',
        fading,
      };
    }).filter(Boolean) as Array<{ key: string; path: string; labelX: number; labelY: number; label: string; fading: boolean }>;

    // Build browser tethers from TWO sources and merge:
    // 1. glowingBrowserCards — the short-lived "flash" when a browser is first assigned
    // 2. Active browser-agent sessions — persistent as long as the agent runs
    //
    // Source #2 is the fix for tethers disappearing when the parent session
    // completes a turn (which clears glowingBrowserCards even though the
    // browser agent is still working). Source #1 covers the initial moment
    // before the browser-agent session is fully created. Together they
    // ensure the arrow is always visible when it should be.

    type Anchor = { x: number; y: number; side: 'left' | 'right' | 'top' | 'bottom' };

    function browserTether(
      browserId: string,
      sourceId: string,
      fading: boolean,
      label: string,
    ) {
      const src = cards[sourceId];
      const dst = browserCards[browserId];
      if (!src || !dst) return null;

      let srcX = src.x, srcY = src.y;
      let dstX = dst.x, dstY = dst.y;
      if (liveDragInfo) {
        if (liveDragInfo.cardId === sourceId) { srcX += liveDragInfo.dx; srcY += liveDragInfo.dy; }
        if (liveDragInfo.cardId === browserId) { dstX += liveDragInfo.dx; dstY += liveDragInfo.dy; }
      }

      const srcMeasured = measuredHeightsRef.current[sourceId];
      const srcH = srcMeasured ?? (expandedSessionIds.includes(sourceId)
        ? Math.max(EXPANDED_CARD_MIN_H, src.height)
        : src.height);
      const dstH = dst.height;

      const srcCx = srcX + src.width / 2;
      const dstCx = dstX + dst.width / 2;

      const srcAnchors: Anchor[] = [
        { x: srcX + src.width, y: srcY + srcH * 0.54, side: 'right' },
        { x: srcX, y: srcY + srcH * 0.54, side: 'left' },
        { x: srcCx, y: srcY, side: 'top' },
        { x: srcCx, y: srcY + srcH, side: 'bottom' },
      ];
      const dstAnchors: Anchor[] = [
        { x: dstX, y: dstY + dstH * 0.54, side: 'left' },
        { x: dstX + dst.width, y: dstY + dstH * 0.54, side: 'right' },
        { x: dstCx, y: dstY, side: 'top' },
        { x: dstCx, y: dstY + dstH, side: 'bottom' },
      ];

      let bestSrc = srcAnchors[0], bestDst = dstAnchors[0];
      let bestDist = Infinity;
      for (const sa of srcAnchors) {
        for (const da of dstAnchors) {
          const d = Math.hypot(sa.x - da.x, sa.y - da.y);
          if (d < bestDist) { bestDist = d; bestSrc = sa; bestDst = da; }
        }
      }

      const x1 = bestSrc.x, y1 = bestSrc.y;
      const x2 = bestDst.x, y2 = bestDst.y;

      const isVertical = (bestSrc.side === 'top' || bestSrc.side === 'bottom')
        && (bestDst.side === 'top' || bestDst.side === 'bottom');

      let pathD: string;
      if (isVertical) {
        const dx = x2 - x1;
        const dy = y2 - y1;
        const midY = y1 + dy / 2;
        const r = (Math.abs(dx) < 1 || Math.abs(dy) < ELBOW_RADIUS * 2)
          ? 0
          : Math.min(ELBOW_RADIUS, Math.abs(dx) / 2, Math.abs(dy) / 4);
        const sx = dx >= 0 ? 1 : -1;
        const sy = dy >= 0 ? 1 : -1;
        pathD = [
          `M ${x1},${y1}`,
          `V ${midY - sy * r}`,
          `Q ${x1},${midY} ${x1 + sx * r},${midY}`,
          `H ${x2 - sx * r}`,
          `Q ${x2},${midY} ${x2},${midY + sy * r}`,
          `V ${y2}`,
        ].join(' ');
      } else {
        pathD = elbowPath(x1, y1, x2, y2);
      }

      const midX = x1 + (x2 - x1) / 2;
      const midY = y1 + (y2 - y1) / 2;
      const labelX = isVertical ? midX : midX + (x2 - midX) * 0.15;
      const labelY = isVertical ? midY + (y2 - midY) * 0.15 : y2;

      return {
        key: `browser-${browserId}`,
        path: pathD,
        labelX,
        labelY,
        label,
        fading,
      };
    }

    // Source 1: glow-based (covers the initial flash before browser-agent session exists)
    const glowTethers = new Map<string, ReturnType<typeof browserTether>>();
    for (const [browserId, { sourceId, fading, label }] of Object.entries(glowingBrowserCards)) {
      const t = browserTether(browserId, sourceId, fading, label || '');
      if (t) glowTethers.set(browserId, t);
    }

    // Source 2: active browser-agent sessions (persistent — survives parent turn completion)
    for (const s of sessionList) {
      if (s.mode !== 'browser-agent') continue;
      if (s.status !== 'running' && s.status !== 'waiting_approval') continue;
      if (!s.browser_id || !s.parent_session_id) continue;
      if (glowTethers.has(s.browser_id)) continue; // glow already covers this one
      const t = browserTether(s.browser_id, s.parent_session_id, false, '');
      if (t) glowTethers.set(s.browser_id, t);
    }

    const browserTethers = Array.from(glowTethers.values()).filter(Boolean) as Array<{ key: string; path: string; labelX: number; labelY: number; label: string; fading: boolean }>;

    return [...agentTethers, ...browserTethers];
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [glowingAgentCards, glowingBrowserCards, cards, browserCards, expandedSessionIds, liveDragInfo, measuredHeightsTick, sessionList]);

  const dotSize = Math.max(1, 1.5 * canvas.zoom);
  const dotSpacing = 24 * canvas.zoom;
  const dpr = window.devicePixelRatio || 1;
  const crispPanX = Math.round(canvas.panX * dpr) / dpr;
  const crispPanY = Math.round(canvas.panY * dpr) / dpr;

  useEffect(() => {
    const el = canvas.viewportRef.current;
    if (!el) return;

    const update = () => {
      setCanvasViewportSize({
        width: el.clientWidth,
        height: el.clientHeight,
      });
    };

    update();

    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, [canvas.viewportRef]);

  const handleRenameDashboard = useCallback((name: string) => {
    if (!dashboardId || !dashboard) return;
    dispatch(renameDashboard({
      id: dashboardId,
      name,
      previousName: dashboard.name,
      autoNamed: false,
    }));
  }, [dashboard, dashboardId, dispatch]);

  const handleOpenDashboardWorkspace = useCallback(async () => {
    if (!dashboardWorkspacePath) return;
    const result = await window.openswarm?.openFolder?.(dashboardWorkspacePath);
    if (result && !result.ok) {
      console.warn('[dashboard] failed to open workspace folder:', result.error);
    }
  }, [dashboardWorkspacePath]);

  return (
    <>
    <DashboardSelectionOverlay />
    <Box sx={{ position: 'relative', height: '100%', overflow: 'hidden' }}>
      {/* Floating header overlay */}
      <Box
        sx={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          zIndex: 10,
          pointerEvents: 'none',
          p: 3,
          pb: 0,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', pointerEvents: 'auto' }}>
          <DashboardHeader
            dashboardName={dashboardName}
            sessions={sessions}
            cards={cards}
            viewCards={viewCards}
            browserCards={browserCards}
            outputs={outputs}
            dashboardId={dashboardId}
            canvasActions={canvas.actions}
            onHighlightCard={handleHighlightCard}
            onRenameDashboard={handleRenameDashboard}
            onOpenWorkspace={handleOpenDashboardWorkspace}
            workspacePath={dashboardWorkspacePath}
            workspaceLoading={dashboardWorkspaceLoading}
          />
        </Box>
      </Box>

      {/* Canvas viewport */}
      <Box
        ref={canvas.viewportRef}
        onMouseDown={handleViewportMouseDown}
        onMouseMove={handleViewportMouseMove}
        onMouseUp={handleViewportMouseUp}
        onDoubleClick={handleViewportDoubleClick}
        onContextMenu={(e) => e.preventDefault()}
        sx={{
          position: 'absolute',
          inset: 0,
          overflow: 'hidden',
          cursor: canvas.isPanning
            ? 'grabbing'
            : (canvas.spaceHeld || canvas.cmdHeld)
              ? 'grab'
              : selection.marquee
                ? 'crosshair'
                : 'default',
        }}
      >
        {/* Dot grid background */}
        <Box
          sx={{
            position: 'absolute',
            inset: 0,
            pointerEvents: 'none',
            backgroundImage: `radial-gradient(circle, ${c.border.medium} ${dotSize}px, transparent ${dotSize}px)`,
            backgroundSize: `${dotSpacing}px ${dotSpacing}px`,
            backgroundPosition: `${crispPanX % dotSpacing}px ${crispPanY % dotSpacing}px`,
          }}
        />

        {sessionList.length === 0 && Object.keys(viewCards).length === 0 && Object.keys(browserCards).length === 0 && Object.keys(plansCards).length === 0 && Object.keys(swarmCards).length === 0 && Object.keys(notes).length === 0 ? (
          <Box
            sx={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              pointerEvents: 'none',
            }}
          >
            <style>{`@keyframes empty-state-shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }`}</style>
            <Typography sx={{ color: c.text.tertiary, fontSize: '1.1rem', mb: 1 }}>
              No agents running
            </Typography>
            <Typography
              sx={{
                fontSize: '0.9rem',
                background: `linear-gradient(90deg, ${c.text.ghost} 0%, ${c.text.ghost} 40%, ${c.text.primary} 50%, ${c.text.ghost} 60%, ${c.text.ghost} 100%)`,
                backgroundSize: '200% 100%',
                WebkitBackgroundClip: 'text',
                backgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                color: 'transparent',
                animation: 'empty-state-shimmer 6s linear infinite',
              }}
            >
              Click the &quot;+&quot; button below to launch your first agent
            </Typography>
          </Box>
        ) : (
          <div
            ref={canvas.contentRef}
            style={{
              transform: `translate(${crispPanX}px, ${crispPanY}px) scale(${canvas.zoom})`,
              transformOrigin: '0 0',
              willChange: canvas.isPanning ? 'transform' : 'auto',
              position: 'relative',
            }}
          >
            {/* Tether lines between branched cards */}
            {tethers.length > 0 && (
              <svg
                style={{
                  position: 'absolute',
                  left: 0,
                  top: 0,
                  width: 1,
                  height: 1,
                  overflow: 'visible',
                  pointerEvents: 'none',
                  zIndex: 10,
                }}
              >
                <defs>
                  <filter id="tether-glow-f" x="-50%" y="-50%" width="200%" height="200%">
                    <feGaussianBlur in="SourceGraphic" stdDeviation="6" result="blur" />
                    <feMerge>
                      <feMergeNode in="blur" />
                      <feMergeNode in="SourceGraphic" />
                    </feMerge>
                  </filter>
                  <marker
                    id="tether-arrow"
                    viewBox="0 0 10 10"
                    refX="10"
                    refY="5"
                    markerWidth="10"
                    markerHeight="10"
                    orient="auto"
                  >
                    <path d="M 0 1 L 10 5 L 0 9 z" fill={c.accent.primary} opacity={0.8} />
                  </marker>
                </defs>
                <style>{`
                  @keyframes tether-flow { to { stroke-dashoffset: -16; } }
                  @keyframes tether-pulse { 0%, 100% { opacity: 0.6; } 50% { opacity: 1; } }
                `}</style>
                {tethers.map((t) => (
                  <g
                    key={t.key}
                    style={{
                      opacity: t.fading ? 0 : 1,
                      transition: `opacity ${TETHER_FADE_MS}ms ease-out`,
                    }}
                  >
                    <path
                      d={t.path}
                      fill="none"
                      stroke={c.accent.primary}
                      strokeWidth={8}
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      opacity={0.2}
                      filter="url(#tether-glow-f)"
                    />
                    <path
                      d={t.path}
                      fill="none"
                      stroke={c.accent.primary}
                      strokeWidth={2}
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      opacity={0.65}
                      markerEnd="url(#tether-arrow)"
                      style={{ animation: 'tether-pulse 2s ease-in-out infinite' }}
                    />
                    <path
                      d={t.path}
                      fill="none"
                      stroke={c.accent.primary}
                      strokeWidth={1.5}
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeDasharray="8 8"
                      opacity={0.9}
                      style={{ animation: 'tether-flow 0.6s linear infinite' }}
                    />
                    {t.label && (
                      <g transform={`translate(${t.labelX},${t.labelY})`}>
                        <rect
                          x={-4}
                          y={-14}
                          width={t.label.length * 7.5 + 8}
                          height={20}
                          rx={4}
                          fill={c.bg.surface}
                          stroke={c.accent.primary}
                          strokeWidth={1}
                          opacity={0.95}
                        />
                        <text
                          x={t.label.length * 7.5 / 2}
                          y={1}
                          textAnchor="middle"
                          fontSize={11}
                          fontWeight={600}
                          fontFamily="inherit"
                          fill={c.accent.primary}
                        >
                          {t.label}
                        </text>
                      </g>
                    )}
                  </g>
                ))}
              </svg>
            )}
            <SwarmOrchestrationPreview
              state={orchestrationCanvasState}
              zoom={canvas.zoom}
              onNodeMoveEnd={(nodeId, x, y) => {
                const swarmId = activeExperimentalSwarm?.id;
                if (!swarmId) return;
                dispatch(updateOrchestrationNodePosition({ swarmId, nodeId, x, y }));
              }}
              onNodeExpandedChange={(nodeId, expanded) => {
                const swarmId = activeExperimentalSwarm?.id;
                if (!swarmId) return;
                dispatch(updateOrchestrationNodePosition({ swarmId, nodeId, expanded }));
              }}
              onNodeDoubleClick={(node) => {
                const viewport = canvas.viewportRef.current;
                if (!viewport) return;

                const previousFocus = orchestrationFocusReturnRef.current;
                if (previousFocus?.nodeId === node.id) {
                  canvas.actions.setState({
                    panX: previousFocus.panX,
                    panY: previousFocus.panY,
                    zoom: previousFocus.zoom,
                  });
                  orchestrationFocusReturnRef.current = null;
                  return;
                }

                const currentView = canvasStateRef.current;
                orchestrationFocusReturnRef.current = {
                  nodeId: node.id,
                  panX: currentView.panX,
                  panY: currentView.panY,
                  zoom: currentView.zoom,
                };

                const targetZoom = 1.8;
                const width = node.width || 180;
                const height = node.expanded ? 172 : (node.height || 96);
                const targetPanX = (viewport.clientWidth - width * targetZoom) / 2 - node.x * targetZoom;
                const targetPanY = (viewport.clientHeight - height * targetZoom) / 2 - node.y * targetZoom;
                canvas.actions.setState({ panX: targetPanX, panY: targetPanY, zoom: targetZoom });
              }}
            />
            <AnimatePresence>
            {Object.values(cards).map((card) => {
              const session = sessions[card.session_id];
              if (!session) return null;

              let origin = spawnOriginsRef.current[session.id];
              if (origin) {
                delete spawnOriginsRef.current[session.id];
              } else {
                const glow = glowingAgentCards[session.id];
                if (glow && !revealSpawnedRef.current.has(session.id)) {
                  revealSpawnedRef.current.add(session.id);
                  const srcCard = cards[glow.sourceId];
                  if (srcCard) {
                    const srcH = measuredHeightsRef.current[glow.sourceId]
                      ?? (expandedSessionIds.includes(glow.sourceId)
                        ? Math.max(EXPANDED_CARD_MIN_H, srcCard.height)
                        : srcCard.height);
                    origin = {
                      x: srcCard.x + srcCard.width,
                      y: srcCard.y + srcH / 2,
                      type: 'branch' as const,
                    };
                  }
                }
              }

              let exitTarget: { x: number; y: number } | undefined;
              const glow = glowingAgentCards[session.id];
              if (glow) {
                const srcCard = cards[glow.sourceId];
                if (srcCard) {
                  const srcH = measuredHeightsRef.current[glow.sourceId]
                    ?? (expandedSessionIds.includes(glow.sourceId)
                      ? Math.max(EXPANDED_CARD_MIN_H, srcCard.height)
                      : srcCard.height);
                  exitTarget = {
                    x: srcCard.x + srcCard.width,
                    y: srcCard.y + srcH / 2,
                  };
                }
              }

              let snapColumn: { x: number; width: number } | undefined;
              if (glow) {
                const srcCard = cards[glow.sourceId];
                if (srcCard) {
                  snapColumn = {
                    x: srcCard.x + srcCard.width + GRID_GAP * 12,
                    width: DEFAULT_CARD_W,
                  };
                }
              }

              return (
                <AgentCard
                  key={session.id}
                  session={session}
                  expanded={expandedSessionIds.includes(session.id)}
                  cardX={card.x}
                  cardY={card.y}
                  cardWidth={card.width}
                  cardHeight={card.height}
                  cardZOrder={card.zOrder ?? 0}
                  zoom={canvas.zoom}
                  panX={canvas.panX}
                  panY={canvas.panY}
                  spawnFrom={origin}
                  exitTarget={exitTarget}
                  isSelected={selection.isSelected(session.id)}
                  isHighlighted={highlightedCardId === session.id}
                  multiDragDelta={multiDragDelta}
                  onCardSelect={handleCardSelect}
                  onDragStart={handleCardDragStart}
                  onDragMove={handleCardDragMove}
                  onDragEnd={handleCardDragEnd}
                  onBranch={handleBranchFromCard}
                  onMeasuredHeight={handleMeasuredHeight}
                  snapColumn={snapColumn}
                  autoFocusInput={autoFocusSessionId === session.id}
                  onDoubleClick={handleCardDoubleClick}
                  onBringToFront={handleBringToFront}
                  shakeDirection={focusedCardId === session.id ? shakeDirection : null}
                />
              );
            })}
            </AnimatePresence>
            {Object.entries(viewCards).map(([viewCardId, vc]) => {
              const output = outputs[vc.output_id];
              if (!output) return null;
              const resolvedViewCardId = vc.view_card_id || viewCardId;
              return (
                <DashboardViewCard
                  key={`view-${resolvedViewCardId}`}
                  viewCardId={resolvedViewCardId}
                  output={output}
                  previewKind={vc.preview_kind || 'stable'}
                  iterationId={vc.iteration_id ?? null}
                  candidateWorkspacePath={vc.candidate_workspace_path ?? null}
                  title={vc.title ?? null}
                  cardX={vc.x}
                  cardY={vc.y}
                  cardWidth={vc.width}
                  cardHeight={vc.height}
                  devicePreset={vc.device_preset ?? null}
                  cardZOrder={vc.zOrder ?? 0}
                  zoom={canvas.zoom}
                  panX={canvas.panX}
                  panY={canvas.panY}
                  cmdHeld={canvas.cmdHeld}
                  isSelected={selection.isSelected(resolvedViewCardId)}
                  isHighlighted={highlightedCardId === resolvedViewCardId}
                  multiDragDelta={multiDragDelta}
                  onCardSelect={handleCardSelect}
                  onDragStart={handleCardDragStart}
                  onDragMove={handleCardDragMove}
                  onDragEnd={handleCardDragEnd}
                  onDoubleClick={handleCardDoubleClick}
                  onBringToFront={handleBringToFront}
                  onFocusViewCard={focusViewCard}
                  onRefineOutput={handleRefineOutput}
                />
              );
            })}
            {Object.values(browserCards).map((bc) => (
              <BrowserCard
                key={`browser-${bc.browser_id}`}
                browserId={bc.browser_id}
                tabs={bc.tabs}
                activeTabId={bc.activeTabId}
                cardX={bc.x}
                cardY={bc.y}
                cardWidth={bc.width}
                cardHeight={bc.height}
                cardZOrder={bc.zOrder ?? 0}
                zoom={canvas.zoom}
                panX={canvas.panX}
                panY={canvas.panY}
                renderPanX={crispPanX}
                renderPanY={crispPanY}
                viewportWidth={canvasViewportSize.width}
                viewportHeight={canvasViewportSize.height}
                cmdHeld={canvas.cmdHeld}
                isSelected={selection.isSelected(bc.browser_id)}
                isHighlighted={highlightedCardId === bc.browser_id}
                multiDragDelta={multiDragDelta}
                onCardSelect={handleCardSelect}
                onDragStart={handleCardDragStart}
                onDragMove={handleCardDragMove}
                onDragEnd={handleCardDragEnd}
                onDoubleClick={handleCardDoubleClick}
                onBringToFront={handleBringToFront}
              />
            ))}
            {Object.values(swarmCards).filter((sc) => !sc.hidden).map((sc) => (
              <ExperimentalSwarmCanvasCard
                key={`swarm-${sc.swarm_card_id}`}
                swarmCardId={sc.swarm_card_id}
                swarmId={sc.swarm_id}
                cardX={sc.x}
                cardY={sc.y}
                cardWidth={sc.width}
                cardHeight={sc.height}
                cardZOrder={sc.zOrder ?? 0}
                collapsed={!!sc.collapsed}
                swarmMode={sc.swarm_mode || 'ask'}
                swarmModel={sc.swarm_model || null}
                previewOutputId={sc.preview_output_id || null}
                skillWorkspaceId={sc.skill_workspace_id || null}
                skillWorkspacePath={sc.skill_workspace_path || null}
                zoom={canvas.zoom}
                isSelected={selection.isSelected(sc.swarm_card_id)}
                isHighlighted={highlightedCardId === sc.swarm_card_id}
                multiDragDelta={multiDragDelta}
                onCardSelect={handleCardSelect}
                onDragStart={handleCardDragStart}
                onDragMove={handleCardDragMove}
                onDragEnd={handleCardDragEnd}
                onBringToFront={handleBringToFront}
                onDoubleClick={handleCardDoubleClick}
                onSwarmBound={persistLayoutNow}
                onAddPreviewCard={handleAddView}
                draftPrompt={swarmDraftPrompts[sc.swarm_card_id] || null}
                onDraftPromptConsumed={() => {
                  setSwarmDraftPrompts((prev) => {
                    if (!prev[sc.swarm_card_id]) return prev;
                    const next = { ...prev };
                    delete next[sc.swarm_card_id];
                    return next;
                  });
                }}
                dashboardId={dashboardId}
              />
            ))}

            {Object.values(plansCards).filter((pc) => !pc.hidden).map((pc) => (
              <PersistentPlansCanvasCard
                key={`plans-${pc.plans_card_id}`}
                plansCardId={pc.plans_card_id}
                cardX={pc.x}
                cardY={pc.y}
                cardWidth={pc.width}
                cardHeight={pc.height}
                cardZOrder={pc.zOrder ?? 0}
                collapsed={!!pc.collapsed}
                dashboardId={dashboardId}
                zoom={canvas.zoom}
                panX={canvas.panX}
                panY={canvas.panY}
                isSelected={selection.isSelected(pc.plans_card_id)}
                isHighlighted={highlightedCardId === pc.plans_card_id}
                multiDragDelta={multiDragDelta}
                onClose={() => dispatch(removePlansCard(pc.plans_card_id))}
                onCardSelect={handleCardSelect}
                onDragStart={handleCardDragStart}
                onDragMove={handleCardDragMove}
                onDragEnd={handleCardDragEnd}
                onBringToFront={handleBringToFront}
                onDoubleClick={handleCardDoubleClick}
                onGoToAgent={handleGoToAgentFromPlans}
              />
            ))}

            {Object.values(notes).map((n) => (
              <NoteCard
                key={`note-${n.note_id}`}
                noteId={n.note_id}
                cardX={n.x}
                cardY={n.y}
                cardWidth={n.width}
                cardHeight={n.height}
                cardZOrder={n.zOrder ?? 0}
                zoom={canvas.zoom}
                panX={canvas.panX}
                panY={canvas.panY}
                cmdHeld={canvas.cmdHeld}
                content={n.content}
                color={n.color}
                isSelected={selection.isSelected(n.note_id)}
                isHighlighted={highlightedCardId === n.note_id}
                multiDragDelta={multiDragDelta}
                autoFocus={pendingFocusNoteId === n.note_id}
                onCardSelect={handleCardSelect}
                onDragStart={handleCardDragStart}
                onDragMove={handleCardDragMove}
                onDragEnd={handleCardDragEnd}
                onBringToFront={handleBringToFront}
              />
            ))}
            {/* Marquee selection rectangle */}
            {selection.marquee && (
              <div
                style={{
                  position: 'absolute',
                  left: selection.marquee.x,
                  top: selection.marquee.y,
                  width: selection.marquee.width,
                  height: selection.marquee.height,
                  border: '1.5px dashed rgba(59, 130, 246, 0.6)',
                  background: 'rgba(59, 130, 246, 0.08)',
                  borderRadius: 2,
                  pointerEvents: 'none',
                  zIndex: 9999,
                }}
              />
            )}
          </div>
        )}
      </Box>

      {/* Floating bottom toolbar */}
      <Box sx={{ position: 'absolute', bottom: 16, left: '50%', transform: 'translateX(-50%)', zIndex: 10 }}>
        <DashboardToolbar
          ref={toolbarRef}
          composerType={toolbarComposer}
          onAddSwarm={handleAddSwarm}
          onNewAgent={handleNewAgent}
          onCancel={handleToolbarCancel}
          onSend={handleToolbarSend}
          onSwarmSend={handleToolbarSwarmSend}
          onAddView={handleAddView}
          onHistoryResume={handleHistoryResume}
          onAddBrowser={handleAddBrowser}
          onAddNote={handleAddNote}
          onAddPlans={handleAddPlans}
          dashboardId={dashboardId}
          newAgentBounce={newAgentBounce}
          onNewAgentBounceEnd={() => setNewAgentBounce(false)}
        />
      </Box>

      {/* Arrow navigation hints when zoomed in on a card */}
      {focusedCardId && canvas.zoom >= 0.4 && (
        <DirectionHints
          hasLeft={neighborDirections.left}
          hasRight={neighborDirections.right}
          hasUp={neighborDirections.up}
          hasDown={neighborDirections.down}
          shakeDirection={shakeDirection}
        />
      )}

      {/* Floating zoom controls + minimap */}
      <Box sx={{ position: 'absolute', bottom: 16, right: 16, zIndex: 10 }}>
        <CanvasControls
          zoom={canvas.zoom}
          actions={canvas.actions}
          onFitToView={handleFitToView}
          onTidy={handleTidy}
          minimapProps={{
            panX: canvas.panX,
            panY: canvas.panY,
            zoom: canvas.zoom,
            viewportRef: canvas.viewportRef,
            cards,
            viewCards,
            browserCards,
            plansCards,
            swarmCards,
            extraRects: orchestrationRects,
          }}
          onMinimapPan={(px, py) => canvas.actions.setState({ panX: px, panY: py, zoom: canvas.zoom })}
        />
      </Box>
    </Box>

    {/* Card search palette (Cmd+F) */}
    <CardSearchPalette
      open={searchPaletteOpen}
      onClose={() => setSearchPaletteOpen(false)}
      onNavigate={(rect) => canvas.actions.fitToCards([rect], 1.15, true)}
      cards={cards}
      viewCards={viewCards}
      browserCards={browserCards}
      sessions={sessions}
    />

    {/* Onboarding walkthrough overlay */}
    {showWalkthrough && (
      <OnboardingWalkthrough onComplete={handleWalkthroughComplete} />
    )}
    </>
  );
};

const Dashboard: React.FC<DashboardProps> = ({ dashboardId, isActive = true }) => (
  <ElementSelectionProvider>
    <DashboardInner dashboardId={dashboardId} isActive={isActive} />
  </ElementSelectionProvider>
);

export default Dashboard;
