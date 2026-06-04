import React from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import { useClaudeTokens } from '@/shared/styles/ThemeContext';

type LightweightThinkingVariant = 'live' | 'completed';

interface LightweightThinkingRowProps {
  variant: LightweightThinkingVariant;
  label?: string | null;
  durationMs?: number | null;
  seedKey?: string | null;
}

const thinkingShimmerKeyframes = `
@keyframes lightweight-thinking-shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
`;

const STREAMING_LABELS: ReadonlyArray<string> = [
  'Thinking',
];

function streamingLabelFor(seedKey: string | null | undefined): string {
  if (!seedKey) return STREAMING_LABELS[0];
  let h = 0;
  for (let i = 0; i < seedKey.length; i += 1) {
    h = ((h << 5) - h + seedKey.charCodeAt(i)) | 0;
  }
  return STREAMING_LABELS[Math.abs(h) % STREAMING_LABELS.length];
}

function formatDuration(ms?: number | null): string | null {
  if (typeof ms !== 'number' || !Number.isFinite(ms) || ms < 0) return null;
  const totalSeconds = Math.max(0, Math.round(ms / 1000));
  if (totalSeconds < 60) return `${totalSeconds}s`;
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return seconds > 0 ? `${minutes}m ${seconds}s` : `${minutes}m`;
}

const LightweightThinkingRow: React.FC<LightweightThinkingRowProps> = ({
  variant,
  label,
  durationMs,
  seedKey,
}) => {
  const c = useClaudeTokens();
  const duration = formatDuration(durationMs);
  const baseLabel = String(label || '').trim();
  const liveLabel = baseLabel || streamingLabelFor(seedKey);
  const completedLabel = baseLabel || 'Thought';
  const text = variant === 'live'
    ? `${liveLabel}${duration ? ` · ${duration}` : ''}`
    : `${completedLabel}${duration ? ` for ${duration}` : ''}`;

  const shimmerBase = c.text.tertiary;
  const shimmerHighlight = c.text.primary;

  return (
    <Box sx={{ display: 'flex', justifyContent: 'flex-start', mt: variant === 'completed' ? 0.45 : 0.75, mb: 0.35 }}>
      {variant === 'live' && <style>{thinkingShimmerKeyframes}</style>}
      <Box
        sx={{
          display: 'inline-flex',
          alignItems: 'center',
          minHeight: variant === 'completed' ? 18 : 30,
          maxWidth: '100%',
          borderRadius: '14px 14px 14px 4px',
          px: variant === 'completed' ? 0 : 1.25,
          py: variant === 'completed' ? 0 : 0.65,
          bgcolor: variant === 'live' ? c.bg.surface : 'transparent',
          border: variant === 'live' ? `1px solid ${c.border.subtle}` : 'none',
          boxShadow: variant === 'live' ? c.shadow.sm : 'none',
        }}
      >
        <Typography
          component="span"
          sx={{
            fontSize: variant === 'completed' ? '0.72rem' : '0.82rem',
            fontWeight: variant === 'live' ? 520 : 400,
            lineHeight: variant === 'completed' ? 1.25 : 1.35,
            color: variant === 'completed' ? c.text.muted : c.text.tertiary,
            ...(variant === 'live'
              ? {
                  background: `linear-gradient(90deg, ${shimmerBase} 0%, ${shimmerBase} 40%, ${shimmerHighlight} 50%, ${shimmerBase} 60%, ${shimmerBase} 100%)`,
                  backgroundSize: '200% 100%',
                  WebkitBackgroundClip: 'text',
                  backgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                  animation: 'lightweight-thinking-shimmer 2s linear infinite',
                }
              : {}),
          }}
        >
          {text}
        </Typography>
      </Box>
    </Box>
  );
};

export default LightweightThinkingRow;
