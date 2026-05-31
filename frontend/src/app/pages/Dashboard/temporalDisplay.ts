export type TemporalStatusKind =
  | 'completed'
  | 'failed'
  | 'interrupted'
  | 'timed_out'
  | 'cancelled'
  | 'blocked'
  | 'running'
  | 'warning'
  | 'unknown';

export function formatTemporalDurationMs(durationMs?: number | null): string {
  if (durationMs == null || Number.isNaN(Number(durationMs))) return 'not recorded';
  const safeMs = Math.max(0, Math.round(Number(durationMs)));
  if (safeMs < 1000) return `${safeMs}ms`;
  const totalSeconds = Math.floor(safeMs / 1000);
  const msRemainder = safeMs % 1000;
  if (totalSeconds < 60) return msRemainder > 0 ? `${totalSeconds}.${String(msRemainder).padStart(3, '0').slice(0, 1)}s` : `${totalSeconds}s`;
  const seconds = totalSeconds % 60;
  const totalMinutes = Math.floor(totalSeconds / 60);
  if (totalMinutes < 60) return `${totalMinutes}m ${String(seconds).padStart(2, '0')}s`;
  const minutes = totalMinutes % 60;
  const hours = Math.floor(totalMinutes / 60);
  return minutes > 0 ? `${hours}h ${minutes}m` : `${hours}h`;
}

export function parseTemporalTimestamp(value: unknown): number | null {
  const text = String(value || '').trim();
  if (!text) return null;
  const timestamp = new Date(text).getTime();
  return Number.isNaN(timestamp) ? null : timestamp;
}

export function formatTemporalTimestampLocal(value: unknown, fallback = 'not recorded'): string {
  const timestamp = parseTemporalTimestamp(value);
  if (timestamp == null) return fallback;
  return new Date(timestamp).toLocaleString([], {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

export function getTemporalRunningDurationMs(startedAt: unknown, completedAt?: unknown, interruptedAt?: unknown, nowMs = Date.now()): number | null {
  const start = parseTemporalTimestamp(startedAt);
  if (start == null) return null;
  if (parseTemporalTimestamp(completedAt) != null || parseTemporalTimestamp(interruptedAt) != null) return null;
  return Math.max(0, nowMs - start);
}

export function getTemporalStatusLabel(status?: unknown): string {
  const normalized = String(status || '').trim().toLowerCase().replace(/[\s-]+/g, '_');
  const labels: Record<string, string> = {
    completed: 'Completed',
    failed: 'Failed',
    interrupted: 'Interrupted',
    timed_out: 'Timed out',
    timeout: 'Timed out',
    cancelled: 'Canceled',
    canceled: 'Canceled',
    blocked: 'Blocked',
    running: 'Running',
    warning: 'Warning',
  };
  return labels[normalized] || (normalized ? normalized.split('_').map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(' ') : 'Unknown');
}

export function getTemporalFreshnessLabel(value?: unknown): string {
  const normalized = String(value || '').trim().toLowerCase().replace(/[\s-]+/g, '_');
  const labels: Record<string, string> = {
    fresh: 'Fresh',
    expiring: 'Expiring soon',
    stale: 'Stale',
    unknown: 'Freshness unknown',
  };
  return labels[normalized] || 'Freshness not recorded';
}

export function isTemporalDurationSlow(durationMs?: number | null, thresholdMs = 60_000): boolean {
  if (durationMs == null || Number.isNaN(Number(durationMs))) return false;
  return Number(durationMs) >= thresholdMs;
}
