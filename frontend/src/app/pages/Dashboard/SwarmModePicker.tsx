import React, { useEffect, useMemo } from 'react';
import Button from '@mui/material/Button';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ChatBubbleOutlineIcon from '@mui/icons-material/ChatBubbleOutline';
import FactCheckOutlinedIcon from '@mui/icons-material/FactCheckOutlined';
import AppsOutlinedIcon from '@mui/icons-material/AppsOutlined';
import ExtensionOutlinedIcon from '@mui/icons-material/ExtensionOutlined';
import BugReportOutlinedIcon from '@mui/icons-material/BugReportOutlined';
import { useClaudeTokens } from '@/shared/styles/ThemeContext';
import { useAppDispatch, useAppSelector } from '@/shared/hooks';
import { fetchModes, type Mode } from '@/shared/state/modesSlice';
import type { SwarmMode } from '@/shared/state/dashboardLayoutSlice';

export const DEFAULT_SWARM_MODE: SwarmMode = 'ask';
const SWARM_MODE_IDS = ['ask', 'plan', 'app_builder', 'skill_builder', 'debug'] as const;
const SWARM_MODE_ALIASES: Record<string, SwarmMode> = {
  ask: 'ask',
  chat: 'ask',
  plan: 'plan',
  app_builder: 'app_builder',
  'app-builder': 'app_builder',
  view_builder: 'app_builder',
  'view-builder': 'app_builder',
  skill_builder: 'skill_builder',
  'skill-builder': 'skill_builder',
  debug: 'debug',
};
const REGISTRY_IDS_BY_SWARM_MODE: Record<SwarmMode, string[]> = {
  ask: ['ask', 'chat'],
  plan: ['plan'],
  app_builder: ['app_builder', 'app-builder', 'view-builder', 'view_builder'],
  skill_builder: ['skill_builder', 'skill-builder'],
  debug: ['debug'],
};

export interface SwarmModeOption {
  id: SwarmMode;
  label: string;
  shortDescription: string;
  placeholder: string;
  color: string;
  icon: React.ReactNode;
}

const FALLBACK_SWARM_MODE_OPTIONS: SwarmModeOption[] = [
  {
    id: 'ask',
    label: 'Ask',
    shortDescription: 'Chat normal; no inicia intake.',
    placeholder: 'Ask Swarm…',
    color: '#3b82f6',
    icon: <ChatBubbleOutlineIcon sx={{ fontSize: 14 }} />,
  },
  {
    id: 'plan',
    label: 'Plan',
    shortDescription: 'Plan liviano, sin implementación.',
    placeholder: 'Describe qué querés planificar…',
    color: '#8b5cf6',
    icon: <FactCheckOutlinedIcon sx={{ fontSize: 14 }} />,
  },
  {
    id: 'app_builder',
    label: 'App Builder',
    shortDescription: 'Inicia el intake actual de app.',
    placeholder: 'Describe la app que querés construir…',
    color: '#10b981',
    icon: <AppsOutlinedIcon sx={{ fontSize: 14 }} />,
  },
  {
    id: 'skill_builder',
    label: 'Skill Builder',
    shortDescription: 'Borrador de skill; sin AgentManager.',
    placeholder: 'Describe la skill o agente que querés diseñar…',
    color: '#f59e0b',
    icon: <ExtensionOutlinedIcon sx={{ fontSize: 14 }} />,
  },
  {
    id: 'debug',
    label: 'Debug',
    shortDescription: 'Diagnóstico orientado a estado/logs.',
    placeholder: 'Describe el error o síntoma a diagnosticar…',
    color: '#ef4444',
    icon: <BugReportOutlinedIcon sx={{ fontSize: 14 }} />,
  },
];

function modeIcon(icon?: string | null): React.ReactNode {
  const sx = { fontSize: 14 };
  switch (icon) {
    case 'map':
      return <FactCheckOutlinedIcon sx={sx} />;
    case 'view_quilt':
    case 'category':
      return <AppsOutlinedIcon sx={sx} />;
    case 'psychology':
      return <ExtensionOutlinedIcon sx={sx} />;
    case 'bug_report':
      return <BugReportOutlinedIcon sx={sx} />;
    case 'question_answer':
    case 'smart_toy':
    default:
      return <ChatBubbleOutlineIcon sx={sx} />;
  }
}

export function normalizeSwarmMode(mode?: string | null): SwarmMode {
  return SWARM_MODE_ALIASES[String(mode || '').trim().toLowerCase()] || DEFAULT_SWARM_MODE;
}

function findRegistryMode(modesMap: Record<string, Mode>, mode: SwarmMode): Mode | null {
  for (const id of REGISTRY_IDS_BY_SWARM_MODE[mode]) {
    if (modesMap[id]) return modesMap[id];
  }
  return null;
}

function placeholderForMode(mode: SwarmMode): string {
  return FALLBACK_SWARM_MODE_OPTIONS.find((option) => option.id === mode)?.placeholder || FALLBACK_SWARM_MODE_OPTIONS[0].placeholder;
}

function fallbackSwarmModeOption(mode: SwarmMode): SwarmModeOption {
  return FALLBACK_SWARM_MODE_OPTIONS.find((option) => option.id === mode) || FALLBACK_SWARM_MODE_OPTIONS[0];
}

function registrySwarmModeOption(modesMap: Record<string, Mode>, mode: SwarmMode): SwarmModeOption | null {
  const registryMode = findRegistryMode(modesMap, mode);
  if (!registryMode) return null;
  return {
    id: mode,
    label: registryMode.name,
    shortDescription: registryMode.description,
    placeholder: placeholderForMode(mode),
    color: registryMode.color,
    icon: modeIcon(registryMode.icon),
  };
}

export function getSwarmModeOption(mode?: string | null): SwarmModeOption {
  return fallbackSwarmModeOption(normalizeSwarmMode(mode));
}

interface Props {
  mode: SwarmMode;
  onChange: (mode: SwarmMode) => void;
  disabled?: boolean;
}

const SwarmModePicker: React.FC<Props> = ({ mode, onChange, disabled = false }) => {
  const c = useClaudeTokens();
  const dispatch = useAppDispatch();
  const modesMap = useAppSelector((state) => state.modes.items);
  const modesLoaded = useAppSelector((state) => state.modes.loaded);
  const [anchorEl, setAnchorEl] = React.useState<HTMLElement | null>(null);
  const registryOptions = useMemo(
    () => SWARM_MODE_IDS
      .map((modeId) => registrySwarmModeOption(modesMap, modeId))
      .filter((option): option is SwarmModeOption => Boolean(option)),
    [modesMap],
  );
  const options = registryOptions.length > 0 ? registryOptions : FALLBACK_SWARM_MODE_OPTIONS;
  const normalizedMode = normalizeSwarmMode(mode);
  const selected = registrySwarmModeOption(modesMap, normalizedMode) || fallbackSwarmModeOption(normalizedMode);

  useEffect(() => {
    if (!modesLoaded && Object.keys(modesMap).length === 0) dispatch(fetchModes());
  }, [dispatch, modesLoaded, modesMap]);

  return (
    <>
      <Button
        size="small"
        onClick={(event) => setAnchorEl(event.currentTarget)}
        disabled={disabled}
        startIcon={selected.icon}
        endIcon={<ExpandMoreIcon sx={{ fontSize: 14 }} />}
        data-swarm-mode-picker-style="agent-like"
        sx={{
          minWidth: 'auto',
          minHeight: 'auto',
          height: 'auto',
          px: 1,
          py: 0.375,
          gap: 0.5,
          borderRadius: '999px',
          color: selected.color,
          bgcolor: `${selected.color}14`,
          border: 'none',
          textTransform: 'none',
          fontSize: '0.82rem',
          fontWeight: 600,
          lineHeight: 1,
          cursor: disabled ? 'default' : 'pointer',
          userSelect: 'none',
          transition: 'background 0.15s',
          '&:hover': { bgcolor: `${selected.color}22` },
          '& .MuiButton-startIcon': { m: 0, mr: 0 },
          '& .MuiButton-endIcon': { m: 0, ml: 0 },
          '& .MuiButton-startIcon svg': { fontSize: 14 },
          '& .MuiButton-endIcon svg': { fontSize: 14, opacity: 0.7 },
        }}
      >
        {selected.label}
      </Button>
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={() => setAnchorEl(null)}
        slotProps={{
          paper: {
            sx: {
              mt: 0.75,
              width: 260,
              bgcolor: c.bg.surface,
              border: `1px solid ${c.border.subtle}`,
              boxShadow: c.shadow.lg,
            },
          },
        }}
      >
        {options.map((option) => (
          <MenuItem
            key={option.id}
            selected={option.id === normalizedMode}
            onClick={() => {
              onChange(option.id);
              setAnchorEl(null);
            }}
            sx={{ alignItems: 'flex-start', gap: 1, py: 1 }}
          >
            <Box sx={{ color: option.color, pt: 0.25 }}>{option.icon}</Box>
            <Box sx={{ minWidth: 0 }}>
              <Typography sx={{ color: c.text.primary, fontSize: '0.82rem', fontWeight: 700 }}>
                {option.label}
              </Typography>
              <Typography sx={{ color: c.text.tertiary, fontSize: '0.72rem', lineHeight: 1.35 }}>
                {option.shortDescription}
              </Typography>
            </Box>
          </MenuItem>
        ))}
      </Menu>
    </>
  );
};

export default SwarmModePicker;
