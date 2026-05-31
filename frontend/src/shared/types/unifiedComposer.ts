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
  kind: 'file' | 'directory' | 'context_ref' | 'image' | 'symbol' | 'workspace' | 'output' | 'candidate' | 'skill' | 'memory' | 'terminal' | 'error' | 'browser' | 'evidence';
  path?: string;
  label: string;
  source: 'upload' | 'directory_browser' | 'selection' | 'existing' | 'catalog' | 'redux' | 'element_selection';
  metadata?: Record<string, unknown>;
  disabled_reason?: UnifiedComposerDisabledReason;
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

export type UnifiedComposerResearchSourceState =
  | 'available'
  | 'selected'
  | 'disabled'
  | 'requires_approval'
  | 'not_configured'
  | 'unsupported';

export interface UnifiedComposerResearchSourceRef {
  id: string;
  kind: 'current_project' | 'selected_context_refs' | 'uploaded_or_attached_files' | 'browser_refs' | 'evidence_refs' | 'public_web' | 'outputs' | 'candidates';
  label: string;
  state: UnifiedComposerResearchSourceState;
  source_ref_ids?: string[];
  allowed_domains?: string[];
  depth?: 'shallow' | 'standard' | 'deep';
  requires_approval?: boolean;
  disabled_reason?: UnifiedComposerDisabledReason;
  metadata?: Record<string, unknown>;
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
  warnings?: string[];
  research_sources?: UnifiedComposerResearchSourceRef[];
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
  warnings?: string[];
  research_sources?: UnifiedComposerResearchSourceRef[];
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

export function contextRefFromCatalog(
  id: string,
  label: string,
  kind: UnifiedComposerContextRef['kind'] = 'context_ref',
  metadata?: Record<string, unknown>,
): UnifiedComposerContextRef {
  return {
    id,
    kind,
    label,
    source: 'catalog',
    metadata,
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

export const RESEARCH_PUBLIC_WEB_REQUIRES_APPROVAL: UnifiedComposerDisabledReason = {
  code: 'permission_missing',
  message: 'Public web research requires explicit approval and a connected safe research runtime.',
};

export function createDefaultResearchSources(params: {
  contextRefIds?: string[];
  attachmentRefIds?: string[];
  browserRefIds?: string[];
  evidenceRefIds?: string[];
} = {}): UnifiedComposerResearchSourceRef[] {
  const contextRefIds = params.contextRefIds || [];
  const attachmentRefIds = params.attachmentRefIds || [];
  const browserRefIds = params.browserRefIds || [];
  const evidenceRefIds = params.evidenceRefIds || [];
  return [
    { id: 'research-current-project', kind: 'current_project', label: 'Current project', state: 'selected', depth: 'standard' },
    {
      id: 'research-selected-context',
      kind: 'selected_context_refs',
      label: 'Selected context refs',
      state: contextRefIds.length > 0 ? 'selected' : 'disabled',
      source_ref_ids: contextRefIds,
      disabled_reason: contextRefIds.length ? undefined : { code: 'not_configured', message: 'No context refs selected yet.' },
    },
    {
      id: 'research-attached-files',
      kind: 'uploaded_or_attached_files',
      label: 'Attached files',
      state: attachmentRefIds.length > 0 ? 'selected' : 'disabled',
      source_ref_ids: attachmentRefIds,
      disabled_reason: attachmentRefIds.length ? undefined : { code: 'not_configured', message: 'No attached files selected yet.' },
    },
    {
      id: 'research-browser-refs',
      kind: 'browser_refs',
      label: 'Browser refs',
      state: browserRefIds.length > 0 ? 'selected' : 'disabled',
      source_ref_ids: browserRefIds,
      disabled_reason: browserRefIds.length ? undefined : { code: 'not_configured', message: 'No browser refs selected yet.' },
    },
    {
      id: 'research-evidence-refs',
      kind: 'evidence_refs',
      label: 'Evidence refs',
      state: evidenceRefIds.length > 0 ? 'selected' : 'disabled',
      source_ref_ids: evidenceRefIds,
      disabled_reason: evidenceRefIds.length ? undefined : { code: 'not_configured', message: 'No evidence refs selected yet.' },
    },
    {
      id: 'research-public-web',
      kind: 'public_web',
      label: 'Public web',
      state: 'requires_approval',
      requires_approval: true,
      depth: 'shallow',
      disabled_reason: RESEARCH_PUBLIC_WEB_REQUIRES_APPROVAL,
    },
  ];
}
