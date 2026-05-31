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

function normalizeCanvasStatus(status?: string | null): string {
  const raw = String(status || 'pending').trim().toLowerCase();
  if (!raw) return 'pending';
  if (raw === 'error') return 'failed';
  if (raw === 'waiting' || raw === 'queued') return 'waiting';
  if (raw === 'waiting_approval' || raw === 'requires_approval') return 'blocked';
  return raw;
}

function buildEdgeMarkerId(edgeId: string): string {
  return `orchestration-arrow-${String(edgeId || 'edge').replace(/[^a-zA-Z0-9_-]/g, '-')}`;
}

function isAttentionCanvasStatus(status: string): boolean {
  return ['needs_context', 'needs_review', 'needs_skill', 'blocked', 'failed', 'unverified'].includes(status);
}

function isActiveCanvasStatus(status: string): boolean {
  return ['running', 'next_to_run'].includes(status);
}

function humanizeCanvasStatusLabel(status: string): string {
  return status.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());
}

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

  const getStatusMeta = useCallback((status?: string) => {
    const normalized = normalizeCanvasStatus(status);

    if (normalized === 'running') {
      return {
        label: 'Ejecutando',
        color: c.status.warning,
        border: `${c.status.warning}AA`,
        bg: `${c.status.warning}10`,
        description: 'Nodo en ejecución. La tarea o tool asociada está corriendo.',
        active: true,
        attention: false,
      };
    }
    if (normalized === 'next_to_run') {
      return {
        label: 'Siguiente',
        color: c.status.info,
        border: `${c.status.info}AA`,
        bg: `${c.status.info}10`,
        description: 'Nodo marcado como próximo paso del flujo.',
        active: true,
        attention: false,
      };
    }
    if (normalized === 'completed' || normalized === 'verified') {
      return {
        label: normalized === 'verified' ? 'Verificado' : 'Completado',
        color: c.status.success,
        border: `${c.status.success}88`,
        bg: `${c.status.success}0D`,
        description: normalized === 'verified' ? 'Nodo verificado con evidencia asociada.' : 'Nodo completado correctamente.',
        active: false,
        attention: false,
      };
    }
    if (normalized === 'needs_context') {
      return {
        label: 'Necesita contexto',
        color: c.accent.primary,
        border: `${c.accent.primary}AA`,
        bg: `${c.accent.primary}10`,
        description: 'Nodo pausado porque necesita contexto adicional real.',
        active: false,
        attention: true,
      };
    }
    if (normalized === 'needs_review') {
      return {
        label: 'Requiere revisión',
        color: '#a78bfa',
        border: '#a78bfaAA',
        bg: '#a78bfa14',
        description: 'Nodo requiere revisión humana o validación antes de continuar.',
        active: false,
        attention: true,
      };
    }
    if (normalized === 'needs_skill') {
      return {
        label: 'Necesita skill',
        color: c.status.warning,
        border: `${c.status.warning}AA`,
        bg: `${c.status.warning}12`,
        description: 'Nodo requiere una skill o capacidad adicional antes de ejecutarse.',
        active: false,
        attention: true,
      };
    }
    if (normalized === 'blocked') {
      return {
        label: 'Bloqueado',
        color: c.status.warning,
        border: `${c.status.warning}AA`,
        bg: `${c.status.warning}12`,
        description: 'Nodo bloqueado por aprobación, dependencia o falta de datos.',
        active: false,
        attention: true,
      };
    }
    if (normalized === 'failed') {
      return {
        label: 'Falló',
        color: c.status.error,
        border: `${c.status.error}AA`,
        bg: `${c.status.error}10`,
        description: 'Nodo fallido. Revisá la actividad reciente para ver el detalle.',
        active: false,
        attention: true,
      };
    }
    if (normalized === 'skipped') {
      return {
        label: 'Omitido',
        color: c.text.ghost,
        border: `${c.text.ghost}66`,
        bg: `${c.text.ghost}10`,
        description: 'Nodo omitido por el flujo de orquestación.',
        active: false,
        attention: false,
      };
    }
    if (normalized === 'unverified') {
      return {
        label: 'No verificado',
        color: c.status.warning,
        border: `${c.status.warning}88`,
        bg: `${c.status.warning}10`,
        description: 'Nodo completado o evaluado, pero la evidencia no quedó verificada.',
        active: false,
        attention: true,
      };
    }

    return {
      label: normalized === 'pending' ? 'Pendiente' : humanizeCanvasStatusLabel(normalized),
      color: c.text.tertiary,
      border: `${c.text.tertiary}66`,
      bg: `${c.bg.secondary}66`,
      description: 'Esperando inicio de ejecución. No se ejecutaron tools ni DAG.',
      active: false,
      attention: false,
    };
  }, [c]);

  const getEdgeMeta = useCallback((edge: OrchestrationCanvasEdge) => {
    const from = nodeById.get(edge.from);
    const to = nodeById.get(edge.to);
    const fromStatus = normalizeCanvasStatus(from?.status);
    const toStatus = normalizeCanvasStatus(to?.status);
    const active = isActiveCanvasStatus(fromStatus) || isActiveCanvasStatus(toStatus);
    const attention = isAttentionCanvasStatus(fromStatus) || isAttentionCanvasStatus(toStatus);

    if (fromStatus === 'failed' || toStatus === 'failed') {
      return { color: c.status.error, opacity: 0.78, dash: '5 5', active: false, attention: true };
    }
    if (attention) {
      return { color: c.status.warning, opacity: 0.72, dash: '6 6', active: false, attention: true };
    }
    if (active) {
      return { color: c.status.warning, opacity: 0.88, dash: '8 8', active: true, attention: false };
    }
    if (fromStatus === 'completed' || fromStatus === 'verified') {
      return { color: c.status.success, opacity: 0.64, dash: '0', active: false, attention: false };
    }
    return { color: c.text.tertiary, opacity: 0.42, dash: '8 8', active: false, attention: false };
  }, [c, nodeById]);

  return (
    <Box
      sx={{
        position: 'absolute',
        left: 0,
        top: 0,
        pointerEvents: 'none',
        zIndex: 6,
        '@keyframes swarm-node-glow': {
          '0%, 100%': { boxShadow: '0 0 0 1px rgba(245, 158, 11, 0.22), 0 0 12px rgba(245, 158, 11, 0.16)' },
          '50%': { boxShadow: '0 0 0 1px rgba(245, 158, 11, 0.42), 0 0 24px rgba(245, 158, 11, 0.28)' },
        },
        '@keyframes swarm-edge-dash': {
          from: { strokeDashoffset: 24 },
          to: { strokeDashoffset: 0 },
        },
      }}
    >
      <svg
        style={{ position: 'absolute', left: 0, top: 0, width: 1, height: 1, overflow: 'visible' }}
      >
        <defs>
          {edges.map((edge) => {
            const from = nodeById.get(edge.from);
            const to = nodeById.get(edge.to);
            if (!from || !to) return null;
            const edgeMeta = getEdgeMeta(edge);
            return (
              <marker
                key={`marker-${edge.id}`}
                id={buildEdgeMarkerId(edge.id)}
                viewBox="0 0 10 10"
                refX="10"
                refY="5"
                markerWidth="8"
                markerHeight="8"
                orient="auto"
              >
                <path d="M 0 1 L 10 5 L 0 9 z" fill={edgeMeta.color} opacity={edgeMeta.opacity} />
              </marker>
            );
          })}
        </defs>
        {edges.map((edge) => {
          const from = nodeById.get(edge.from);
          const to = nodeById.get(edge.to);
          if (!from || !to) return null;
          const fromW = from.width || NODE_W;
          const fromH = from.expanded ? NODE_EXPANDED_H : (from.height || NODE_H);
          const toH = to.expanded ? NODE_EXPANDED_H : (to.height || NODE_H);
          const x1 = from.x + fromW;
          const y1 = from.y + fromH / 2;
          const x2 = to.x;
          const y2 = to.y + toH / 2;
          const midX = x1 + Math.max(40, (x2 - x1) / 2);
          const edgeMeta = getEdgeMeta(edge);
          return (
            <path
              key={edge.id}
              d={`M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`}
              fill="none"
              stroke={edgeMeta.color}
              strokeWidth={edgeMeta.active ? 2.5 : 2}
              strokeDasharray={edgeMeta.dash}
              opacity={edgeMeta.opacity}
              markerEnd={`url(#${buildEdgeMarkerId(edge.id)})`}
              style={{
                animation: edgeMeta.active ? 'swarm-edge-dash 1.6s linear infinite' : undefined,
              }}
            />
          );
        })}
      </svg>

      {displayedNodes.map((node) => {
        const width = node.width || NODE_W;
        const height = node.expanded ? NODE_EXPANDED_H : (node.height || NODE_H);
        const status = normalizeCanvasStatus(node.status || 'pending');
        const statusMeta = getStatusMeta(status);
        const attentionChips = [
          ...(statusMeta.attention ? [{ label: statusMeta.label, color: statusMeta.color }] : []),
          ...(node.evidence_ref ? [{ label: 'evidence', color: c.status.success }] : []),
          ...(node.artifact_ref ? [{ label: 'artifact', color: c.status.success }] : []),
          ...(Array.isArray(node.allowed_tools) && node.allowed_tools.length > 0 ? [{ label: `tools:${node.allowed_tools.length}`, color: c.status.info }] : []),
          ...(node.model ? [{ label: 'model', color: c.text.tertiary }] : []),
        ];
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
              bgcolor: statusMeta.bg,
              border: `1px solid ${statusMeta.border}`,
              boxShadow: statusMeta.active
                ? `0 0 0 1px ${statusMeta.color}33, 0 0 20px ${statusMeta.color}24`
                : statusMeta.attention
                  ? `0 0 0 1px ${statusMeta.color}22, 0 0 14px ${statusMeta.color}16`
                  : c.shadow.lg,
              animation: statusMeta.active ? 'swarm-node-glow 2.4s ease-in-out infinite' : 'none',
              opacity: status === 'skipped' ? 0.72 : 0.97,
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
                  bgcolor: statusMeta.bg,
                  border: `1px solid ${statusMeta.border}`,
                }}
              />
            </Box>
            {attentionChips.length > 0 && (
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.35, mb: 0.6 }}>
                {attentionChips.slice(0, 5).map((chip) => (
                  <Chip
                    key={`${node.id}-${chip.label}`}
                    size="small"
                    label={chip.label}
                    sx={{
                      height: 17,
                      maxWidth: 112,
                      fontSize: 9.5,
                      color: chip.color,
                      bgcolor: `${chip.color}12`,
                      '& .MuiChip-label': { px: 0.55, overflow: 'hidden', textOverflow: 'ellipsis' },
                    }}
                  />
                ))}
              </Box>
            )}
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
