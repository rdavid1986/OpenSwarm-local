import React from 'react';
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
import type { SwarmMode } from '@/shared/state/dashboardLayoutSlice';

export const DEFAULT_SWARM_MODE: SwarmMode = 'ask';

export interface SwarmModeOption {
  id: SwarmMode;
  label: string;
  shortDescription: string;
  placeholder: string;
  color: string;
  icon: React.ReactNode;
}

export const SWARM_MODE_OPTIONS: SwarmModeOption[] = [
  {
    id: 'ask',
    label: 'Ask',
    shortDescription: 'Chat normal; no inicia intake.',
    placeholder: 'Ask Swarm…',
    color: '#3b82f6',
    icon: <ChatBubbleOutlineIcon sx={{ fontSize: 16 }} />,
  },
  {
    id: 'plan',
    label: 'Plan',
    shortDescription: 'Plan liviano, sin implementación.',
    placeholder: 'Describe qué querés planificar…',
    color: '#8b5cf6',
    icon: <FactCheckOutlinedIcon sx={{ fontSize: 16 }} />,
  },
  {
    id: 'app_builder',
    label: 'App Builder',
    shortDescription: 'Inicia el intake actual de app.',
    placeholder: 'Describe la app que querés construir…',
    color: '#10b981',
    icon: <AppsOutlinedIcon sx={{ fontSize: 16 }} />,
  },
  {
    id: 'skill_builder',
    label: 'Skill Builder',
    shortDescription: 'Borrador de skill; sin AgentManager.',
    placeholder: 'Describe la skill o agente que querés diseñar…',
    color: '#f59e0b',
    icon: <ExtensionOutlinedIcon sx={{ fontSize: 16 }} />,
  },
  {
    id: 'debug',
    label: 'Debug',
    shortDescription: 'Diagnóstico orientado a estado/logs.',
    placeholder: 'Describe el error o síntoma a diagnosticar…',
    color: '#ef4444',
    icon: <BugReportOutlinedIcon sx={{ fontSize: 16 }} />,
  },
];

export function getSwarmModeOption(mode?: string | null): SwarmModeOption {
  return SWARM_MODE_OPTIONS.find((option) => option.id === mode) || SWARM_MODE_OPTIONS[0];
}

interface Props {
  mode: SwarmMode;
  onChange: (mode: SwarmMode) => void;
  disabled?: boolean;
}

const SwarmModePicker: React.FC<Props> = ({ mode, onChange, disabled = false }) => {
  const c = useClaudeTokens();
  const [anchorEl, setAnchorEl] = React.useState<HTMLElement | null>(null);
  const selected = getSwarmModeOption(mode);

  return (
    <>
      <Button
        size="small"
        onClick={(event) => setAnchorEl(event.currentTarget)}
        disabled={disabled}
        startIcon={selected.icon}
        endIcon={<ExpandMoreIcon sx={{ fontSize: 16 }} />}
        sx={{
          minHeight: 28,
          px: 1,
          py: 0.25,
          borderRadius: 999,
          color: selected.color,
          bgcolor: `${selected.color}14`,
          border: `1px solid ${selected.color}44`,
          textTransform: 'none',
          fontSize: '0.74rem',
          fontWeight: 650,
          '&:hover': { bgcolor: `${selected.color}22` },
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
        {SWARM_MODE_OPTIONS.map((option) => (
          <MenuItem
            key={option.id}
            selected={option.id === mode}
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
