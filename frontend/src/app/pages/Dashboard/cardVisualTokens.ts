import type { ClaudeTokens } from '@/shared/styles/claudeTokens';

export function buildCardVisualTokens(c: ClaudeTokens) {
  return {
    surface: {
      background: c.bg.surface,
      headerBackground: c.bg.surface,
      bodyBackground: c.bg.page,
      border: c.border.subtle,
      selectedBorder: c.accent.primary,
      radius: 1.25,
      radiusPx: `${c.radius.lg}px`,
      shadow: c.shadow.md,
      subtleShadow: c.shadow.sm,
      highlightedShadow: c.shadow.lg,
      padding: 2,
      headerPaddingX: 2,
      headerPaddingY: 1.15,
      transition: c.transition,
      highlightedGlowShadow: `0 0 0 3px ${c.accent.primary}50, 0 0 20px ${c.accent.primary}35, 0 0 40px ${c.accent.primary}15`,
      selectedGlowShadow: `0 0 0 1px ${c.accent.primary}22, 0 0 10px ${c.accent.primary}12`,
    },
    trace: {
      background: c.bg.elevated,
      turnBackground: c.bg.surface,
      expandedBackground: c.bg.surface,
      nestedBackground: c.bg.page,
      headerHoverBackground: c.bg.secondary,
      border: c.border.subtle,
      runningBorder: `${c.accent.primary}80`,
      radius: `${c.radius.md}px`,
      turnRadius: `${c.radius.lg}px`,
      nestedRadius: `${c.radius.sm}px`,
      shadow: 'none',
      turnShadow: c.shadow.sm,
      runningShadow: `0 0 0 1px ${c.accent.primary}25, 0 0 18px ${c.accent.primary}18`,
      runningTurnShadow: `0 0 0 1px ${c.accent.primary}20, 0 0 18px ${c.accent.primary}12`,
      px: 1.25,
      compactPx: 1,
      py: 0.85,
      compactPy: 0.65,
      turnCompactPy: 0.7,
      panelPadding: 1,
      compactPanelPadding: 0.75,
      itemGap: 0.65,
    },
    density: {
      sidebarPadding: 1.5,
      inputPadding: 1.5,
      headerPaddingX: 2,
      headerPaddingY: 1.15,
    },
  };
}

export type CardVisualTokens = ReturnType<typeof buildCardVisualTokens>;
