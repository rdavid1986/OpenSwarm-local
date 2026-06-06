export interface CanvasRect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface CanvasPoint {
  x: number;
  y: number;
}

export interface CanvasGridResolverOptions {
  origin?: CanvasPoint;
  gap?: number;
  cellWidth?: number;
  cellHeight?: number;
  maxColumns?: number;
  maxAttempts?: number;
}

export function rectsOverlap(a: CanvasRect, b: CanvasRect): boolean {
  return a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
}

export function mergeCanvasBounds(rects: CanvasRect[]): CanvasRect | null {
  if (!rects.length) return null;
  const left = Math.min(...rects.map((rect) => rect.x));
  const top = Math.min(...rects.map((rect) => rect.y));
  const right = Math.max(...rects.map((rect) => rect.x + rect.w));
  const bottom = Math.max(...rects.map((rect) => rect.y + rect.h));
  return { x: left, y: top, w: right - left, h: bottom - top };
}

export function findOpenCanvasGridSlot(params: {
  occupiedRects: CanvasRect[];
  width: number;
  height: number;
  options?: CanvasGridResolverOptions;
}): CanvasPoint {
  const origin = params.options?.origin ?? { x: 32, y: 32 };
  const gap = Math.max(0, params.options?.gap ?? 24);
  const cellWidth = Math.max(1, params.options?.cellWidth ?? params.width + gap);
  const cellHeight = Math.max(1, params.options?.cellHeight ?? params.height + gap);
  const maxColumns = Math.max(1, params.options?.maxColumns ?? 4);
  const maxAttempts = Math.max(maxColumns, params.options?.maxAttempts ?? 400);

  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    const row = Math.floor(attempt / maxColumns);
    const column = attempt % maxColumns;
    const candidate = {
      x: origin.x + column * cellWidth,
      y: origin.y + row * cellHeight,
      w: params.width,
      h: params.height,
    };
    if (!params.occupiedRects.some((rect) => rectsOverlap(candidate, rect))) {
      return { x: candidate.x, y: candidate.y };
    }
  }

  const fallbackRow = Math.floor(maxAttempts / maxColumns);
  return {
    x: origin.x,
    y: origin.y + fallbackRow * cellHeight,
  };
}
