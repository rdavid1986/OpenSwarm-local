import React, { useMemo, useState } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Paper from '@mui/material/Paper';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Divider from '@mui/material/Divider';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import type { SelectChangeEvent } from '@mui/material/Select';
import { useClaudeTokens } from '@/shared/styles/ThemeContext';
import {
  buildTemporalUsageAnalytics,
  buildTemporalUsageCsv,
  buildTemporalUsageExport,
  buildTemporalUsagePrivacyReport,
  formatUsageDurationMs,
  type TemporalUsageBucket,
  type TemporalUsageRecord,
  type TemporalUsageSortMode,
} from './temporalUsageAnalytics';

const localUsageRecords: TemporalUsageRecord[] = [];

const sortLabels: Record<TemporalUsageSortMode, string> = {
  most_time: 'Most time',
  least_time: 'Least time',
  most_sessions: 'Most sessions',
  latest_activity: 'Latest activity',
  most_agent_runtime: 'Most agent runtime',
};

function downloadTextFile(filename: string, mimeType: string, contents: string) {
  const blob = new Blob([contents], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function formatLocalTimestamp(value?: string | null): string {
  if (!value) return 'Not recorded';
  const timestamp = new Date(value).getTime();
  if (!Number.isFinite(timestamp)) return 'Not recorded';
  return new Date(timestamp).toLocaleString();
}

const Analytics: React.FC = () => {
  const c = useClaudeTokens();
  const [sortMode, setSortMode] = useState<TemporalUsageSortMode>('most_time');
  const summary = useMemo(() => buildTemporalUsageAnalytics(localUsageRecords, sortMode), [sortMode]);
  const privacyReport = useMemo(() => buildTemporalUsagePrivacyReport(), []);
  const hasData = !summary.empty;

  const handleSortChange = (event: SelectChangeEvent) => {
    setSortMode(event.target.value as TemporalUsageSortMode);
  };

  const exportJson = () => {
    const payload = buildTemporalUsageExport(summary);
    downloadTextFile('openswarm-local-temporal-usage-summary.json', 'application/json', JSON.stringify(payload, null, 2));
  };

  const exportCsv = () => {
    downloadTextFile('openswarm-local-temporal-usage-summary.csv', 'text/csv', buildTemporalUsageCsv(summary));
  };

  const cardSx = {
    p: 2,
    borderRadius: `${c.radius.lg}px`,
    bgcolor: c.bg.surface,
    border: `1px solid ${c.border.subtle}`,
  };

  const metric = (label: string, value: string, detail?: string) => (
    <Paper sx={{ ...cardSx, minHeight: 104 }}>
      <Typography sx={{ color: c.text.tertiary, fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.06em', mb: 0.75 }}>
        {label}
      </Typography>
      <Typography sx={{ color: c.text.primary, fontSize: '1.45rem', fontWeight: 700, lineHeight: 1.1 }}>
        {value}
      </Typography>
      {detail && (
        <Typography sx={{ color: c.text.muted, fontSize: '0.75rem', mt: 0.75 }}>
          {detail}
        </Typography>
      )}
    </Paper>
  );

  const bucketList = (title: string, buckets: TemporalUsageBucket[]) => (
    <Paper sx={cardSx}>
      <Typography sx={{ color: c.text.primary, fontWeight: 700, mb: 1 }}>{title}</Typography>
      {buckets.length === 0 ? (
        <Typography sx={{ color: c.text.muted, fontSize: '0.82rem' }}>No local aggregates recorded.</Typography>
      ) : buckets.slice(0, 5).map((bucket) => (
        <Box key={`${title}-${bucket.id}`} sx={{ py: 1, borderTop: `1px solid ${c.border.subtle}` }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 2 }}>
            <Typography sx={{ color: c.text.primary, fontSize: '0.86rem', fontFamily: c.font.mono }}>{bucket.id}</Typography>
            <Typography sx={{ color: c.text.primary, fontSize: '0.86rem', fontWeight: 700 }}>{formatUsageDurationMs(bucket.total_ms)}</Typography>
          </Box>
          <Typography sx={{ color: c.text.muted, fontSize: '0.72rem' }}>
            {bucket.session_count} sessions - agent {formatUsageDurationMs(bucket.agent_runtime_ms)} - last {formatLocalTimestamp(bucket.last_activity_at)}
          </Typography>
        </Box>
      ))}
    </Paper>
  );

  return (
    <Box sx={{ height: '100%', overflow: 'auto', p: 3, bgcolor: c.bg.page }}>
      <Box sx={{ maxWidth: 1120, mx: 'auto' }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 2, alignItems: 'flex-start', mb: 3 }}>
          <Box>
            <Typography variant="h5" sx={{ color: c.text.primary, fontWeight: 700, mb: 0.75 }}>
              Local Usage Analytics
            </Typography>
            <Typography sx={{ color: c.text.muted, fontSize: '0.88rem', lineHeight: 1.55, maxWidth: 720 }}>
              Private temporal work-time summary for this OpenSwarm install. No community sharing, telemetry, scoreboard, or external upload is enabled.
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
            <Chip size="small" label="Local only" sx={{ bgcolor: c.status.successBg, color: c.status.success, fontWeight: 700 }} />
            <Chip size="small" label="Telemetry disabled" sx={{ bgcolor: c.bg.elevated, color: c.text.secondary }} />
            <Chip size="small" label="Sharing off" sx={{ bgcolor: c.bg.elevated, color: c.text.secondary }} />
          </Box>
        </Box>

        <Paper sx={{ ...cardSx, mb: 2.5 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 2, flexWrap: 'wrap' }}>
            <Box>
              <Typography sx={{ color: c.text.primary, fontWeight: 700, mb: 0.5 }}>Temporal runtime source</Typography>
              <Typography sx={{ color: c.text.muted, fontSize: '0.82rem', lineHeight: 1.5 }}>
                Prepared for local temporal usage records. Runtime integration is not connected here yet, so this screen does not invent or backfill data.
              </Typography>
            </Box>
            <Select size="small" value={sortMode} onChange={handleSortChange} disabled={!hasData} sx={{ minWidth: 190, color: c.text.primary }}>
              {(Object.keys(sortLabels) as TemporalUsageSortMode[]).map((mode) => (
                <MenuItem key={mode} value={mode}>{sortLabels[mode]}</MenuItem>
              ))}
            </Select>
          </Box>
        </Paper>

        {!hasData && (
          <Paper sx={{ ...cardSx, mb: 2.5, textAlign: 'center', py: 4 }}>
            <Typography sx={{ color: c.text.primary, fontSize: '1.1rem', fontWeight: 700, mb: 1 }}>
              No local usage data recorded yet.
            </Typography>
            <Typography sx={{ color: c.text.muted, fontSize: '0.86rem', lineHeight: 1.6, maxWidth: 620, mx: 'auto' }}>
              Local/private tracking is disabled or not connected until runtime integration provides temporal records. Export remains available, but it contains only the empty aggregate summary and privacy report.
            </Typography>
          </Paper>
        )}

        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: 'repeat(4, 1fr)' }, gap: 1.5, mb: 2.5 }}>
          {metric('OpenSwarm usage', formatUsageDurationMs(summary.totals.openswarm_usage_ms), `${summary.session_count} sessions`)}
          {metric('Active work', formatUsageDurationMs(summary.totals.active_work_ms), `Idle ${formatUsageDurationMs(summary.totals.idle_ms)}`)}
          {metric('Agent runtime', formatUsageDurationMs(summary.totals.agent_runtime_ms), `Review ${formatUsageDurationMs(summary.totals.user_review_ms)}`)}
          {metric('Blocked', formatUsageDurationMs(summary.totals.blocked_ms), `Last ${formatLocalTimestamp(summary.sessions.last_activity_at)}`)}
          {metric('Projects', String(summary.projects.length), 'Aggregated by safe IDs only')}
          {metric('Dashboards', String(summary.dashboards.length), 'No dashboard names exported')}
          {metric('Avg session', formatUsageDurationMs(summary.sessions.average_duration_ms), `Longest ${formatUsageDurationMs(summary.sessions.longest_duration_ms)}`)}
          {metric('Records', String(summary.record_count), 'Aggregated before export')}
        </Box>

        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: 'repeat(2, 1fr)' }, gap: 1.5, mb: 2.5 }}>
          {bucketList('Top projects', summary.projects)}
          {bucketList('Top dashboards', summary.dashboards)}
          {bucketList('Top swarms', summary.swarms)}
          {bucketList('Top agents', summary.agents)}
        </Box>

        <Paper sx={{ ...cardSx, mb: 2.5 }}>
          <Typography sx={{ color: c.text.primary, fontWeight: 700, mb: 1 }}>Local export</Typography>
          <Typography sx={{ color: c.text.muted, fontSize: '0.84rem', lineHeight: 1.55, mb: 1.5 }}>
            Downloads contain only aggregate durations, counts, safe IDs, timestamps and this privacy report. They exclude prompts, conversations, code, file paths, outputs, logs, secrets and private project names.
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            <Button variant="contained" onClick={exportJson} sx={{ bgcolor: c.accent.primary, '&:hover': { bgcolor: c.accent.hover } }}>
              Download JSON summary
            </Button>
            <Button variant="outlined" onClick={exportCsv} sx={{ color: c.text.primary, borderColor: c.border.strong }}>
              Download CSV summary
            </Button>
          </Box>
        </Paper>

        <Paper sx={cardSx}>
          <Typography sx={{ color: c.text.primary, fontWeight: 700, mb: 1 }}>Privacy report</Typography>
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: 'repeat(2, 1fr)' }, gap: 2 }}>
            <Box>
              <Typography sx={{ color: c.text.secondary, fontWeight: 700, mb: 0.5 }}>What is measured</Typography>
              <Typography component="ul" sx={{ color: c.text.muted, fontSize: '0.82rem', pl: 2.25, mt: 0, lineHeight: 1.6 }}>
                {privacyReport.measured.map((item) => <li key={item}>{item}</li>)}
              </Typography>
              <Divider sx={{ borderColor: c.border.subtle, my: 1.5 }} />
              <Typography sx={{ color: c.text.secondary, fontWeight: 700, mb: 0.5 }}>Where it is kept</Typography>
              <Typography sx={{ color: c.text.muted, fontSize: '0.82rem', lineHeight: 1.6 }}>{privacyReport.kept_conceptually}</Typography>
            </Box>
            <Box>
              <Typography sx={{ color: c.text.secondary, fontWeight: 700, mb: 0.5 }}>What is not measured or exported</Typography>
              <Typography component="ul" sx={{ color: c.text.muted, fontSize: '0.82rem', pl: 2.25, mt: 0, lineHeight: 1.6 }}>
                {privacyReport.not_measured.map((item) => <li key={item}>{item}</li>)}
              </Typography>
              <Divider sx={{ borderColor: c.border.subtle, my: 1.5 }} />
              <Typography sx={{ color: c.text.secondary, fontWeight: 700, mb: 0.5 }}>Never uploaded</Typography>
              <Typography sx={{ color: c.text.muted, fontSize: '0.82rem', lineHeight: 1.6 }}>
                Local usage summaries, privacy exports, project/dashboard aggregates and swarm/agent aggregates. Community sharing is off, telemetry is disabled, and there is no global scoreboard.
              </Typography>
            </Box>
          </Box>
        </Paper>
      </Box>
    </Box>
  );
};

export default Analytics;
