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
import ComposerContextPreview from '@/app/components/ComposerContextPreview';
import ChatDebugContextView from '@/app/components/ChatDebugContextView';
import ProjectMemoryContextPanel from '@/app/components/ProjectMemoryContextPanel';
import PromptSkillAuthoringPanel from '@/app/components/PromptSkillAuthoringPanel';
import ComposerResearchSourceControl from '@/app/components/ComposerResearchSourceControl';
import { useElementSelection } from '@/app/components/ElementSelectionContext';
import ModelPicker from '@/app/components/ModelPicker';
import SwarmModePicker, { getSwarmModeOption } from './SwarmModePicker';
import { API_BASE } from '@/shared/config';
import { useClaudeTokens } from '@/shared/styles/ThemeContext';
import type { SwarmMode } from '@/shared/state/dashboardLayoutSlice';
import type { ContextPath } from '@/app/components/DirectoryBrowser';
import {
  createDisabledVoiceState,
  createDefaultResearchSources,
  contextRefFromPath,
  contextRefFromCatalog,
  selectionRefFromElement,
  toolRefFromNames,
  type UnifiedComposerState,
  type UnifiedComposerSubmitPayload,
  type UnifiedComposerToolRef,
  type UnifiedComposerResearchSourceRef,
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
  const [explicitContextRefs, setExplicitContextRefs] = useState<ReturnType<typeof contextRefFromCatalog>[]>([]);
  const [showResearchSources, setShowResearchSources] = useState(false);
  const [researchOverrides, setResearchOverrides] = useState<Record<string, UnifiedComposerResearchSourceRef['state']>>({});
  const [forcedTools, setForcedTools] = useState<Array<{ label: string; tools: string[]; icon?: React.ReactNode; iconKey?: string }>>([]);
  const [picker, setPicker] = useState<{ open: boolean; trigger: '@' | '/' | '#'; filter: string }>({ open: false, trigger: '@', filter: '' });
  const [isUploading, setIsUploading] = useState(false);
  const modeOption = getSwarmModeOption(mode);
  const selectedModel = model || modelLabel || '';
  const selectedElements = elementSelection?.elementsByOwner?.[composerOwnerId] ?? [];
  const voiceState = useMemo(() => createDisabledVoiceState(), []);
  const submitDisabled = disabled || loading || (!value.trim() && !canContinue);
  const placeholder = placeholderOverride || (customIntakeMode ? 'Escribí tu respuesta personalizada…' : modeOption.placeholder);
  const contextRefs = useMemo(() => (
    [
      ...contextPaths.map((cp) => contextRefFromPath(cp.path, cp.type === 'directory' ? 'directory' : 'file', 'upload')),
      ...explicitContextRefs,
    ]
  ), [contextPaths, explicitContextRefs]);
  const selectedToolRefs = useMemo<UnifiedComposerToolRef[]>(() => (
    forcedTools.map((tool) => toolRefFromNames(tool.label, tool.tools, tool.iconKey))
  ), [forcedTools]);
  const selectionRefs = useMemo(() => (
    selectedElements.map((el) => selectionRefFromElement(el, composerOwnerId))
  ), [composerOwnerId, selectedElements]);
  const attachmentRefs = useMemo(() => contextRefs.map((ref) => ({ ...ref, source: ref.source === 'upload' ? 'upload' as const : 'existing' as const })), [contextRefs]);
  const researchSources = useMemo(() => createDefaultResearchSources({
    contextRefIds: contextRefs.map((ref) => ref.id),
    attachmentRefIds: attachmentRefs.map((ref) => ref.id),
    browserRefIds: contextRefs.filter((ref) => ref.kind === 'browser').map((ref) => ref.id),
    evidenceRefIds: contextRefs.filter((ref) => ref.kind === 'evidence').map((ref) => ref.id),
  }).map((source) => researchOverrides[source.id] ? { ...source, state: researchOverrides[source.id] } : source), [attachmentRefs, contextRefs, researchOverrides]);
  const editTarget = useMemo(() => {
    const ref = explicitContextRefs.find((item) => item.kind === 'output' || item.kind === 'candidate');
    if (!ref) return null;
    return {
      id: `edit:${ref.id}`,
      kind: ref.kind === 'candidate' ? 'candidate' as const : 'output' as const,
      label: ref.label,
      source: 'context_ref' as const,
      output_id: ref.metadata?.output_id as string | undefined,
      candidate_iteration_id: ref.metadata?.candidate_iteration_id as string | undefined,
      metadata: ref.metadata,
      disabled_reason: { code: 'unsupported' as const, message: 'Targeted edit is prepared; Swarm applies changes through candidate/refinement flow only.' },
    };
  }, [explicitContextRefs]);
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
    research_sources: showResearchSources ? researchSources : [],
    edit_target: editTarget,
  }), [attachmentRefs, cardId, composerOwnerId, contextRefs, disabled, editTarget, loading, mode, researchSources, selectedModel, selectedToolRefs, selectionRefs, showResearchSources, submitDisabled, value, voiceState]);

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
    if (item.enabled === false) return;
    if (item.type === 'slash' && item.actionKind === 'set_mode' && typeof item.payload?.mode === 'string') {
      onModeChange(item.payload.mode as SwarmMode);
      onChange(value.replace(/^\/\S*\s*/, ''));
    } else if (item.type === 'slash' && item.actionKind === 'open_context_picker') {
      onChange(value.replace(/^\/\S*\s*/, ''));
      setPicker({ open: true, trigger: '#', filter: '' });
      return;
    } else if (item.type === 'slash' && item.actionKind === 'open_tools_picker') {
      onChange(value.replace(/^\/\S*\s*/, ''));
      setPicker({ open: true, trigger: '@', filter: '' });
      return;
    } else if (item.type === 'slash' && item.actionKind === 'toggle_research_sources') {
      onChange(value.replace(/^\/\S*\s*/, ''));
      setShowResearchSources(true);
    } else if ((item.type === 'slash' || item.type === 'context') && item.actionKind === 'open_file_picker') {
      if (item.type === 'slash') onChange(value.replace(/^\/\S*\s*/, ''));
      fileInputRef.current?.click();
    } else if (item.type === 'context' && item.actionKind === 'add_context_ref' && item.contextRef) {
      setExplicitContextRefs((prev) => prev.some((ref) => ref.id === item.contextRef!.id) ? prev : [...prev, item.contextRef!]);
    } else if (item.type === 'context' && item.toolNames?.length) {
      setForcedTools((prev) => [...prev, { label: item.name, tools: item.toolNames!, icon: item.icon, iconKey: item.iconKey }]);
    }
    setPicker((p) => ({ ...p, open: false }));
  }, [onChange, onModeChange, value]);

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
    research_sources: showResearchSources ? researchSources : [],
    edit_target: editTarget,
  }), [attachmentRefs, cardId, composerOwnerId, contextRefs, editTarget, mode, researchSources, selectedModel, selectedToolRefs, selectionRefs, showResearchSources, value, voiceState]);

  const handleSubmit = useCallback(() => {
    if (submitDisabled) return;
    const slash = value.trim().match(/^\/(\S+)/);
    if (slash) {
      const command = slash[1].toLowerCase();
      const modeByCommand: Record<string, SwarmMode> = { ask: 'ask', plan: 'plan', app: 'app_builder', debug: 'debug', skill: 'skill_builder' };
      if (modeByCommand[command]) {
        onModeChange(modeByCommand[command]);
        onChange(value.replace(/^\/\S*\s*/, ''));
      } else if (command === 'file') {
        fileInputRef.current?.click();
        onChange(value.replace(/^\/\S*\s*/, ''));
      } else if (command === 'context') {
        setPicker({ open: true, trigger: '#', filter: '' });
      } else if (command === 'tool') {
        setPicker({ open: true, trigger: '@', filter: '' });
      } else if (command === 'research') {
        setShowResearchSources(true);
        onChange(value.replace(/^\/\S*\s*/, ''));
      }
      return;
    }
    onSend(buildSubmitPayload());
    setContextPaths([]);
    setExplicitContextRefs([]);
    setShowResearchSources(false);
    setForcedTools([]);
    elementSelection?.clearOwnerElements(composerOwnerId);
  }, [buildSubmitPayload, composerOwnerId, elementSelection, onChange, onModeChange, onSend, submitDisabled, value]);

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
      <CommandPicker trigger={picker.trigger} filter={picker.filter} visible={picker.open} surface="swarm" onSelect={handlePickerSelect} onClose={() => setPicker((p) => ({ ...p, open: false }))} />
      <Box onPointerDown={(e) => e.stopPropagation()} onClick={(e) => e.stopPropagation()} sx={{ px: 1.5, pt: 1.25, pb: 0.25 }}>
        <InputBase
          multiline
          fullWidth
          minRows={1}
          maxRows={5}
          inputRef={inputRef}
          autoFocus={autoFocus}
          value={value}
          onChange={(e) => {
            const next = e.target.value;
            onChange(next);
            const match = next.match(/(?:^|\s)([\/#])([^\s]*)$/);
            if (match) setPicker({ open: true, trigger: match[1] as '/' | '#', filter: match[2] || '' });
          }}
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
              <IconButton size="small" disabled={disabled || loading} onClick={() => setPicker((p) => ({ open: !(p.open && p.trigger === '@'), trigger: '@', filter: '' }))} sx={{ width: 26, height: 26, p: 0.5 }}>
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

      <ComposerContextPreview state={unifiedComposerState} compact />
      <ChatDebugContextView title="Swarm composer debug" state={unifiedComposerState} compact />
      <ProjectMemoryContextPanel state={unifiedComposerState} compact />
      <PromptSkillAuthoringPanel title="Swarm authoring" state={unifiedComposerState} compact />
      <ComposerResearchSourceControl
        sources={researchSources}
        visible={showResearchSources}
        onToggleSource={(id) => {
          setResearchOverrides((prev) => {
            const source = researchSources.find((item) => item.id === id);
            if (!source || source.state === 'disabled' || source.state === 'not_configured' || source.state === 'unsupported') return prev;
            return { ...prev, [id]: source.state === 'selected' ? 'available' : 'selected' };
          });
        }}
      />

      {(contextRefs.length > 0 || selectedToolRefs.length > 0 || selectionRefs.length > 0) && (
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, px: 1.5, pb: 0.75 }}>
          {contextRefs.map((ref, idx) => (
            <Chip key={`ctx-${ref.id}-${idx}`} size="small" icon={<AttachFileIcon sx={{ fontSize: 14 }} />} label={ref.kind === 'file' ? ref.label : `#${ref.kind}:${ref.label}`} onDelete={() => {
              if (ref.source === 'catalog') setExplicitContextRefs((prev) => prev.filter((ctx) => ctx.id !== ref.id));
              else setContextPaths((prev) => prev.filter((_, i) => i !== idx));
            }} sx={{ height: 24, fontSize: '0.7rem', color: c.accent.primary, bgcolor: `${c.accent.primary}12`, fontFamily: c.font.mono }} />
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
                setExplicitContextRefs([]);
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
