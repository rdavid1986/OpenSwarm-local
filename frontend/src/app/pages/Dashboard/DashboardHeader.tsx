import React, { useState, useRef, useEffect, useCallback } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import InputBase from '@mui/material/InputBase';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import DashboardIcon from '@mui/icons-material/Dashboard';
import SmartToyOutlinedIcon from '@mui/icons-material/SmartToyOutlined';
import GridViewRoundedIcon from '@mui/icons-material/GridViewRounded';
import LanguageIcon from '@mui/icons-material/Language';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import EditIcon from '@mui/icons-material/Edit';
import CheckIcon from '@mui/icons-material/Check';
import CloseIcon from '@mui/icons-material/Close';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import { useClaudeTokens } from '@/shared/styles/ThemeContext';
import type { AgentSession } from '@/shared/state/agentsSlice';
import type { CardPosition, ViewCardPosition, BrowserCardPosition } from '@/shared/state/dashboardLayoutSlice';
import type { Output } from '@/shared/state/outputsSlice';
import type { CanvasActions } from './useCanvasControls';

interface DashboardHeaderProps {
  dashboardName: string | undefined;
  sessions: Record<string, AgentSession>;
  cards: Record<string, CardPosition>;
  viewCards: Record<string, ViewCardPosition>;
  browserCards: Record<string, BrowserCardPosition>;
  outputs: Record<string, Output>;
  dashboardId: string | undefined;
  canvasActions: CanvasActions;
  onHighlightCard?: (cardId: string) => void;
  onRenameDashboard?: (name: string) => void;
  onOpenWorkspace?: () => void;
  workspacePath?: string | null;
  workspaceLoading?: boolean;
}

const STATUS_DOT: Record<string, string> = {
  running: '#22c55e',
  waiting_approval: '#f59e0b',
  completed: '#94a3b8',
  error: '#ef4444',
  stopped: '#94a3b8',
  draft: '#6366f1',
};

const DashboardHeader: React.FC<DashboardHeaderProps> = ({
  dashboardName,
  sessions,
  cards,
  viewCards,
  browserCards,
  outputs,
  dashboardId,
  canvasActions,
  onHighlightCard,
  onRenameDashboard,
  onOpenWorkspace,
  workspacePath,
  workspaceLoading = false,
}) => {
  const c = useClaudeTokens();
  const [expanded, setExpanded] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draftName, setDraftName] = useState('');
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const agentItems = Object.values(cards)
    .map((card) => {
      const session = sessions[card.session_id];
      if (!session || session.status === 'draft') return null;
      return { id: card.session_id, name: session.name, status: session.status, model: session.model, card };
    })
    .filter(Boolean) as Array<{ id: string; name: string; status: string; model: string; card: CardPosition }>;

  const viewItems = Object.values(viewCards)
    .map((vc) => {
      const output = outputs[vc.output_id];
      if (!output) return null;
      return { id: vc.output_id, name: output.name, card: vc };
    })
    .filter(Boolean) as Array<{ id: string; name: string; card: ViewCardPosition }>;

  const browserItems = Object.values(browserCards).map((bc) => {
    const activeTab = bc.tabs.find((t) => t.id === bc.activeTabId);
    return {
      id: bc.browser_id,
      title: activeTab?.title || 'New Tab',
      url: activeTab?.url || bc.url,
      card: bc,
    };
  });

  const hasItems = agentItems.length > 0 || viewItems.length > 0 || browserItems.length > 0;

  useEffect(() => {
    if (!expanded) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setExpanded(false);
      }
    };
    const timer = setTimeout(() => document.addEventListener('mousedown', handleClickOutside), 0);
    return () => {
      clearTimeout(timer);
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [expanded]);

  const handleFocus = useCallback(
    (cardId: string, card: { x: number; y: number; width: number; height: number }) => {
      canvasActions.fitToCards([card], 1.15, true);
      onHighlightCard?.(cardId);
      setExpanded(false);
    },
    [canvasActions, onHighlightCard],
  );

  const toggle = useCallback(() => {
    if (!editing && hasItems) setExpanded((v) => !v);
  }, [editing, hasItems]);

  const startEditing = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    setExpanded(false);
    setDraftName(dashboardName || 'Dashboard');
    setEditing(true);
    window.setTimeout(() => inputRef.current?.focus(), 0);
  }, [dashboardName]);

  const cancelEditing = useCallback((e?: React.MouseEvent) => {
    e?.stopPropagation();
    setEditing(false);
    setDraftName('');
  }, []);

  const submitEditing = useCallback((e?: React.MouseEvent) => {
    e?.stopPropagation();
    const trimmed = draftName.trim();
    if (trimmed && trimmed !== dashboardName) {
      onRenameDashboard?.(trimmed);
    }
    setEditing(false);
  }, [dashboardName, draftName, onRenameDashboard]);

  const handleOpenWorkspace = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    onOpenWorkspace?.();
  }, [onOpenWorkspace]);

  const workspaceDisabled = !workspacePath || workspaceLoading || !onOpenWorkspace;

  return (
    <Box ref={containerRef} sx={{ position: 'relative', display: 'inline-flex', flexDirection: 'column' }}>
      <Box
        onClick={toggle}
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          bgcolor: c.bg.surface,
          border: `1px solid ${c.border.medium}`,
          borderRadius: expanded ? `${c.radius.lg}px ${c.radius.lg}px 0 0` : `${c.radius.lg}px`,
          boxShadow: c.shadow.sm,
          py: 0.75,
          px: 1.5,
          cursor: hasItems ? 'pointer' : 'default',
          userSelect: 'none',
          transition: 'border-radius 0.2s',
          '&:hover': hasItems ? { bgcolor: c.bg.secondary } : {},
        }}
      >
        <DashboardIcon sx={{ fontSize: 'small', color: c.accent.primary }} />
        {editing ? (
          <InputBase
            inputRef={inputRef}
            value={draftName}
            onChange={(e) => setDraftName(e.target.value)}
            onClick={(e) => e.stopPropagation()}
            onPointerDown={(e) => e.stopPropagation()}
            onKeyDown={(e) => {
              e.stopPropagation();
              if (e.key === 'Enter') submitEditing();
              if (e.key === 'Escape') cancelEditing();
            }}
            sx={{
              width: 220,
              fontSize: '0.9rem',
              fontWeight: 600,
              color: c.text.primary,
              lineHeight: 1,
            }}
          />
        ) : (
          <Typography
            sx={{
              fontSize: '0.9rem',
              fontWeight: 600,
              color: c.text.primary,
              lineHeight: 1,
              maxWidth: 280,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {dashboardName || 'Dashboard'}
          </Typography>
        )}
        {editing ? (
          <>
            <IconButton
              size="small"
              onClick={submitEditing}
              onPointerDown={(e) => e.stopPropagation()}
              sx={{ p: 0.25, color: c.status.success }}
            >
              <CheckIcon sx={{ fontSize: 16 }} />
            </IconButton>
            <IconButton
              size="small"
              onClick={cancelEditing}
              onPointerDown={(e) => e.stopPropagation()}
              sx={{ p: 0.25, color: c.text.muted }}
            >
              <CloseIcon sx={{ fontSize: 16 }} />
            </IconButton>
          </>
        ) : (
          <>
            <Tooltip title="Rename dashboard">
              <IconButton
                size="small"
                onClick={startEditing}
                onPointerDown={(e) => e.stopPropagation()}
                sx={{ p: 0.25, color: c.text.muted, '&:hover': { color: c.text.primary } }}
              >
                <EditIcon sx={{ fontSize: 15 }} />
              </IconButton>
            </Tooltip>
            <Tooltip title={workspaceDisabled ? 'Workspace no disponible todavía' : workspacePath}>
              <span>
                <IconButton
                  size="small"
                  onClick={handleOpenWorkspace}
                  onPointerDown={(e) => e.stopPropagation()}
                  disabled={workspaceDisabled}
                  sx={{ p: 0.25, color: c.text.muted, '&:hover': { color: c.accent.primary } }}
                >
                  <FolderOpenIcon sx={{ fontSize: 16 }} />
                </IconButton>
              </span>
            </Tooltip>
          </>
        )}
        {hasItems && (
          <KeyboardArrowDownIcon
            sx={{
              fontSize: 18,
              color: c.text.tertiary,
              transition: 'transform 0.2s',
              transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
              ml: 0.25,
            }}
          />
        )}
      </Box>

      {/* Dropdown overlay */}
      {hasItems && (
        <Box
          sx={{
            position: 'absolute',
            top: '100%',
            left: 0,
            zIndex: 100,
            minWidth: 280,
            maxWidth: 360,
            maxHeight: expanded ? 400 : 0,
            overflow: 'hidden',
            transition: 'max-height 0.25s ease-in-out',
          }}
        >
          <Box
            sx={{
              bgcolor: c.bg.surface,
              border: `1px solid ${c.border.medium}`,
              borderTop: 'none',
              borderRadius: `0 0 ${c.radius.lg}px ${c.radius.lg}px`,
              boxShadow: c.shadow.md,
              py: 0.75,
              overflowY: 'auto',
              maxHeight: 380,
            }}
          >
            {agentItems.length > 0 && (
              <CategoryGroup icon={<SmartToyOutlinedIcon />} label="Agents" count={agentItems.length} c={c}>
                {agentItems.map((item) => (
                  <ItemRow key={item.id} onClick={() => handleFocus(item.id, item.card)} c={c}>
                    <Box
                      sx={{
                        width: 7,
                        height: 7,
                        borderRadius: '50%',
                        bgcolor: STATUS_DOT[item.status] || c.text.tertiary,
                        flexShrink: 0,
                        mt: '1px',
                      }}
                    />
                    <Typography
                      noWrap
                      sx={{ fontSize: '0.8rem', color: c.text.primary, flex: 1, minWidth: 0 }}
                    >
                      {item.name}
                    </Typography>
                    <Typography
                      sx={{ fontSize: '0.7rem', color: c.text.ghost, flexShrink: 0 }}
                    >
                      {item.status.replace('_', ' ')}
                    </Typography>
                  </ItemRow>
                ))}
              </CategoryGroup>
            )}

            {viewItems.length > 0 && (
              <CategoryGroup icon={<GridViewRoundedIcon />} label="Views" count={viewItems.length} c={c}>
                {viewItems.map((item) => (
                  <ItemRow key={item.id} onClick={() => handleFocus(item.id, item.card)} c={c}>
                    <Typography
                      noWrap
                      sx={{ fontSize: '0.8rem', color: c.text.primary, flex: 1, minWidth: 0 }}
                    >
                      {item.name}
                    </Typography>
                  </ItemRow>
                ))}
              </CategoryGroup>
            )}

            {browserItems.length > 0 && (
              <CategoryGroup icon={<LanguageIcon />} label="Browsers" count={browserItems.length} c={c}>
                {browserItems.map((item) => (
                  <ItemRow key={item.id} onClick={() => handleFocus(item.id, item.card)} c={c}>
                    <Typography
                      noWrap
                      sx={{ fontSize: '0.8rem', color: c.text.primary, flex: 1, minWidth: 0 }}
                    >
                      {item.title}
                    </Typography>
                    <Typography
                      noWrap
                      sx={{ fontSize: '0.68rem', color: c.text.ghost, maxWidth: 120, flexShrink: 0 }}
                    >
                      {cleanUrl(item.url)}
                    </Typography>
                  </ItemRow>
                ))}
              </CategoryGroup>
            )}
          </Box>
        </Box>
      )}
    </Box>
  );
};

function cleanUrl(url: string): string {
  try {
    const u = new URL(url);
    return u.hostname + (u.pathname !== '/' ? u.pathname : '');
  } catch {
    return url;
  }
}

const CategoryGroup: React.FC<{
  icon: React.ReactNode;
  label: string;
  count: number;
  c: ReturnType<typeof useClaudeTokens>;
  children: React.ReactNode;
}> = ({ icon, label, count, c, children }) => (
  <Box sx={{ '&:not(:first-of-type)': { borderTop: `1px solid ${c.border.subtle}`, mt: 0.5, pt: 0.5 } }}>
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 0.75,
        px: 1.5,
        py: 0.5,
      }}
    >
      <Box sx={{ display: 'flex', color: c.text.tertiary, '& > svg': { fontSize: 15 } }}>{icon}</Box>
      <Typography sx={{ fontSize: '0.72rem', fontWeight: 600, color: c.text.tertiary, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
        {label}
      </Typography>
      <Typography sx={{ fontSize: '0.68rem', color: c.text.ghost }}>
        {count}
      </Typography>
    </Box>
    {children}
  </Box>
);

const ItemRow: React.FC<{
  onClick: () => void;
  c: ReturnType<typeof useClaudeTokens>;
  children: React.ReactNode;
}> = ({ onClick, c, children }) => (
  <Box
    onClick={onClick}
    sx={{
      display: 'flex',
      alignItems: 'center',
      gap: 0.75,
      px: 1.5,
      pl: 3.25,
      py: 0.4,
      cursor: 'pointer',
      borderRadius: 0.5,
      mx: 0.5,
      '&:hover': { bgcolor: c.bg.secondary },
      transition: 'background-color 0.1s',
    }}
  >
    {children}
  </Box>
);

export default React.memo(DashboardHeader);
