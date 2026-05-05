// Service-sync client (frontend half).
//
// Single public surface: `submit(kind, payload)`. The desktop hands off
// opaque payload dicts; the cloud at api.openswarm.com is responsible
// for parsing them. Reports are batched into 1-second windows so a busy
// UI doesn't fire dozens of HTTP calls per second.
//
// Operationally named — generic "operational state sync" surface, no
// vendor-specific terminology in the source.

import { API_BASE } from './config';

interface Submission {
  kind: string;
  payload: Record<string, unknown>;
  /** Use sendBeacon (page-unload reliability). Bypasses batching. */
  beacon?: boolean;
}

let _lastInteractionTs = Date.now();
let _appStart = Date.now();

const _queue: Submission[] = [];
let _flushTimer: ReturnType<typeof setTimeout> | null = null;

function _flush(): void {
  if (_queue.length === 0) return;
  const batch = _queue.splice(0);
  for (const s of batch) {
    const body = JSON.stringify({ kind: s.kind, payload: s.payload });
    if (s.beacon && typeof navigator !== 'undefined' && navigator.sendBeacon) {
      navigator.sendBeacon(
        `${API_BASE}/service/submit`,
        new Blob([body], { type: 'application/json' }),
      );
    } else {
      fetch(`${API_BASE}/service/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body,
      }).catch(() => {
        /* fire-and-forget */
      });
    }
  }
}

/** Hand off an opaque payload to the cloud. */
export function submit(
  kind: string,
  payload: Record<string, unknown> = {},
  opts: { beacon?: boolean } = {},
): void {
  if (!kind) return;
  _lastInteractionTs = Date.now();
  const s: Submission = { kind, payload, beacon: opts.beacon };
  if (opts.beacon) {
    _queue.push(s);
    _flush();
    return;
  }
  _queue.push(s);
  if (_flushTimer == null) {
    _flushTimer = setTimeout(() => {
      _flushTimer = null;
      _flush();
    }, 1000);
  }
}

/** Backwards-compat shim for legacy `trackEvent("foo.bar", props)` call
 * sites. Splits the dotted name into surface/action and bundles into
 * the opaque payload. New code calls `submit()` directly. */
export function trackEvent(
  eventType: string,
  properties?: Record<string, unknown>,
  useBeacon = false,
): void {
  const dot = eventType.indexOf('.');
  const surface = dot > 0 ? eventType.slice(0, dot) : eventType;
  const action = dot > 0 ? eventType.slice(dot + 1) : 'fired';
  submit(
    'event',
    { surface, action, props: properties || {} },
    { beacon: useBeacon },
  );
}

/** Returns interaction-state timestamps for legitimate UI consumers
 * (idle dimming, "still there?" prompts). */
export function getSessionTraceState(): {
  appStartTs: number;
  lastInteractionTs: number;
} {
  return { appStartTs: _appStart, lastInteractionTs: _lastInteractionTs };
}

export function _resetForTest(): void {
  _queue.length = 0;
  if (_flushTimer != null) {
    clearTimeout(_flushTimer);
    _flushTimer = null;
  }
  _appStart = Date.now();
  _lastInteractionTs = _appStart;
}

// Legacy helpers kept so the analytics.ts shim's exports continue to
// resolve. Removed when analytics.ts is deleted.
export function getLastAction(): string {
  return '';
}
export function getLastPage(): string {
  if (typeof window === 'undefined') return '';
  return window.location.hash || window.location.pathname;
}
export function getTimeSpent(): number {
  return Math.round((Date.now() - _appStart) / 1000);
}

const serviceClient = { submit, trackEvent, getSessionTraceState };
export default serviceClient;
