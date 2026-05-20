import React, { useRef, useCallback, useMemo } from 'react';
import { useClaudeTokens } from '@/shared/styles/ThemeContext';
import type {
  CardPosition,
  ViewCardPosition,
  BrowserCardPosition,
  PlansCardPosition,
  SwarmCardPosition,
} from '@/shared/state/dashboardLayoutSlice';

const MINIMAP_W = 200;
const MINIMAP_H = 140;
const PADDING = 20;

export interface MinimapProps {
  panX: number;
  panY: number;
  zoom: number;
  viewportRef: React.RefObject<HTMLDivElement | null>;
  cards: Record<string, CardPosition>;
  viewCards: Record<string, ViewCardPosition>;
  browserCards: Record<string, BrowserCardPosition>;
  plansCards: Record<string, PlansCardPosition>;
  swarmCards: Record<string, SwarmCardPosition>;
  extraRects?: Array<{ x: number; y: number; width: number; height: number; type?: 'orchestration' }>;
  onPan: (panX: number, panY: number) => void;
}

interface CardRect {
  x: number;
  y: number;
  width: number;
  height: number;
  type: 'agent' | 'view' | 'browser' | 'plans' | 'swarm' | 'orchestration';
}

const Minimap: React.FC<MinimapProps> = ({
  panX, panY, zoom, viewportRef,
  cards, viewCards, browserCards, plansCards, swarmCards, extraRects = [],
  onPan,
}) => {
  const c = useClaudeTokens();
  const svgRef = useRef<SVGSVGElement>(null);
  const isDraggingRef = useRef(false);

  const allCards = useMemo((): CardRect[] => {
    const result: CardRect[] = [];
    for (const card of Object.values(cards)) {
      result.push({ x: card.x, y: card.y, width: card.width, height: card.height, type: 'agent' });
    }
    for (const vc of Object.values(viewCards)) {
      result.push({ x: vc.x, y: vc.y, width: vc.width, height: vc.height, type: 'view' });
    }
    for (const bc of Object.values(browserCards)) {
      result.push({ x: bc.x, y: bc.y, width: bc.width, height: bc.height, type: 'browser' });
    }
    for (const pc of Object.values(plansCards)) {
      if (!pc.hidden) {
        result.push({ x: pc.x, y: pc.y, width: pc.width, height: pc.height, type: 'plans' });
      }
    }
    for (const sc of Object.values(swarmCards)) {
      if (!sc.hidden) {
        result.push({ x: sc.x, y: sc.y, width: sc.width, height: sc.height, type: 'swarm' });
      }
    }
    for (const rect of extraRects) {
      result.push({ ...rect, type: rect.type || 'orchestration' });
    }
    return result;
  }, [cards, viewCards, browserCards, plansCards, swarmCards, extraRects]);

  const layout = useMemo(() => {
    const vp = viewportRef.current;
    const vpW = vp ? vp.clientWidth : 1200;
    const vpH = vp ? vp.clientHeight : 800;

    const vpRect = {
      x: -panX / zoom,
      y: -panY / zoom,
      width: vpW / zoom,
      height: vpH / zoom,
    };

    if (allCards.length === 0) {
      const scale = Math.min(
        (MINIMAP_W - PADDING * 2) / vpRect.width,
        (MINIMAP_H - PADDING * 2) / vpRect.height,
      );
      return {
        scale,
        offsetX: MINIMAP_W / 2 - (vpRect.x + vpRect.width / 2) * scale,
        offsetY: MINIMAP_H / 2 - (vpRect.y + vpRect.height / 2) * scale,
        vpRect,
      };
    }

    let minX = vpRect.x, minY = vpRect.y;
    let maxX = vpRect.x + vpRect.width, maxY = vpRect.y + vpRect.height;
    for (const card of allCards) {
      minX = Math.min(minX, card.x);
      minY = Math.min(minY, card.y);
      maxX = Math.max(maxX, card.x + card.width);
      maxY = Math.max(maxY, card.y + card.height);
    }

    const contentW = maxX - minX;
    const contentH = maxY - minY;
    const scale = Math.min(
      (MINIMAP_W - PADDING * 2) / contentW,
      (MINIMAP_H - PADDING * 2) / contentH,
    );
    return {
      scale,
      offsetX: (MINIMAP_W - contentW * scale) / 2 - minX * scale,
      offsetY: (MINIMAP_H - contentH * scale) / 2 - minY * scale,
      vpRect,
    };
  }, [allCards, panX, panY, zoom, viewportRef]);

  const minimapToCanvas = useCallback((clientX: number, clientY: number) => {
    const svg = svgRef.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const mx = clientX - rect.left;
    const my = clientY - rect.top;
    const canvasX = (mx - layout.offsetX) / layout.scale;
    const canvasY = (my - layout.offsetY) / layout.scale;
    onPan(
      -(canvasX - layout.vpRect.width / 2) * zoom,
      -(canvasY - layout.vpRect.height / 2) * zoom,
    );
  }, [layout, zoom, onPan]);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    isDraggingRef.current = true;
    minimapToCanvas(e.clientX, e.clientY);

    const onMove = (ev: MouseEvent) => {
      if (isDraggingRef.current) minimapToCanvas(ev.clientX, ev.clientY);
    };
    const onUp = () => {
      isDraggingRef.current = false;
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }, [minimapToCanvas]);

  const typeColor = (type: CardRect['type']) => {
    switch (type) {
      case 'agent': return c.accent.primary;
      case 'view': return c.status.info;
      case 'browser': return c.status.success;
      case 'plans': return c.status.warning;
      case 'swarm': return c.status.error;
      case 'orchestration': return c.accent.hover;
    }
  };

  return (
    <svg
      ref={svgRef}
      width={MINIMAP_W}
      height={MINIMAP_H}
      onMouseDown={handleMouseDown}
      style={{ cursor: 'pointer', display: 'block' }}
    >
      {allCards.map((card, i) => (
        <rect
          key={i}
          x={card.x * layout.scale + layout.offsetX}
          y={card.y * layout.scale + layout.offsetY}
          width={card.width * layout.scale}
          height={card.height * layout.scale}
          fill={typeColor(card.type)}
          opacity={0.6}
          rx={1}
        />
      ))}
      <rect
        x={layout.vpRect.x * layout.scale + layout.offsetX}
        y={layout.vpRect.y * layout.scale + layout.offsetY}
        width={layout.vpRect.width * layout.scale}
        height={layout.vpRect.height * layout.scale}
        fill="none"
        stroke={c.accent.primary}
        strokeWidth={1.5}
        opacity={0.8}
        rx={1}
      />
    </svg>
  );
};

export default Minimap;
