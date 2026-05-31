import React from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import TextField from '@mui/material/TextField';
import ClickAwayListener from '@mui/material/ClickAwayListener';
import Button from '@mui/material/Button';
import CloseIcon from '@mui/icons-material/Close';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import CheckIcon from '@mui/icons-material/Check';
import DragIndicatorIcon from '@mui/icons-material/DragIndicator';
import { useClaudeTokens } from '@/shared/styles/ThemeContext';

export interface TaskQueueItem {
  id: string;
  prompt: string;
  status?: 'queued' | 'running' | 'blocked';
  meta?: string;
}

interface TaskQueuePanelProps {
  items: TaskQueueItem[];
  expanded: boolean;
  onExpandedChange: (expanded: boolean) => void;
  editingIndex: number | null;
  editingText: string;
  onEditingIndexChange: (index: number | null) => void;
  onEditingTextChange: (value: string) => void;
  dragIndex: number | null;
  dropTargetIndex: number | null;
  onDragIndexChange: (index: number | null) => void;
  onDropTargetIndexChange: (index: number | null) => void;
  onClear: () => void;
  onRemove: (index: number) => void;
  onEdit: (index: number, prompt: string) => void;
  onMove: (fromIndex: number, toIndex: number) => void;
  label?: string;
}

export default function TaskQueuePanel({
  items,
  expanded,
  onExpandedChange,
  editingIndex,
  editingText,
  onEditingIndexChange,
  onEditingTextChange,
  dragIndex,
  dropTargetIndex,
  onDragIndexChange,
  onDropTargetIndexChange,
  onClear,
  onRemove,
  onEdit,
  onMove,
  label = 'Follow-up queue',
}: TaskQueuePanelProps) {
  const c = useClaudeTokens();
  if (items.length === 0) return null;

  const finishEdit = (idx: number) => {
    const trimmed = editingText.trim();
    if (trimmed) onEdit(idx, trimmed);
    onEditingIndexChange(null);
  };

  return (
    <ClickAwayListener onClickAway={() => { if (expanded) { onExpandedChange(false); onEditingIndexChange(null); } }}>
      <Box sx={{ ml: 3, mr: 1.5 }}>
        <Box
          onClick={() => { onExpandedChange(!expanded); onEditingIndexChange(null); }}
          sx={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 0.5,
            px: 1.25,
            py: 0.25,
            borderRadius: '8px 8px 0 0',
            bgcolor: c.bg.surface,
            border: `1px solid ${c.border.subtle}`,
            borderBottom: 'none',
            cursor: 'pointer',
            userSelect: 'none',
            '&:hover': { bgcolor: c.bg.secondary },
            transition: 'background 0.12s',
          }}
        >
          {expanded
            ? <KeyboardArrowDownIcon sx={{ fontSize: 12, color: c.text.tertiary }} />
            : <KeyboardArrowUpIcon sx={{ fontSize: 12, color: c.text.tertiary }} />
          }
          <Typography sx={{ fontSize: '0.68rem', fontWeight: 700, color: c.text.muted, letterSpacing: 0.2 }}>
            {label}: {items.length} queued
          </Typography>
          <Tooltip title="Clear all queued follow-ups">
            <IconButton
              size="small"
              onClick={(e) => { e.stopPropagation(); onClear(); }}
              sx={{ p: 0.15, color: c.text.tertiary, '&:hover': { color: c.status.error } }}
            >
              <CloseIcon sx={{ fontSize: 10 }} />
            </IconButton>
          </Tooltip>
        </Box>

        {expanded && (
          <Box
            sx={{
              bgcolor: c.bg.surface,
              border: `1px solid ${c.border.subtle}`,
              borderBottom: 'none',
              borderRadius: '0 8px 0 0',
              maxHeight: 260,
              overflowY: 'auto',
              boxShadow: c.shadow.sm,
              '&::-webkit-scrollbar': { width: 4 },
              '&::-webkit-scrollbar-thumb': { background: c.border.medium, borderRadius: 2 },
            }}
          >
            <Box sx={{ px: 1.5, py: 0.75, display: 'flex', flexWrap: 'wrap', gap: 0.5, borderBottom: `1px solid ${c.border.subtle}` }}>
              <Typography sx={{ color: c.text.tertiary, fontSize: '0.68rem', flex: 1, minWidth: 180 }}>
                Real queue: items run after the current turn finishes. Drag, edit, remove, or clear only affects queued prompts.
              </Typography>
              <Tooltip title="Pause/convert requires a real scheduler; no background worker is enabled here.">
                <span><Button size="small" disabled sx={{ minHeight: 22, py: 0, px: 0.8, fontSize: '0.65rem', textTransform: 'none' }}>Pause</Button></span>
              </Tooltip>
              <Tooltip title="Convert to scheduled task is not wired without a scheduler/backend contract.">
                <span><Button size="small" disabled sx={{ minHeight: 22, py: 0, px: 0.8, fontSize: '0.65rem', textTransform: 'none' }}>Convert</Button></span>
              </Tooltip>
            </Box>
            {items.map((item, idx) => (
              <Box
                key={item.id}
                draggable={editingIndex !== idx}
                onDragStart={(e) => {
                  onDragIndexChange(idx);
                  e.dataTransfer.effectAllowed = 'move';
                }}
                onDragOver={(e) => {
                  e.preventDefault();
                  e.dataTransfer.dropEffect = 'move';
                  if (dragIndex !== null && dragIndex !== idx) onDropTargetIndexChange(idx);
                }}
                onDragLeave={() => { if (dropTargetIndex === idx) onDropTargetIndexChange(null); }}
                onDrop={(e) => {
                  e.preventDefault();
                  if (dragIndex !== null && dragIndex !== idx) onMove(dragIndex, idx);
                  onDragIndexChange(null);
                  onDropTargetIndexChange(null);
                }}
                onDragEnd={() => { onDragIndexChange(null); onDropTargetIndexChange(null); }}
                sx={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 0.75,
                  px: 1.5,
                  py: 1,
                  borderBottom: idx < items.length - 1 ? `1px solid ${c.border.subtle}` : 'none',
                  '&:hover': { bgcolor: c.bg.secondary },
                  transition: 'background 0.1s, opacity 0.15s',
                  ...(dragIndex === idx ? { opacity: 0.35 } : {}),
                  ...(dropTargetIndex === idx && dragIndex !== null && dragIndex !== idx ? { borderTop: `2px solid ${c.accent.primary}` } : {}),
                }}
              >
                <Box sx={{ cursor: editingIndex === idx ? 'default' : 'grab', display: 'flex', alignItems: 'center', mt: 0.3, color: c.text.ghost, '&:hover': { color: c.text.tertiary }, '&:active': { cursor: 'grabbing' } }}>
                  <DragIndicatorIcon sx={{ fontSize: 14 }} />
                </Box>
                {editingIndex === idx ? (
                  <Box sx={{ flex: 1, display: 'flex', gap: 0.5, alignItems: 'flex-start' }}>
                    <TextField
                      multiline
                      fullWidth
                      size="small"
                      value={editingText}
                      onChange={(e) => onEditingTextChange(e.target.value)}
                      autoFocus
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                          e.preventDefault();
                          finishEdit(idx);
                        }
                        if (e.key === 'Escape') onEditingIndexChange(null);
                      }}
                      sx={{
                        '& .MuiOutlinedInput-root': {
                          fontSize: '0.78rem',
                          color: c.text.primary,
                          '& fieldset': { borderColor: c.border.medium },
                          '&.Mui-focused fieldset': { borderColor: c.accent.primary },
                        },
                      }}
                    />
                    <IconButton size="small" onClick={() => finishEdit(idx)} sx={{ p: 0.25, color: c.accent.primary, mt: 0.25 }}>
                      <CheckIcon sx={{ fontSize: 14 }} />
                    </IconButton>
                  </Box>
                ) : (
                  <Box sx={{ flex: 1, minWidth: 0 }}>
                    <Typography sx={{ fontSize: '0.78rem', color: c.text.secondary, lineHeight: 1.5, overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', wordBreak: 'break-word' }}>
                      {item.prompt}
                    </Typography>
                    {item.meta && <Typography sx={{ mt: 0.2, color: c.text.ghost, fontSize: '0.65rem' }}>{item.meta}</Typography>}
                  </Box>
                )}
                {editingIndex !== idx && (
                  <Box sx={{ display: 'flex', gap: 0.25, flexShrink: 0, mt: 0.15 }}>
                    <Tooltip title="Edit queued prompt">
                      <IconButton size="small" onClick={() => { onEditingIndexChange(idx); onEditingTextChange(item.prompt); }} sx={{ p: 0.25, color: c.text.tertiary, '&:hover': { color: c.text.primary } }}>
                        <EditOutlinedIcon sx={{ fontSize: 13 }} />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Remove queued prompt">
                      <IconButton size="small" onClick={() => onRemove(idx)} sx={{ p: 0.25, color: c.text.tertiary, '&:hover': { color: c.status.error } }}>
                        <DeleteOutlineIcon sx={{ fontSize: 13 }} />
                      </IconButton>
                    </Tooltip>
                  </Box>
                )}
              </Box>
            ))}
          </Box>
        )}
      </Box>
    </ClickAwayListener>
  );
}
