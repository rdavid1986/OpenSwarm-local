import React, { useCallback, useMemo, useRef, useState } from 'react';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Typography from '@mui/material/Typography';
import { useClaudeTokens } from '@/shared/styles/ThemeContext';

type OrchestrationNodeStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'skipped'
  | 'waiting_approval'
  | 'draft'
  | 'verified'
  | 'unverified'
  | string;

export interface OrchestrationCanvasNode {
  id: string;
  label: string;
  role?: string | null;
  status?: OrchestrationNodeStatus;
  description?: string | null;
  assigned_agent_role?: string | null;
  assigned_contract_id?: string | null;
  allowed_tools?: string[];
  model?: string | null;
  artifact_ref?: string | null;
  evidence_ref?: string | null;
  expanded?: boolean;
  x: number;
  y: number;
  width?: number;
  height?: number;
}

export interface OrchestrationCanvasEdge {
  id: string;
  from: string;
  to: string;
  label?: string | null;
}

export interface OrchestrationCanvasState {
  status?: string;
  source?: string;
  linked_swarm_id?: string | null;
  nodes?: OrchestrationCanvasNode[];
  edges?: OrchestrationCanvasEdge[];
}

interface Props {
  state?: OrchestrationCanvasState | null;
  zoom?: number;
  onNodeMoveEnd?: (nodeId: string, x: number, y: number) => void;
  onNodeExpandedChange?: (nodeId: string, expanded: boolean) => void;
  onNodeDoubleClick?: (node: OrchestrationCanvasNode) => void;
}

const NODE_W = 180;
const NODE_H = 96;
const NODE_EXPANDED_H = 172;
const CLICK_DRAG_THRESHOLD = 4;

const SwarmOrchestrationPreview: React.FC<Props> = ({ state, zoom = 1, onNodeMoveEnd, onNodeExpandedChange, onNodeDoubleClick }) => {
  const c = useClaudeTokens();
  const [dragNodeId, setDragNodeId] = useState<string | null>(null);
  const [localNodePositions, setLocalNodePositions] = useState<Record<string, { x: number; y: number }>>({});
  const dragRef = useRef<{
    nodeId: string;
    startClientX: number;
    startClientY: number;
    startX: number;
    startY: number;
    moved: boolean;
  } | null>(null);
  const clickTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const nodes = useMemo(() => (Array.isArray(state?.nodes) ? state?.nodes || [] : []), [state]);
  const edges = useMemo(() => (Array.isArray(state?.edges) ? state?.edges || [] : []), [state]);
  const displayedNodes = useMemo(
    () => nodes.map((node) => ({ ...node, ...(localNodePositions[node.id] || {}) })),
    [nodes, localNodePositions],
  );
  const nodeById = useMemo(() => new Map(displayedNodes.map((node) => [node.id, node])), [displayedNodes]);

  const handleNodePointerDown = useCallback((node: OrchestrationCanvasNode) => (e: React.PointerEvent) => {
    e.stopPropagation();
    e.preventDefault();
    const current = localNodePositions[node.id] || { x: node.x, y: node.y };
    dragRef.current = {
      nodeId: node.id,
      startClientX: e.clientX,
      startClientY: e.clientY,
      startX: current.x,
      startY: current.y,
      moved: false,
    };
    setDragNodeId(node.id);
    (e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId);
  }, [localNodePositions]);

  const handleNodePointerMove = useCallback((e: React.PointerEvent) => {
    const drag = dragRef.current;
    if (!drag) return;
    e.stopPropagation();
    const rawDx = e.clientX - drag.startClientX;
    const rawDy = e.clientY - drag.startClientY;
    drag.moved = drag.moved || Math.abs(rawDx) > CLICK_DRAG_THRESHOLD || Math.abs(rawDy) > CLICK_DRAG_THRESHOLD;
    const nextX = Math.round(drag.startX + rawDx / zoom);
    const nextY = Math.round(drag.startY + rawDy / zoom);
    setLocalNodePositions((prev) => ({
      ...prev,
      [drag.nodeId]: { x: nextX, y: nextY },
    }));
  }, [zoom]);

  const handleNodePointerUp = useCallback((e: React.PointerEvent) => {
    const drag = dragRef.current;
    if (!drag) return;
    e.stopPropagation();
    const finalPos = localNodePositions[drag.nodeId] || { x: drag.startX, y: drag.startY };
    const wasMoved = drag.moved;
    const node = displayedNodes.find((item) => item.id === drag.nodeId);
    dragRef.current = null;
    setDragNodeId(null);

    if (wasMoved) {
      onNodeMoveEnd?.(drag.nodeId, finalPos.x, finalPos.y);
      return;
    }

    if (node) {
      if (clickTimerRef.current) {
        clearTimeout(clickTimerRef.current);
        clickTimerRef.current = null;
      }
      clickTimerRef.current = setTimeout(() => {
        clickTimerRef.current = null;
        onNodeExpandedChange?.(drag.nodeId, !Boolean(node.expanded));
      }, 220);
    }
  }, [displayedNodes, localNodePositions, onNodeExpandedChange, onNodeMoveEnd]);

  if (nodes.length === 0) return null;

  const getStatusMeta = (status?: string) => {
    switch (status) {
      case 'running':
        return { label: 'Ejecutando', color: c.status.info, description: 'Nodo en ejecución. La tarea o tool asociada está corriendo.' };
      case 'completed':
        return { label: 'Completado', color: c.status.success, description: 'Nodo completado correctamente.' };
      case 'failed':
        return { label: 'Falló', color: c.status.error, description: 'Nodo fallido. Revisá la actividad reciente para ver el detalle.' };
      case 'skipped':
        return { label: 'Omitido', color: c.text.muted, description: 'Nodo omitido por el flujo de orquestación.' };
      case 'waiting_approval':
        return { label: 'Esperando aprobación', color: c.status.warning, description: 'Nodo pausado hasta recibir aprobación.' };
      case 'draft':
        return { label: 'Borrador', color: c.text.tertiary, description: 'Nodo planificado como borrador; todavía no fue ejecutado.' };
      case 'verified':
        return { label: 'Verificado', color: c.status.success, description: 'Nodo verificado con evidencia asociada.' };
      case 'unverified':
        return { label: 'No verificado', color: c.status.warning, description: 'Nodo completado o evaluado, pero la evidencia no quedó verificada.' };
      case 'pending':
      default:
        return {
          label: status && status !== 'pending' ? status : 'Pendiente',
          color: c.text.tertiary,
          description: 'Esperando inicio de ejecución. No se ejecutaron tools ni DAG.',
        };
    }
  };

  return (
    <Box sx={{ position: 'absolute', left: 0, top: 0, pointerEvents: 'none', zIndex: 6 }}>
      <svg
        style={{ position: 'absolute', left: 0, top: 0, width: 1, height: 1, overflow: 'visible' }}
      >
        <defs>
          <marker id="orchestration-arrow" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="8" markerHeight="8" orient="auto">
            <path d="M 0 1 L 10 5 L 0 9 z" fill={c.accent.primary} opacity="0.65" />
          </marker>
        </defs>
        {edges.map((edge) => {
          const from = nodeById.get(edge.from);
          const to = nodeById.get(edge.to);
          if (!from || !to) return null;
          const fromW = from.width || NODE_W;
          const fromH = from.height || NODE_H;
          const toH = to.height || NODE_H;
          const x1 = from.x + fromW;
          const y1 = from.y + fromH / 2;
          const x2 = to.x;
          const y2 = to.y + toH / 2;
          const midX = x1 + Math.max(40, (x2 - x1) / 2);
          return (
            <path
              key={edge.id}
              d={`M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`}
              fill="none"
              stroke={c.accent.primary}
              strokeWidth={2}
              strokeDasharray="8 8"
              opacity={0.45}
              markerEnd="url(#orchestration-arrow)"
            />
          );
        })}
      </svg>

      {displayedNodes.map((node) => {
        const width = node.width || NODE_W;
        const height = node.expanded ? NODE_EXPANDED_H : (node.height || NODE_H);
        const status = node.status || 'pending';
        const statusMeta = getStatusMeta(status);
        return (
          <Box
            key={node.id}
            onDoubleClick={(e) => {
              e.stopPropagation();
              if (clickTimerRef.current) {
                clearTimeout(clickTimerRef.current);
                clickTimerRef.current = null;
              }
              onNodeDoubleClick?.(node);
            }}
            sx={{
              position: 'absolute',
              left: node.x,
              top: node.y,
              width,
              minHeight: height,
              p: 1.25,
              borderRadius: 2,
              bgcolor: c.bg.surface,
              border: `1px solid ${statusMeta.color}`,
              boxShadow: c.shadow.lg,
              opacity: 0.96,
              pointerEvents: 'auto',
              userSelect: 'none',
            }}
          >
            <Box
              onPointerDown={handleNodePointerDown(node)}
              onPointerMove={handleNodePointerMove}
              onPointerUp={handleNodePointerUp}
              onPointerCancel={handleNodePointerUp}
              sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 1,
                mb: 0.75,
                cursor: dragNodeId === node.id ? 'grabbing' : 'grab',
                touchAction: 'none',
              }}
            >
              <Typography sx={{ color: c.text.primary, fontSize: 13, fontWeight: 700, lineHeight: 1.2 }}>
                {node.label}
              </Typography>
              <Chip
                size="small"
                label={statusMeta.label}
                sx={{
                  height: 18,
                  fontSize: 10,
                  color: statusMeta.color,
                  bgcolor: `${statusMeta.color}22`,
                }}
              />
            </Box>
            {node.role && (
              <Typography sx={{ color: c.accent.primary, fontSize: 11, fontWeight: 600, mb: 0.5 }}>
                {node.role}
              </Typography>
            )}
            {node.assigned_agent_role && (
              <Typography sx={{ color: c.text.tertiary, fontSize: 10.5, mb: 0.5 }} noWrap>
                agent: {node.assigned_agent_role}
              </Typography>
            )}
            {node.description && (
              <Typography sx={{ color: c.text.secondary, fontSize: 11, lineHeight: 1.25 }} noWrap={!node.expanded}>
                {node.description}
              </Typography>
            )}
            {node.expanded && (
              <Box sx={{ mt: 0.85, pt: 0.75, borderTop: `1px solid ${c.border.subtle}` }}>
                <Typography sx={{ color: c.text.tertiary, fontSize: 10, mb: 0.35 }}>
                  Estado operativo
                </Typography>
                <Typography sx={{ color: c.text.secondary, fontSize: 11, lineHeight: 1.35 }}>
                  {statusMeta.description}
                </Typography>
              </Box>
            )}
            {node.model && (
              <Typography sx={{ color: c.text.tertiary, fontSize: 10, mt: 0.5 }} noWrap>
                model: {node.model}
              </Typography>
            )}
            {Array.isArray(node.allowed_tools) && node.allowed_tools.length > 0 && (
              <Typography sx={{ color: c.text.tertiary, fontSize: 10, mt: 0.5 }} noWrap>
                tools: {node.allowed_tools.join(', ')}
              </Typography>
            )}
            {(node.artifact_ref || node.evidence_ref) && (
              <Typography sx={{ color: c.text.tertiary, fontSize: 10, mt: 0.5 }} noWrap>
                {node.artifact_ref ? `artifact: ${node.artifact_ref}` : `evidence: ${node.evidence_ref}`}
              </Typography>
            )}
          </Box>
        );
      })}
    </Box>
  );
};

export default SwarmOrchestrationPreview;
