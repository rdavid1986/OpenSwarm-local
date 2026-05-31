import type { UnifiedComposerDisabledReason, UnifiedComposerSurface } from './unifiedComposer';

export type ComposerCommandSurface = UnifiedComposerSurface | 'both';
export type ComposerActionKind =
  | 'set_mode'
  | 'open_context_drawer'
  | 'open_file_picker'
  | 'open_context_picker'
  | 'open_tools_picker'
  | 'toggle_research_sources'
  | 'add_context_ref'
  | 'prepared';

export interface ComposerCatalogCommand {
  id: string;
  command: string;
  label: string;
  description: string;
  category: string;
  surface: ComposerCommandSurface;
  enabled: boolean;
  disabled_reason?: UnifiedComposerDisabledReason;
  action_kind: ComposerActionKind;
  payload?: Record<string, unknown>;
}

const PREPARED_ONLY: UnifiedComposerDisabledReason = {
  code: 'unsupported',
  message: 'Prepared contract only: no safe handler is connected for this command yet.',
};

export const SHARED_SLASH_COMMANDS: ComposerCatalogCommand[] = [
  { id: 'slash-ask', command: 'ask', label: 'Ask', description: 'Switch composer to Ask mode.', category: 'Modes', surface: 'both', enabled: true, action_kind: 'set_mode', payload: { mode: 'ask' } },
  { id: 'slash-plan', command: 'plan', label: 'Plan', description: 'Switch composer to Plan mode.', category: 'Modes', surface: 'both', enabled: true, action_kind: 'set_mode', payload: { mode: 'plan' } },
  { id: 'slash-app', command: 'app', label: 'App Builder', description: 'Switch composer to App Builder mode.', category: 'Modes', surface: 'both', enabled: true, action_kind: 'set_mode', payload: { mode: 'app_builder' } },
  { id: 'slash-debug', command: 'debug', label: 'Debug', description: 'Switch composer to Debug mode.', category: 'Modes', surface: 'both', enabled: true, action_kind: 'set_mode', payload: { mode: 'debug' } },
  { id: 'slash-skill', command: 'skill', label: 'Skill Builder', description: 'Switch composer to Skill Builder mode.', category: 'Modes', surface: 'both', enabled: true, action_kind: 'set_mode', payload: { mode: 'skill_builder' } },
  { id: 'slash-context', command: 'context', label: 'Context', description: 'Open the context picker/drawer.', category: 'Context', surface: 'both', enabled: true, action_kind: 'open_context_picker' },
  { id: 'slash-file', command: 'file', label: 'File', description: 'Attach a file as context.', category: 'Context', surface: 'both', enabled: true, action_kind: 'open_file_picker' },
  { id: 'slash-folder', command: 'folder', label: 'Folder', description: 'Folder context picker is not connected yet.', category: 'Context', surface: 'both', enabled: false, action_kind: 'prepared', disabled_reason: PREPARED_ONLY },
  { id: 'slash-symbol', command: 'symbol', label: 'Symbol', description: 'Symbol index context is not connected yet.', category: 'Context', surface: 'both', enabled: false, action_kind: 'prepared', disabled_reason: PREPARED_ONLY },
  { id: 'slash-tool', command: 'tool', label: 'Tool', description: 'Open tools/actions selector without executing tools.', category: 'Tools', surface: 'both', enabled: true, action_kind: 'open_tools_picker' },
  { id: 'slash-research', command: 'research', label: 'Research', description: 'Open research source control without running research.', category: 'Research', surface: 'both', enabled: true, action_kind: 'toggle_research_sources', payload: { requires_approval: true } },
  { id: 'slash-skill-candidate', command: 'skill-candidate', label: 'Skill Candidate', description: 'Prepared for skill candidate context/actions.', category: 'Future', surface: 'both', enabled: false, action_kind: 'prepared', disabled_reason: PREPARED_ONLY },
  { id: 'slash-refine', command: 'refine', label: 'Refine', description: 'Prepared for targeted refine flow; no output is created here.', category: 'Future', surface: 'both', enabled: false, action_kind: 'prepared', disabled_reason: PREPARED_ONLY },
  { id: 'slash-preview', command: 'preview', label: 'Preview', description: 'Prepared for preview/canvas flow; no output is created here.', category: 'Future', surface: 'both', enabled: false, action_kind: 'prepared', disabled_reason: PREPARED_ONLY },
  { id: 'slash-compare', command: 'compare', label: 'Compare', description: 'Prepared for review/diff flow.', category: 'Future', surface: 'both', enabled: false, action_kind: 'prepared', disabled_reason: PREPARED_ONLY },
  { id: 'slash-trace', command: 'trace', label: 'Trace', description: 'Prepared for trace inspector; no evidence is invented.', category: 'Inspector', surface: 'both', enabled: false, action_kind: 'prepared', disabled_reason: PREPARED_ONLY },
  { id: 'slash-metrics', command: 'metrics', label: 'Metrics', description: 'Prepared for runtime metrics inspector.', category: 'Inspector', surface: 'both', enabled: false, action_kind: 'prepared', disabled_reason: PREPARED_ONLY },
];

export const SHARED_CONTEXT_COMMANDS: ComposerCatalogCommand[] = [
  { id: 'ctx-file', command: 'file', label: 'File', description: 'Attach a file ref.', category: 'Files', surface: 'both', enabled: true, action_kind: 'open_file_picker', payload: { context_kind: 'file' } },
  { id: 'ctx-folder', command: 'folder', label: 'Folder', description: 'Folder refs need a safe picker backend.', category: 'Files', surface: 'both', enabled: false, action_kind: 'prepared', disabled_reason: PREPARED_ONLY },
  { id: 'ctx-symbol', command: 'symbol', label: 'Symbol', description: 'Symbol refs need an index/resolver.', category: 'Code', surface: 'both', enabled: false, action_kind: 'prepared', disabled_reason: PREPARED_ONLY },
  { id: 'ctx-workspace', command: 'workspace', label: 'Workspace', description: 'Workspace-wide refs are too broad without resolver limits.', category: 'Code', surface: 'both', enabled: false, action_kind: 'prepared', disabled_reason: PREPARED_ONLY },
  { id: 'ctx-candidate', command: 'candidate', label: 'Candidate', description: 'Candidate refs are prepared for a future resolver.', category: 'Project', surface: 'both', enabled: false, action_kind: 'prepared', disabled_reason: PREPARED_ONLY },
  { id: 'ctx-memory', command: 'memory', label: 'Memory', description: 'Memory UX belongs to a later CHAT-UX phase.', category: 'Project', surface: 'both', enabled: false, action_kind: 'prepared', disabled_reason: PREPARED_ONLY },
  { id: 'ctx-terminal', command: 'terminal', label: 'Terminal', description: 'Terminal refs need explicit captured evidence.', category: 'Evidence', surface: 'both', enabled: false, action_kind: 'prepared', disabled_reason: PREPARED_ONLY },
  { id: 'ctx-error', command: 'error', label: 'Error', description: 'Error refs need a concrete captured error source.', category: 'Evidence', surface: 'both', enabled: false, action_kind: 'prepared', disabled_reason: PREPARED_ONLY },
  { id: 'ctx-browser', command: 'browser', label: 'Browser', description: 'Use Select UI element for browser-card refs.', category: 'Evidence', surface: 'both', enabled: false, action_kind: 'prepared', disabled_reason: PREPARED_ONLY },
  { id: 'ctx-evidence', command: 'evidence', label: 'Evidence', description: 'Evidence refs must come from real trace/evidence records.', category: 'Evidence', surface: 'both', enabled: false, action_kind: 'prepared', disabled_reason: PREPARED_ONLY },
];

export function commandForSurface(command: ComposerCatalogCommand, surface?: UnifiedComposerSurface): boolean {
  return !surface || command.surface === 'both' || command.surface === surface;
}
