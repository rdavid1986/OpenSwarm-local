export type UnifiedComposerSurface = 'agent' | 'swarm';
export type UnifiedComposerDisabledReasonCode =
  | 'backend_missing'
  | 'permission_missing'
  | 'not_configured'
  | 'running'
  | 'empty_prompt'
  | 'unsupported';

export interface UnifiedComposerDisabledReason {
  code: UnifiedComposerDisabledReasonCode;
  message: string;
}

export interface UnifiedComposerContextRef {
  id: string;
  kind: 'file' | 'directory' | 'context_ref' | 'image';
  path?: string;
  label: string;
  source: 'upload' | 'directory_browser' | 'selection' | 'existing';
  metadata?: Record<string, unknown>;
}

export interface UnifiedComposerToolRef {
  id: string;
  label: string;
  tool_names: string[];
  state: 'available' | 'selected' | 'disabled' | 'blocked' | 'not_configured';
  icon_key?: string;
  disabled_reason?: UnifiedComposerDisabledReason;
}

export interface UnifiedComposerSelectionRef {
  id: string;
  label: string;
  type: string;
  owner_id: string;
  source: 'element_selection';
  metadata?: Record<string, unknown>;
}

export interface UnifiedComposerAttachmentRef {
  id: string;
  kind: 'file' | 'directory' | 'image' | 'context_ref';
  label: string;
  source: 'upload' | 'existing' | 'selection';
  path?: string;
  disabled_reason?: UnifiedComposerDisabledReason;
  metadata?: Record<string, unknown>;
}

export interface UnifiedComposerVoiceState {
  recording: boolean;
  processing: boolean;
  transcript: string;
  permission_state: 'unknown' | 'granted' | 'denied' | 'prompt' | 'unsupported';
  insert_into_composer: boolean;
  disabled_reason?: UnifiedComposerDisabledReason;
  error?: string;
}

export interface UnifiedComposerCapability {
  id: string;
  label: string;
  available: boolean;
  disabled_reason?: UnifiedComposerDisabledReason;
}

export interface UnifiedComposerState {
  source_surface: UnifiedComposerSurface;
  owner_id: string;
  card_id?: string;
  mode?: string;
  model?: string | null;
  prompt: string;
  loading: boolean;
  disabled: boolean;
  disabled_reasons: UnifiedComposerDisabledReason[];
  tools_available: UnifiedComposerToolRef[];
  tools_selected: UnifiedComposerToolRef[];
  context_refs: UnifiedComposerContextRef[];
  attachment_refs: UnifiedComposerAttachmentRef[];
  selected_ui_elements: UnifiedComposerSelectionRef[];
  voice: UnifiedComposerVoiceState;
  can_submit: boolean;
  can_stop: boolean;
  pending_action_capability: 'available' | 'disabled' | 'not_supported';
  evidence_refs: string[];
  trace_refs: string[];
}

export interface UnifiedComposerSubmitPayload {
  source_surface: UnifiedComposerSurface;
  owner_id: string;
  card_id?: string;
  mode?: string;
  model?: string | null;
  prompt: string;
  context_refs: UnifiedComposerContextRef[];
  attachment_refs: UnifiedComposerAttachmentRef[];
  selected_ui_elements: UnifiedComposerSelectionRef[];
  selected_tools: UnifiedComposerToolRef[];
  selected_tool_names: string[];
  voice: UnifiedComposerVoiceState;
  evidence_refs: string[];
  trace_refs: string[];
}

export const DISABLED_VOICE_NO_BACKEND: UnifiedComposerDisabledReason = {
  code: 'backend_missing',
  message: 'Voice input is disabled: no safe recording/transcription backend is connected yet.',
};

export function createDisabledVoiceState(reason: UnifiedComposerDisabledReason = DISABLED_VOICE_NO_BACKEND): UnifiedComposerVoiceState {
  return {
    recording: false,
    processing: false,
    transcript: '',
    permission_state: 'unsupported',
    insert_into_composer: false,
    disabled_reason: reason,
  };
}

export function selectionRefFromElement(el: any, ownerId: string): UnifiedComposerSelectionRef {
  const semanticData = el?.semanticData && typeof el.semanticData === 'object' ? el.semanticData : {};
  const label = String(
    el?.semanticLabel ||
      semanticData.label ||
      semanticData.title ||
      (el?.className ? `${String(el.tagName || 'element').toLowerCase()}.${String(el.className).split(' ')[0]}` : String(el?.tagName || 'element').toLowerCase()),
  );
  const { outerHTML, html, text, content, ...safeSemanticData } = semanticData;
  return {
    id: String(semanticData.selectId || el?.id || label),
    label: label.slice(0, 120),
    type: String(el?.semanticType || el?.tagName || 'element').toLowerCase(),
    owner_id: ownerId,
    source: 'element_selection',
    metadata: Object.keys(safeSemanticData).length ? safeSemanticData : undefined,
  };
}

export function contextRefFromPath(path: string, kind: 'file' | 'directory' = 'file', source: UnifiedComposerContextRef['source'] = 'upload'): UnifiedComposerContextRef {
  const cleanPath = String(path || '').trim();
  const parts = cleanPath.split(/[\\/]/).filter(Boolean);
  return {
    id: cleanPath,
    kind,
    path: cleanPath,
    label: parts.slice(-2).join('/') || cleanPath || 'context',
    source,
  };
}

export function toolRefFromNames(label: string, toolNames: string[], iconKey?: string): UnifiedComposerToolRef {
  return {
    id: `${label}:${toolNames.join(',')}`,
    label,
    tool_names: toolNames,
    state: 'selected',
    icon_key: iconKey,
  };
}
