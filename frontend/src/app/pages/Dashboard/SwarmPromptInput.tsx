import React from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import IconButton from '@mui/material/IconButton';
import InputBase from '@mui/material/InputBase';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import HourglassEmptyIcon from '@mui/icons-material/HourglassEmpty';
import AdsClickOutlinedIcon from '@mui/icons-material/AdsClickOutlined';
import AttachFileIcon from '@mui/icons-material/AttachFile';
import MicNoneIcon from '@mui/icons-material/MicNone';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import SwarmModePicker, { getSwarmModeOption } from './SwarmModePicker';
import { useClaudeTokens } from '@/shared/styles/ThemeContext';
import { useAppSelector } from '@/shared/hooks';
import type { SwarmMode } from '@/shared/state/dashboardLayoutSlice';

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
  inputRef,
}) => {
  const c = useClaudeTokens();
  const modelsByProvider = useAppSelector((s) => s.models.byProvider);
  const modeOption = getSwarmModeOption(mode);
  const [modelAnchor, setModelAnchor] = React.useState<HTMLElement | null>(null);

  const modelOptions = React.useMemo(() => {
    const options: Array<{ value: string; label: string; provider: string }> = [];
    for (const [provider, models] of Object.entries(modelsByProvider)) {
      for (const modelItem of models as any[]) {
        options.push({
          value: String(modelItem.value || modelItem.id || modelItem.label || ''),
          label: String(modelItem.label || modelItem.value || modelItem.id || ''),
          provider,
        });
      }
    }
    return options.filter((option) => option.value);
  }, [modelsByProvider]);

  const selectedModel = modelOptions.find((option) => option.value === model);
  const visibleModelLabel = selectedModel?.label || modelLabel || model || null;
  const submitDisabled = disabled || loading || (!value.trim() && !canContinue);
  const placeholder = customIntakeMode ? 'Escribí tu respuesta personalizada…' : modeOption.placeholder;

  return (
    <Box
      sx={{
        maxWidth: embedded ? '100%' : 760,
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
          {visibleModelLabel && (
            <>
              <Button
                size="small"
                onClick={(event) => setModelAnchor(event.currentTarget)}
                disabled={disabled || loading || !onModelChange}
                endIcon={<KeyboardArrowDownIcon sx={{ fontSize: 14 }} />}
                sx={{
                  height: 26,
                  maxWidth: 220,
                  px: 1,
                  minWidth: 0,
                  borderRadius: 999,
                  bgcolor: c.bg.secondary,
                  color: c.text.secondary,
                  border: `1px solid ${c.border.subtle}`,
                  textTransform: 'none',
                  fontSize: '0.72rem',
                  justifyContent: 'flex-start',
                  '& .MuiButton-endIcon': { ml: 0.25 },
                }}
              >
                <Box component="span" sx={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {visibleModelLabel}
                </Box>
              </Button>
              <Menu
                anchorEl={modelAnchor}
                open={Boolean(modelAnchor)}
                onClose={() => setModelAnchor(null)}
                slotProps={{
                  paper: {
                    sx: {
                      mt: 0.75,
                      maxHeight: 360,
                      width: 280,
                      bgcolor: c.bg.surface,
                      border: `1px solid ${c.border.subtle}`,
                      boxShadow: c.shadow.lg,
                    },
                  },
                }}
              >
                {modelOptions.length === 0 ? (
                  <MenuItem disabled sx={{ fontSize: '0.78rem', color: c.text.tertiary }}>
                    No models loaded
                  </MenuItem>
                ) : modelOptions.map((option) => (
                  <MenuItem
                    key={`${option.provider}-${option.value}`}
                    selected={option.value === model}
                    onClick={() => {
                      onModelChange?.(option.value);
                      setModelAnchor(null);
                    }}
                    sx={{ display: 'block', py: 0.75 }}
                  >
                    <Typography sx={{ fontSize: '0.8rem', color: c.text.primary }} noWrap>
                      {option.label}
                    </Typography>
                    <Typography sx={{ fontSize: '0.68rem', color: c.text.tertiary }} noWrap>
                      {option.provider}
                    </Typography>
                  </MenuItem>
                ))}
              </Menu>
            </>
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
