import { mergeCanvasBounds, rectsOverlap, type CanvasRect } from '@/shared/layout/canvasFreeSlotResolver';

export type CanvasProceduralNodeStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'skipped'
  | 'waiting_approval'
  | 'blocked'
  | 'next_to_run'
  | string;

export type CanvasProceduralLiveStateTone =
  | 'neutral'
  | 'active'
  | 'attention'
  | 'success'
  | 'danger'
  | 'muted';

export interface CanvasProceduralLiveStateMeta {
  tone: CanvasProceduralLiveStateTone;
  label: string;
  description: string;
  active: boolean;
  attention: boolean;
  terminal: boolean;
  dimmed: boolean;
  pulse: boolean;
  glow: boolean;
}

export function resolveProceduralLiveExecutionState(
  status: CanvasProceduralNodeStatus | undefined,
): CanvasProceduralLiveStateMeta {
  const normalized = normalizeStatus(status);

  if (normalized === 'running') {
    return {
      tone: 'active',
      label: 'Ejecutando',
      description: 'El nodo está ejecutando una tarea, tool o subpaso activo.',
      active: true,
      attention: false,
      terminal: false,
      dimmed: false,
      pulse: true,
      glow: true,
    };
  }

  if (normalized === 'next_to_run') {
    return {
      tone: 'active',
      label: 'Siguiente',
      description: 'El nodo está marcado como próximo paso del flujo.',
      active: true,
      attention: false,
      terminal: false,
      dimmed: false,
      pulse: false,
      glow: true,
    };
  }

  if (normalized === 'waiting_approval' || normalized === 'blocked') {
    return {
      tone: 'attention',
      label: normalized === 'waiting_approval' ? 'Esperando aprobación' : 'Bloqueado',
      description: 'El nodo requiere aprobación, desbloqueo o una acción humana antes de continuar.',
      active: true,
      attention: true,
      terminal: false,
      dimmed: false,
      pulse: true,
      glow: true,
    };
  }

  if (normalized === 'completed') {
    return {
      tone: 'success',
      label: 'Completado',
      description: 'El nodo terminó correctamente.',
      active: false,
      attention: false,
      terminal: true,
      dimmed: false,
      pulse: false,
      glow: false,
    };
  }

  if (normalized === 'failed') {
    return {
      tone: 'danger',
      label: 'Falló',
      description: 'El nodo terminó con error y requiere revisión.',
      active: false,
      attention: true,
      terminal: true,
      dimmed: false,
      pulse: false,
      glow: true,
    };
  }

  if (normalized === 'skipped') {
    return {
      tone: 'muted',
      label: 'Omitido',
      description: 'El nodo fue omitido por el flujo actual.',
      active: false,
      attention: false,
      terminal: true,
      dimmed: true,
      pulse: false,
      glow: false,
    };
  }

  return {
    tone: 'neutral',
    label: 'Pendiente',
    description: 'El nodo está pendiente de ejecución.',
    active: false,
    attention: false,
    terminal: false,
    dimmed: false,
    pulse: false,
    glow: false,
  };
}

export interface CanvasProceduralSwarmAnchor {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface CanvasProceduralSwarmNode {
  id: string;
  label?: string | null;
  role?: string | null;
  status?: CanvasProceduralNodeStatus;
  width?: number;
  height?: number;
  x?: number;
  y?: number;
}

export interface CanvasProceduralSwarmLayoutOptions {
  lane?: 'right' | 'left' | 'below';
  gap?: number;
  nodeWidth?: number;
  nodeHeight?: number;
  columns?: number;
  preserveManualPositions?: boolean;
}

export interface CanvasProceduralSwarmLayoutNode extends CanvasProceduralSwarmNode {
  x: number;
  y: number;
  width: number;
  height: number;
  procedural_lane: 'right' | 'left' | 'below';
  procedural_order: number;
  procedural_active: boolean;
  procedural_live_state: CanvasProceduralLiveStateMeta;
}

export interface CanvasProceduralSwarmLayoutResult {
  anchor: CanvasProceduralSwarmAnchor;
  lane: 'right' | 'left' | 'below';
  nodes: CanvasProceduralSwarmLayoutNode[];
  bounds: CanvasRect | null;
  focusRect: CanvasRect | null;
}

const DEFAULT_GAP = 24;
const DEFAULT_NODE_W = 180;
const DEFAULT_NODE_H = 96;
const DEFAULT_COLUMNS = 2;

function normalizeStatus(status: CanvasProceduralNodeStatus | undefined): string {
  return String(status || 'pending').trim().toLowerCase();
}

function isActiveStatus(status: CanvasProceduralNodeStatus | undefined): boolean {
  const normalized = normalizeStatus(status);
  return normalized === 'running' || normalized === 'next_to_run' || normalized === 'waiting_approval' || normalized === 'blocked';
}

function laneOrigin(
  anchor: CanvasProceduralSwarmAnchor,
  lane: 'right' | 'left' | 'below',
  gap: number,
  nodeWidth: number,
): { x: number; y: number } {
  if (lane === 'left') {
    return { x: anchor.x - gap - nodeWidth, y: anchor.y };
  }
  if (lane === 'below') {
    return { x: anchor.x, y: anchor.y + anchor.height + gap };
  }
  return { x: anchor.x + anchor.width + gap, y: anchor.y };
}

function nextCandidatePosition(params: {
  anchor: CanvasProceduralSwarmAnchor;
  lane: 'right' | 'left' | 'below';
  index: number;
  columns: number;
  gap: number;
  nodeWidth: number;
  nodeHeight: number;
}): { x: number; y: number } {
  const origin = laneOrigin(params.anchor, params.lane, params.gap, params.nodeWidth);
  const row = Math.floor(params.index / params.columns);
  const column = params.index % params.columns;
  const direction = params.lane === 'left' ? -1 : 1;
  const xStep = params.nodeWidth + params.gap;
  const yStep = params.nodeHeight + params.gap;

  if (params.lane === 'below') {
    return {
      x: origin.x + column * xStep,
      y: origin.y + row * yStep,
    };
  }

  return {
    x: origin.x + column * xStep * direction,
    y: origin.y + row * yStep,
  };
}

function findProceduralSlot(params: {
  anchor: CanvasProceduralSwarmAnchor;
  lane: 'right' | 'left' | 'below';
  order: number;
  occupiedRects: CanvasRect[];
  placedRects: CanvasRect[];
  columns: number;
  gap: number;
  nodeWidth: number;
  nodeHeight: number;
}): { x: number; y: number } {
  let candidateIndex = params.order;
  for (let attempts = 0; attempts < 120; attempts += 1) {
    const position = nextCandidatePosition({ ...params, index: candidateIndex });
    const candidate: CanvasRect = { x: position.x, y: position.y, w: params.nodeWidth, h: params.nodeHeight };
    const blocked = [...params.occupiedRects, ...params.placedRects].some((rect) => rectsOverlap(candidate, rect));
    if (!blocked) return position;
    candidateIndex += 1;
  }

  return nextCandidatePosition({ ...params, index: candidateIndex });
}

export function resolveProceduralSwarmClusterLayout(params: {
  anchor: CanvasProceduralSwarmAnchor;
  nodes: CanvasProceduralSwarmNode[];
  occupiedRects?: CanvasRect[];
  options?: CanvasProceduralSwarmLayoutOptions;
}): CanvasProceduralSwarmLayoutResult {
  const gap = Math.max(8, params.options?.gap ?? DEFAULT_GAP);
  const nodeWidth = Math.max(120, params.options?.nodeWidth ?? DEFAULT_NODE_W);
  const nodeHeight = Math.max(72, params.options?.nodeHeight ?? DEFAULT_NODE_H);
  const columns = Math.max(1, params.options?.columns ?? DEFAULT_COLUMNS);
  const lane = params.options?.lane ?? 'right';
  const occupiedRects = params.occupiedRects ?? [];
  const placedRects: CanvasRect[] = [];

  const nodes = params.nodes.map((node, index): CanvasProceduralSwarmLayoutNode => {
    const width = Math.max(120, node.width ?? nodeWidth);
    const height = Math.max(72, node.height ?? nodeHeight);
    const keepManual = Boolean(
      params.options?.preserveManualPositions &&
      typeof node.x === 'number' &&
      typeof node.y === 'number',
    );
    const position = keepManual
      ? { x: node.x as number, y: node.y as number }
      : findProceduralSlot({
          anchor: params.anchor,
          lane,
          order: index,
          occupiedRects,
          placedRects,
          columns,
          gap,
          nodeWidth: width,
          nodeHeight: height,
        });

    placedRects.push({ x: position.x, y: position.y, w: width, h: height });

    return {
      ...node,
      x: position.x,
      y: position.y,
      width,
      height,
      procedural_lane: lane,
      procedural_order: index,
      procedural_active: isActiveStatus(node.status),
      procedural_live_state: resolveProceduralLiveExecutionState(node.status),
    };
  });

  const nodeRects = nodes.map((node) => ({ x: node.x, y: node.y, w: node.width, h: node.height }));
  const bounds = mergeCanvasBounds([{ x: params.anchor.x, y: params.anchor.y, w: params.anchor.width, h: params.anchor.height }, ...nodeRects]);
  const activeRects = nodes
    .filter((node) => node.procedural_active)
    .map((node) => ({ x: node.x, y: node.y, w: node.width, h: node.height }));

  return {
    anchor: params.anchor,
    lane,
    nodes,
    bounds,
    focusRect: mergeCanvasBounds(activeRects.length ? activeRects : nodeRects),
  };
}
