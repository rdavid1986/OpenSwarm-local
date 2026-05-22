import React from 'react';
import Box from '@mui/material/Box';
import IconButton from '@mui/material/IconButton';
import InputBase from '@mui/material/InputBase';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import HourglassEmptyIcon from '@mui/icons-material/HourglassEmpty';
import AdsClickOutlinedIcon from '@mui/icons-material/AdsClickOutlined';
import AttachFileIcon from '@mui/icons-material/AttachFile';
import MicNoneIcon from '@mui/icons-material/MicNone';
import ModelPicker from '@/app/components/ModelPicker';
import SwarmModePicker, { getSwarmModeOption } from './SwarmModePicker';
import { useClaudeTokens } from '@/shared/styles/ThemeContext';
import type { SwarmMode } from '@/shared/state/dashboardLayoutSlice';

function formatTokenCount(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

const ContextRing: React.FC<{ used: number; limit: number; accentColor: string; trackColor: string }> = ({ used, limit, accentColor, trackColor }) => {
  if (used === 0 || limit <= 0) return null;
  const pct = Math.min((used / limit) * 100, 100);
  const size = 20;
  const strokeWidth = 2;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const dashOffset = circumference * (1 - pct / 100);
  const tooltip = `${pct.toFixed(1)}% · ${formatTokenCount(used)} / ${formatTokenCount(limit)} context used`;

  return (
    <Tooltip title={tooltip}>
      <Box sx={{ display: 'inline-flex', alignItems: 'center', cursor: 'default', p: 0.5 }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
          <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke={trackColor} strokeWidth={strokeWidth} />
          <circle
            cx={size / 2} cy={size / 2} r={radius}
            fill="none" stroke={accentColor} strokeWidth={strokeWidth}
            strokeDasharray={circumference} strokeDashoffset={dashOffset}
            strokeLinecap="round"
            transform={`rotate(-90 ${size / 2} ${size / 2})`}
          />
        </svg>
      </Box>
    </Tooltip>
  );
};

interface Props {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  mode: SwarmMode;
  onModeChange: (mode: SwarmMode) => void;
  loading?: boolean;
  disabled?: boolean;
  canContinue?: boolean;
  customIntakeMode?: boolean;
  embedded?: boolean;
  autoFocus?: boolean;
  model?: string | null;
  onModelChange?: (model: string) => void;
  modelLabel?: string | null;
  contextEstimate?: { used: number; limit: number };
  inputRef?: React.Ref<HTMLInputElement | HTMLTextAreaElement>;
}

const SwarmPromptInput: React.FC<Props> = ({
  value,
  onChange,
  onSend,
  mode,
  onModeChange,
  loading = false,
  disabled = false,
  canContinue = false,
  customIntakeMode = false,
  embedded = false,
  autoFocus = false,
  model,
  onModelChange,
  modelLabel,
  contextEstimate,
  inputRef,
}) => {
  const c = useClaudeTokens();
  const modeOption = getSwarmModeOption(mode);
  const selectedModel = model || modelLabel || '';
  const submitDisabled = disabled || loading || (!value.trim() && !canContinue);
  const placeholder = customIntakeMode ? 'Escribí tu respuesta personalizada…' : modeOption.placeholder;

  return (
    <Box
      sx={{
        maxWidth: embedded ? '100%' : 860,
        mx: embedded ? 0 : 'auto',
        border: `1px solid ${c.border.subtle}`,
        borderRadius: 1.25,
        bgcolor: c.bg.surface,
        boxShadow: embedded ? 'none' : c.shadow.md,
      }}
    >
      <Box
        onPointerDown={(e) => e.stopPropagation()}
        onClick={(e) => e.stopPropagation()}
        sx={{ px: 1.5, pt: 1.25, pb: 0.25 }}
      >
        <InputBase
          multiline
          fullWidth
          minRows={1}
          maxRows={5}
          inputRef={inputRef}
          autoFocus={autoFocus}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDownCapture={(e) => {
            e.stopPropagation();
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              if (!submitDisabled) onSend();
            }
          }}
          onKeyUpCapture={(e) => e.stopPropagation()}
          onKeyDown={(e) => e.stopPropagation()}
          placeholder={placeholder}
          sx={{ fontSize: '0.95rem', color: c.text.primary, lineHeight: 1.55 }}
        />
      </Box>

      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1, px: 1, pb: 0.75 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, minWidth: 0, flexWrap: 'wrap' }}>
          <SwarmModePicker mode={mode} onChange={onModeChange} disabled={disabled || loading} />
          {selectedModel && (
            <ModelPicker
              model={selectedModel}
              onModelChange={(nextModel) => onModelChange?.(nextModel)}
              disabled={disabled || loading || !onModelChange}
              compact
            />
          )}
          <Tooltip title="Select UI element todavía no está conectado para Swarm">
            <span>
              <IconButton size="small" disabled sx={{ width: 28, height: 28 }}>
                <AdsClickOutlinedIcon sx={{ fontSize: 16 }} />
              </IconButton>
            </span>
          </Tooltip>
          <Tooltip title="Attach file todavía no está conectado para Swarm">
            <span>
              <IconButton size="small" disabled sx={{ width: 28, height: 28 }}>
                <AttachFileIcon sx={{ fontSize: 16 }} />
              </IconButton>
            </span>
          </Tooltip>
          <Tooltip title="Voice chat coming soon">
            <span>
              <IconButton size="small" disabled sx={{ width: 28, height: 28 }}>
                <MicNoneIcon sx={{ fontSize: 16 }} />
              </IconButton>
            </span>
          </Tooltip>
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {contextEstimate && (
            <ContextRing
              used={contextEstimate.used}
              limit={contextEstimate.limit}
              accentColor={c.accent.primary}
              trackColor={c.border.subtle}
            />
          )}
          <Typography sx={{ color: c.text.tertiary, fontSize: '0.72rem', display: { xs: 'none', sm: 'block' } }}>
            Shift+Enter
          </Typography>
          <IconButton
            size="small"
            onClick={onSend}
            disabled={submitDisabled}
            sx={{
              bgcolor: c.accent.primary,
              color: c.text.inverse,
              p: 0.5,
              width: 28,
              height: 28,
              '&:hover': { bgcolor: c.accent.hover },
              '&.Mui-disabled': { bgcolor: c.bg.secondary, color: c.text.ghost },
            }}
          >
            {loading ? <HourglassEmptyIcon sx={{ fontSize: 16 }} /> : <ArrowUpwardIcon sx={{ fontSize: 16 }} />}
          </IconButton>
        </Box>
      </Box>
    </Box>
  );
};

export default SwarmPromptInput;
