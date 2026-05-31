export type TemporalUsageActivityKind =
  | 'active_work'
  | 'idle'
  | 'agent_runtime'
  | 'user_review'
  | 'blocked'
  | 'background'
  | 'qa'
  | 'unknown';

export type TemporalUsageSortMode =
  | 'most_time'
  | 'least_time'
  | 'most_sessions'
  | 'latest_activity'
  | 'most_agent_runtime';

export interface TemporalUsageRecord {
  record_id?: string | null;
  session_id?: string | null;
  project_id?: string | null;
  dashboard_id?: string | null;
  swarm_id?: string | null;
  agent_id?: string | null;
  activity_kind?: TemporalUsageActivityKind | string | null;
  duration_ms?: number | null;
  active_work_ms?: number | null;
  idle_ms?: number | null;
  agent_runtime_ms?: number | null;
  user_review_ms?: number | null;
  blocked_ms?: number | null;
  background_ms?: number | null;
  qa_ms?: number | null;
  started_at?: string | null;
  completed_at?: string | null;
  last_activity_at?: string | null;
}

export interface TemporalUsageBucket {
  id: string;
  total_ms: number;
  active_work_ms: number;
  idle_ms: number;
  agent_runtime_ms: number;
  user_review_ms: number;
  blocked_ms: number;
  session_count: number;
  last_activity_at: string | null;
}

export interface TemporalUsageSummary {
  schema: 'openswarm.local_temporal_usage_summary.v1';
  generated_at: string;
  empty: boolean;
  record_count: number;
  session_count: number;
  totals: {
    openswarm_usage_ms: number;
    active_work_ms: number;
    idle_ms: number;
    agent_runtime_ms: number;
    user_review_ms: number;
    blocked_ms: number;
    background_ms: number;
    qa_ms: number;
  };
  sessions: {
    average_duration_ms: number;
    longest_duration_ms: number;
    last_activity_at: string | null;
  };
  projects: TemporalUsageBucket[];
  dashboards: TemporalUsageBucket[];
  swarms: TemporalUsageBucket[];
  agents: TemporalUsageBucket[];
  activities: Array<{ activity_kind: TemporalUsageActivityKind; total_ms: number; record_count: number }>;
}

export interface TemporalPrivacyReport {
  local_only: true;
  telemetry_enabled: false;
  community_sharing_enabled: false;
  scoreboard_enabled: false;
  external_upload_enabled: false;
  measured: string[];
  kept_conceptually: string;
  not_measured: string[];
  never_uploaded: string[];
  export_excludes: string[];
}

export interface TemporalUsageExport {
  export_kind: 'openswarm.local_temporal_usage_export.v1';
  generated_at: string;
  local_only: true;
  summary: TemporalUsageSummary;
  privacy_report: TemporalPrivacyReport;
}

const ACTIVITY_KINDS: TemporalUsageActivityKind[] = [
  'active_work',
  'idle',
  'agent_runtime',
  'user_review',
  'blocked',
  'background',
  'qa',
  'unknown',
];

function safeNumber(value: unknown): number {
  const n = Number(value);
  return Number.isFinite(n) && n > 0 ? Math.round(n) : 0;
}

function safeId(value: unknown, fallback: string): string {
  const raw = String(value ?? '').trim();
  if (!raw) return fallback;
  const compact = raw.replace(/[^a-zA-Z0-9_.:-]/g, '_').slice(0, 80);
  return compact || fallback;
}

function safeTimestamp(value: unknown): string | null {
  const raw = String(value ?? '').trim();
  if (!raw) return null;
  const time = new Date(raw).getTime();
  return Number.isFinite(time) ? new Date(time).toISOString() : null;
}

function normalizeActivityKind(value: unknown): TemporalUsageActivityKind {
  const normalized = String(value ?? '').trim().toLowerCase().replace(/[\s-]+/g, '_') as TemporalUsageActivityKind;
  return ACTIVITY_KINDS.includes(normalized) ? normalized : 'unknown';
}

function maxTimestamp(a: string | null, b: string | null): string | null {
  if (!a) return b;
  if (!b) return a;
  return new Date(a).getTime() >= new Date(b).getTime() ? a : b;
}

function createBucket(id: string): TemporalUsageBucket {
  return {
    id,
    total_ms: 0,
    active_work_ms: 0,
    idle_ms: 0,
    agent_runtime_ms: 0,
    user_review_ms: 0,
    blocked_ms: 0,
    session_count: 0,
    last_activity_at: null,
  };
}

function addToBucket(bucket: TemporalUsageBucket, record: Required<Pick<TemporalUsageRecord,
  'active_work_ms' | 'idle_ms' | 'agent_runtime_ms' | 'user_review_ms' | 'blocked_ms'
>> & { total_ms: number; session_id: string; last_activity_at: string | null }, seenSessions: Set<string>) {
  bucket.total_ms += record.total_ms;
  bucket.active_work_ms += safeNumber(record.active_work_ms);
  bucket.idle_ms += safeNumber(record.idle_ms);
  bucket.agent_runtime_ms += safeNumber(record.agent_runtime_ms);
  bucket.user_review_ms += safeNumber(record.user_review_ms);
  bucket.blocked_ms += safeNumber(record.blocked_ms);
  bucket.last_activity_at = maxTimestamp(bucket.last_activity_at, record.last_activity_at);
  const key = `${bucket.id}:${record.session_id}`;
  if (!seenSessions.has(key)) {
    seenSessions.add(key);
    bucket.session_count += 1;
  }
}

function sortBuckets(buckets: TemporalUsageBucket[], sort: TemporalUsageSortMode): TemporalUsageBucket[] {
  return [...buckets].sort((a, b) => {
    if (sort === 'least_time') return a.total_ms - b.total_ms || a.id.localeCompare(b.id);
    if (sort === 'most_sessions') return b.session_count - a.session_count || b.total_ms - a.total_ms || a.id.localeCompare(b.id);
    if (sort === 'latest_activity') return new Date(b.last_activity_at || 0).getTime() - new Date(a.last_activity_at || 0).getTime() || a.id.localeCompare(b.id);
    if (sort === 'most_agent_runtime') return b.agent_runtime_ms - a.agent_runtime_ms || b.total_ms - a.total_ms || a.id.localeCompare(b.id);
    return b.total_ms - a.total_ms || a.id.localeCompare(b.id);
  });
}

export function formatUsageDurationMs(durationMs?: number | null): string {
  const safeMs = safeNumber(durationMs);
  if (safeMs <= 0) return '0ms';
  if (safeMs < 1000) return `${safeMs}ms`;
  const totalSeconds = Math.floor(safeMs / 1000);
  if (totalSeconds < 60) return `${totalSeconds}s`;
  const seconds = totalSeconds % 60;
  const totalMinutes = Math.floor(totalSeconds / 60);
  if (totalMinutes < 60) return seconds > 0 ? `${totalMinutes}m ${String(seconds).padStart(2, '0')}s` : `${totalMinutes}m`;
  const minutes = totalMinutes % 60;
  const hours = Math.floor(totalMinutes / 60);
  return minutes > 0 ? `${hours}h ${minutes}m` : `${hours}h`;
}

export function buildTemporalUsagePrivacyReport(): TemporalPrivacyReport {
  return {
    local_only: true,
    telemetry_enabled: false,
    community_sharing_enabled: false,
    scoreboard_enabled: false,
    external_upload_enabled: false,
    measured: [
      'durations by activity kind',
      'session counts',
      'safe project/dashboard/swarm/agent identifiers',
      'last activity timestamps',
      'aggregate active, idle, runtime, review and blocked time',
    ],
    kept_conceptually: 'Only local runtime state or future local storage owned by this OpenSwarm install; this screen does not send data anywhere.',
    not_measured: [
      'prompts',
      'conversations',
      'code content',
      'file paths',
      'model outputs',
      'logs',
      'secrets',
      'credentials',
      'private project names',
    ],
    never_uploaded: [
      'local usage analytics',
      'privacy report exports',
      'project/dashboard time summaries',
      'swarm/agent aggregates',
    ],
    export_excludes: [
      'prompts',
      'conversation text',
      'code',
      'absolute or relative paths',
      'raw outputs',
      'logs',
      'secrets',
      'private project names',
      'settings tokens',
    ],
  };
}

export function buildTemporalUsageAnalytics(
  records: TemporalUsageRecord[] = [],
  sort: TemporalUsageSortMode = 'most_time',
  generatedAt = new Date().toISOString(),
): TemporalUsageSummary {
  const projectBuckets = new Map<string, TemporalUsageBucket>();
  const dashboardBuckets = new Map<string, TemporalUsageBucket>();
  const swarmBuckets = new Map<string, TemporalUsageBucket>();
  const agentBuckets = new Map<string, TemporalUsageBucket>();
  const activityTotals = new Map<TemporalUsageActivityKind, { total_ms: number; record_count: number }>();
  const seenSessions = new Set<string>();
  const bucketSessions = new Set<string>();
  const sessionDurations = new Map<string, number>();

  const totals = {
    openswarm_usage_ms: 0,
    active_work_ms: 0,
    idle_ms: 0,
    agent_runtime_ms: 0,
    user_review_ms: 0,
    blocked_ms: 0,
    background_ms: 0,
    qa_ms: 0,
  };
  let lastActivityAt: string | null = null;

  for (const raw of records) {
    const activityKind = normalizeActivityKind(raw.activity_kind);
    const active = safeNumber(raw.active_work_ms) || (activityKind === 'active_work' ? safeNumber(raw.duration_ms) : 0);
    const idle = safeNumber(raw.idle_ms) || (activityKind === 'idle' ? safeNumber(raw.duration_ms) : 0);
    const agentRuntime = safeNumber(raw.agent_runtime_ms) || (activityKind === 'agent_runtime' ? safeNumber(raw.duration_ms) : 0);
    const userReview = safeNumber(raw.user_review_ms) || (activityKind === 'user_review' ? safeNumber(raw.duration_ms) : 0);
    const blocked = safeNumber(raw.blocked_ms) || (activityKind === 'blocked' ? safeNumber(raw.duration_ms) : 0);
    const background = safeNumber(raw.background_ms) || (activityKind === 'background' ? safeNumber(raw.duration_ms) : 0);
    const qa = safeNumber(raw.qa_ms) || (activityKind === 'qa' ? safeNumber(raw.duration_ms) : 0);
    const explicitDuration = safeNumber(raw.duration_ms);
    const componentDuration = active + idle + agentRuntime + userReview + blocked + background + qa;
    const totalMs = explicitDuration || componentDuration;
    if (totalMs <= 0) continue;

    const sessionId = safeId(raw.session_id || raw.record_id, 'local-session');
    const projectId = safeId(raw.project_id, 'local-project');
    const dashboardId = safeId(raw.dashboard_id, 'local-dashboard');
    const swarmId = safeId(raw.swarm_id, 'local-swarm');
    const agentId = safeId(raw.agent_id, 'local-agent');
    const activityAt = safeTimestamp(raw.last_activity_at) || safeTimestamp(raw.completed_at) || safeTimestamp(raw.started_at);

    totals.openswarm_usage_ms += totalMs;
    totals.active_work_ms += active;
    totals.idle_ms += idle;
    totals.agent_runtime_ms += agentRuntime;
    totals.user_review_ms += userReview;
    totals.blocked_ms += blocked;
    totals.background_ms += background;
    totals.qa_ms += qa;
    lastActivityAt = maxTimestamp(lastActivityAt, activityAt);
    seenSessions.add(sessionId);
    sessionDurations.set(sessionId, (sessionDurations.get(sessionId) || 0) + totalMs);

    const activity = activityTotals.get(activityKind) || { total_ms: 0, record_count: 0 };
    activity.total_ms += totalMs;
    activity.record_count += 1;
    activityTotals.set(activityKind, activity);

    const normalizedRecord = {
      total_ms: totalMs,
      session_id: sessionId,
      active_work_ms: active,
      idle_ms: idle,
      agent_runtime_ms: agentRuntime,
      user_review_ms: userReview,
      blocked_ms: blocked,
      last_activity_at: activityAt,
    };
    for (const [map, id] of [
      [projectBuckets, projectId],
      [dashboardBuckets, dashboardId],
      [swarmBuckets, swarmId],
      [agentBuckets, agentId],
    ] as Array<[Map<string, TemporalUsageBucket>, string]>) {
      if (!map.has(id)) map.set(id, createBucket(id));
      addToBucket(map.get(id) as TemporalUsageBucket, normalizedRecord, bucketSessions);
    }
  }

  const sessionDurationsList = Array.from(sessionDurations.values());
  const longestDuration = sessionDurationsList.length ? Math.max(...sessionDurationsList) : 0;
  const averageDuration = sessionDurationsList.length
    ? Math.round(sessionDurationsList.reduce((acc, value) => acc + value, 0) / sessionDurationsList.length)
    : 0;

  return {
    schema: 'openswarm.local_temporal_usage_summary.v1',
    generated_at: generatedAt,
    empty: totals.openswarm_usage_ms <= 0,
    record_count: records.length,
    session_count: seenSessions.size,
    totals,
    sessions: {
      average_duration_ms: averageDuration,
      longest_duration_ms: longestDuration,
      last_activity_at: lastActivityAt,
    },
    projects: sortBuckets(Array.from(projectBuckets.values()), sort),
    dashboards: sortBuckets(Array.from(dashboardBuckets.values()), sort),
    swarms: sortBuckets(Array.from(swarmBuckets.values()), sort),
    agents: sortBuckets(Array.from(agentBuckets.values()), sort),
    activities: Array.from(activityTotals.entries())
      .map(([activity_kind, value]) => ({ activity_kind, total_ms: value.total_ms, record_count: value.record_count }))
      .sort((a, b) => b.total_ms - a.total_ms || a.activity_kind.localeCompare(b.activity_kind)),
  };
}

export function buildTemporalUsageExport(summary: TemporalUsageSummary, generatedAt = new Date().toISOString()): TemporalUsageExport {
  return {
    export_kind: 'openswarm.local_temporal_usage_export.v1',
    generated_at: generatedAt,
    local_only: true,
    summary,
    privacy_report: buildTemporalUsagePrivacyReport(),
  };
}

function csvEscape(value: unknown): string {
  const text = String(value ?? '');
  return /[",\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

export function buildTemporalUsageCsv(summary: TemporalUsageSummary): string {
  const rows: unknown[][] = [
    ['section', 'id', 'total_ms', 'sessions', 'active_work_ms', 'idle_ms', 'agent_runtime_ms', 'user_review_ms', 'blocked_ms', 'last_activity_at'],
    ['total', 'openswarm_usage', summary.totals.openswarm_usage_ms, summary.session_count, summary.totals.active_work_ms, summary.totals.idle_ms, summary.totals.agent_runtime_ms, summary.totals.user_review_ms, summary.totals.blocked_ms, summary.sessions.last_activity_at || ''],
  ];
  for (const section of ['projects', 'dashboards', 'swarms', 'agents'] as const) {
    for (const bucket of summary[section]) {
      rows.push([section, bucket.id, bucket.total_ms, bucket.session_count, bucket.active_work_ms, bucket.idle_ms, bucket.agent_runtime_ms, bucket.user_review_ms, bucket.blocked_ms, bucket.last_activity_at || '']);
    }
  }
  return rows.map((row) => row.map(csvEscape).join(',')).join('\n');
}
