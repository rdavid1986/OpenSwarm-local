import React, { useCallback, useMemo, useRef, useState } from 'react';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import IconButton from '@mui/material/IconButton';
import InputBase from '@mui/material/InputBase';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import HourglassEmptyIcon from '@mui/icons-material/HourglassEmpty';
import AdsClickOutlinedIcon from '@mui/icons-material/AdsClickOutlined';
import AttachFileIcon from '@mui/icons-material/AttachFile';
import MicNoneIcon from '@mui/icons-material/MicNone';
import TuneOutlinedIcon from '@mui/icons-material/TuneOutlined';
import CloseIcon from '@mui/icons-material/Close';
import CommandPicker, { CommandPickerItem, getToolGroupIcon } from '@/app/components/CommandPicker';
import { useElementSelection } from '@/app/components/ElementSelectionContext';
import ModelPicker from '@/app/components/ModelPicker';
import SwarmModePicker, { getSwarmModeOption } from './SwarmModePicker';
import { API_BASE } from '@/shared/config';
import { useClaudeTokens } from '@/shared/styles/ThemeContext';
import type { SwarmMode } from '@/shared/state/dashboardLayoutSlice';
import type { ContextPath } from '@/app/components/DirectoryBrowser';
import {
  createDisabledVoiceState,
  contextRefFromPath,
  selectionRefFromElement,
  toolRefFromNames,
  type UnifiedComposerState,
  type UnifiedComposerSubmitPayload,
  type UnifiedComposerToolRef,
} from '@/shared/types/unifiedComposer';

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
  onSend: (payload?: UnifiedComposerSubmitPayload) => void;
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
  placeholderOverride?: string;
  ownerId?: string;
  cardId?: string;
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
  placeholderOverride,
  ownerId,
  cardId,
}) => {
  const c = useClaudeTokens();
  const elementSelection = useElementSelection();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const fallbackOwnerIdRef = useRef(`swarm-composer-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`);
  const composerOwnerId = ownerId || cardId || fallbackOwnerIdRef.current;
  const [contextPaths, setContextPaths] = useState<ContextPath[]>([]);
  const [forcedTools, setForcedTools] = useState<Array<{ label: string; tools: string[]; icon?: React.ReactNode; iconKey?: string }>>([]);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const modeOption = getSwarmModeOption(mode);
  const selectedModel = model || modelLabel || '';
  const selectedElements = elementSelection?.elementsByOwner?.[composerOwnerId] ?? [];
  const voiceState = useMemo(() => createDisabledVoiceState(), []);
  const submitDisabled = disabled || loading || (!value.trim() && !canContinue);
  const placeholder = placeholderOverride || (customIntakeMode ? 'Escribí tu respuesta personalizada…' : modeOption.placeholder);
  const contextRefs = useMemo(() => (
    contextPaths.map((cp) => contextRefFromPath(cp.path, cp.type === 'directory' ? 'directory' : 'file', 'upload'))
  ), [contextPaths]);
  const selectedToolRefs = useMemo<UnifiedComposerToolRef[]>(() => (
    forcedTools.map((tool) => toolRefFromNames(tool.label, tool.tools, tool.iconKey))
  ), [forcedTools]);
  const selectionRefs = useMemo(() => (
    selectedElements.map((el) => selectionRefFromElement(el, composerOwnerId))
  ), [composerOwnerId, selectedElements]);
  const attachmentRefs = useMemo(() => contextRefs.map((ref) => ({ ...ref, source: ref.source === 'upload' ? 'upload' as const : 'existing' as const })), [contextRefs]);
  const unifiedComposerState: UnifiedComposerState = useMemo(() => ({
    source_surface: 'swarm',
    owner_id: composerOwnerId,
    card_id: cardId,
    mode,
    model: selectedModel || null,
    prompt: value,
    loading,
    disabled,
    disabled_reasons: disabled ? [{ code: 'running', message: 'Swarm composer is disabled by the current card state.' }] : [],
    tools_available: [],
    tools_selected: selectedToolRefs,
    context_refs: contextRefs,
    attachment_refs: attachmentRefs,
    selected_ui_elements: selectionRefs,
    voice: voiceState,
    can_submit: !submitDisabled,
    can_stop: false,
    pending_action_capability: 'disabled',
    evidence_refs: [],
    trace_refs: [],
  }), [attachmentRefs, cardId, composerOwnerId, contextRefs, disabled, loading, mode, selectedModel, selectedToolRefs, selectionRefs, submitDisabled, value, voiceState]);

  const uploadAndAttachFiles = useCallback(async (files: File[]) => {
    if (files.length === 0) return;
    setIsUploading(true);
    try {
      const formData = new FormData();
      files.forEach((file) => formData.append('files', file));
      const resp = await fetch(`${API_BASE}/settings/upload-files`, { method: 'POST', body: formData });
      if (!resp.ok) throw new Error('Upload failed');
      const data = await resp.json();
      const newPaths: ContextPath[] = (data.files || []).map((file: { path: string }) => ({ path: file.path, type: 'file' as const }));
      setContextPaths((prev) => [...prev, ...newPaths]);
    } catch (error) {
      console.error('Swarm file attach failed:', error);
    } finally {
      setIsUploading(false);
    }
  }, []);

  const handlePickerSelect = useCallback((item: CommandPickerItem) => {
    if (item.type === 'context' && item.command === 'file') {
      fileInputRef.current?.click();
    } else if (item.type === 'context' && item.toolNames?.length) {
      setForcedTools((prev) => [...prev, { label: item.name, tools: item.toolNames!, icon: item.icon, iconKey: item.iconKey }]);
    }
    setPickerOpen(false);
  }, []);

  const buildSubmitPayload = useCallback((): UnifiedComposerSubmitPayload => ({
    source_surface: 'swarm',
    owner_id: composerOwnerId,
    card_id: cardId,
    mode,
    model: selectedModel || null,
    prompt: value.trim() || 'Continue',
    context_refs: contextRefs,
    attachment_refs: attachmentRefs,
    selected_ui_elements: selectionRefs,
    selected_tools: selectedToolRefs,
    selected_tool_names: selectedToolRefs.flatMap((tool) => tool.tool_names),
    voice: voiceState,
    evidence_refs: [],
    trace_refs: [],
  }), [attachmentRefs, cardId, composerOwnerId, contextRefs, mode, selectedModel, selectedToolRefs, selectionRefs, value, voiceState]);

  const handleSubmit = useCallback(() => {
    if (submitDisabled) return;
    onSend(buildSubmitPayload());
    setContextPaths([]);
    setForcedTools([]);
    elementSelection?.clearOwnerElements(composerOwnerId);
  }, [buildSubmitPayload, composerOwnerId, elementSelection, onSend, submitDisabled]);

  const isSelectingForThisSwarm = Boolean(elementSelection?.selectMode && elementSelection.activeOwnerId === composerOwnerId);

  return (
    <Box
      sx={{
        maxWidth: embedded ? '100%' : 860,
        mx: embedded ? 0 : 'auto',
        border: `1px solid ${c.border.subtle}`,
        borderRadius: '16px',
        bgcolor: c.bg.surface,
        boxShadow: embedded ? 'none' : c.shadow.md,
        transition: 'border-color 0.15s ease, box-shadow 0.15s ease, background 0.15s ease',
        position: 'relative',
      }}
      data-composer-surface={unifiedComposerState.source_surface}
      data-composer-owner-id={unifiedComposerState.owner_id}
    >
      <CommandPicker trigger="@" filter="" visible={pickerOpen} onSelect={handlePickerSelect} onClose={() => setPickerOpen(false)} />
      <Box onPointerDown={(e) => e.stopPropagation()} onClick={(e) => e.stopPropagation()} sx={{ px: 1.5, pt: 1.25, pb: 0.25 }}>
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
              handleSubmit();
            }
          }}
          onKeyUpCapture={(e) => e.stopPropagation()}
          onKeyDown={(e) => e.stopPropagation()}
          placeholder={placeholder}
          sx={{ fontSize: '0.95rem', color: c.text.primary, lineHeight: 1.55 }}
        />
      </Box>

      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.25, px: 1, pb: 0.75, pt: 0 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, minWidth: 0, flexWrap: 'wrap' }}>
          <SwarmModePicker mode={mode} onChange={onModeChange} disabled={disabled || loading} />
          {selectedModel && (
            <ModelPicker model={selectedModel} onModelChange={(nextModel) => onModelChange?.(nextModel)} disabled={disabled || loading || !onModelChange} compact />
          )}
          <Tooltip title={isSelectingForThisSwarm ? 'Exit select mode' : 'Select UI element for this Swarm'}>
            <span>
              <IconButton
                size="small"
                disabled={!elementSelection || disabled || loading}
                onClick={() => {
                  if (!elementSelection) return;
                  if (isSelectingForThisSwarm) {
                    elementSelection.setSelectMode(false);
                  } else {
                    elementSelection.setActiveOwnerId(composerOwnerId);
                    elementSelection.setExcludeSelectId(cardId || composerOwnerId);
                    elementSelection.setSelectMode(true);
                  }
                }}
                sx={{ width: 26, height: 26, p: 0.5, bgcolor: isSelectingForThisSwarm ? '#3b82f6' : 'transparent', color: isSelectingForThisSwarm ? '#fff' : c.text.tertiary }}
              >
                <AdsClickOutlinedIcon sx={{ fontSize: 16 }} />
              </IconButton>
            </span>
          </Tooltip>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            hidden
            onChange={(e) => {
              const files = Array.from(e.target.files || []);
              uploadAndAttachFiles(files);
              e.target.value = '';
            }}
          />
          <Tooltip title="Attach files as context refs">
            <span>
              <IconButton size="small" disabled={disabled || loading || isUploading} onClick={() => fileInputRef.current?.click()} sx={{ width: 26, height: 26, p: 0.5 }}>
                {isUploading ? <CircularProgress size={14} /> : <AttachFileIcon sx={{ fontSize: 16 }} />}
              </IconButton>
            </span>
          </Tooltip>
          <Tooltip title="Tools/actions selection only; no execution or MCP activation">
            <span>
              <IconButton size="small" disabled={disabled || loading} onClick={() => setPickerOpen((open) => !open)} sx={{ width: 26, height: 26, p: 0.5 }}>
                <TuneOutlinedIcon sx={{ fontSize: 16 }} />
              </IconButton>
            </span>
          </Tooltip>
          <Tooltip title={voiceState.disabled_reason?.message || 'Voice input disabled'}>
            <span>
              <IconButton size="small" disabled sx={{ width: 26, height: 26, p: 0.5 }}>
                <MicNoneIcon sx={{ fontSize: 16 }} />
              </IconButton>
            </span>
          </Tooltip>
        </Box>

        <Box sx={{ flex: 1 }} />

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          {contextEstimate && <ContextRing used={contextEstimate.used} limit={contextEstimate.limit} accentColor={c.accent.primary} trackColor={c.border.subtle} />}
          <Typography sx={{ color: c.text.tertiary, fontSize: '0.72rem', display: { xs: 'none', sm: 'block' } }}>
            Shift+Enter
          </Typography>
          <IconButton
            size="small"
            onClick={handleSubmit}
            disabled={submitDisabled}
            sx={{
              bgcolor: c.accent.primary,
              color: c.text.inverse,
              p: 0.5,
              width: 26,
              height: 26,
              '&:hover': { bgcolor: c.accent.hover },
              '&.Mui-disabled': { bgcolor: c.bg.secondary, color: c.text.ghost },
            }}
          >
            {loading ? (
              <HourglassEmptyIcon
                sx={{
                  fontSize: 16,
                  animation: 'swarmComposerHourglassClockwise 1.1s linear infinite',
                  '@keyframes swarmComposerHourglassClockwise': {
                    '0%': { transform: 'rotate(0deg)' },
                    '100%': { transform: 'rotate(360deg)' },
                  },
                }}
              />
            ) : <ArrowUpwardIcon sx={{ fontSize: 16 }} />}
          </IconButton>
        </Box>
      </Box>

      {(contextRefs.length > 0 || selectedToolRefs.length > 0 || selectionRefs.length > 0) && (
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, px: 1.5, pb: 0.75 }}>
          {contextRefs.map((ref, idx) => (
            <Chip key={`ctx-${ref.id}-${idx}`} size="small" icon={<AttachFileIcon sx={{ fontSize: 14 }} />} label={ref.label} onDelete={() => setContextPaths((prev) => prev.filter((_, i) => i !== idx))} sx={{ height: 24, fontSize: '0.7rem', color: c.accent.primary, bgcolor: `${c.accent.primary}12`, fontFamily: c.font.mono }} />
          ))}
          {selectedToolRefs.map((tool, idx) => (
            <Chip key={`tool-${tool.id}-${idx}`} size="small" icon={<>{getToolGroupIcon(tool.icon_key || tool.label, 14)}</>} label={`@${tool.label.toLowerCase()}`} onDelete={() => setForcedTools((prev) => prev.filter((_, i) => i !== idx))} sx={{ height: 24, fontSize: '0.7rem', color: c.status.info, bgcolor: `${c.status.info}15`, fontFamily: c.font.mono }} />
          ))}
          {selectionRefs.map((ref) => (
            <Chip key={ref.id} size="small" icon={<AdsClickOutlinedIcon sx={{ fontSize: 14 }} />} label={ref.label} onDelete={() => elementSelection?.removeOwnerElement(composerOwnerId, ref.id)} sx={{ height: 24, fontSize: '0.7rem', color: '#3b82f6', bgcolor: 'rgba(59, 130, 246, 0.1)', fontFamily: c.font.mono }} />
          ))}
          <Tooltip title="Clear composer refs">
            <IconButton
              size="small"
              onClick={() => {
                setContextPaths([]);
                setForcedTools([]);
                elementSelection?.clearOwnerElements(composerOwnerId);
              }}
              sx={{ width: 22, height: 22, color: c.text.tertiary }}
            >
              <CloseIcon sx={{ fontSize: 14 }} />
            </IconButton>
          </Tooltip>
        </Box>
      )}
    </Box>
  );
};

export default SwarmPromptInput;
