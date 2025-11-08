import { useEffect } from 'react';

export interface KeyboardShortcut {
  key: string;
  ctrlKey?: boolean;
  shiftKey?: boolean;
  altKey?: boolean;
  metaKey?: boolean;
  action: () => void;
  description: string;
  disabled?: boolean;
}

interface UseKeyboardShortcutsOptions {
  shortcuts: KeyboardShortcut[];
  enabled?: boolean;
}

/**
 * Hook to register keyboard shortcuts for task actions
 *
 * Common shortcuts:
 * - Ctrl/Cmd + S: Start task
 * - Ctrl/Cmd + P: Pause task
 * - Ctrl/Cmd + X: Stop task
 * - Ctrl/Cmd + R: Rerun task
 * - Ctrl/Cmd + C: Copy task
 * - Ctrl/Cmd + E: Edit task
 * - Delete: Delete task
 */
export const useKeyboardShortcuts = ({
  shortcuts,
  enabled = true,
}: UseKeyboardShortcutsOptions) => {
  useEffect(() => {
    if (!enabled) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      // Don't trigger shortcuts when typing in input fields
      const target = event.target as HTMLElement;
      if (
        target.tagName === 'INPUT' ||
        target.tagName === 'TEXTAREA' ||
        target.isContentEditable
      ) {
        return;
      }

      for (const shortcut of shortcuts) {
        if (shortcut.disabled) continue;

        const keyMatches =
          event.key.toLowerCase() === shortcut.key.toLowerCase();
        const ctrlMatches = shortcut.ctrlKey ? event.ctrlKey : !event.ctrlKey;
        const shiftMatches = shortcut.shiftKey
          ? event.shiftKey
          : !event.shiftKey;
        const altMatches = shortcut.altKey ? event.altKey : !event.altKey;
        const metaMatches = shortcut.metaKey ? event.metaKey : !event.metaKey;

        if (
          keyMatches &&
          ctrlMatches &&
          shiftMatches &&
          altMatches &&
          metaMatches
        ) {
          event.preventDefault();
          shortcut.action();
          break;
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [shortcuts, enabled]);
};

/**
 * Get platform-specific modifier key label
 */
export const getModifierKeyLabel = (): string => {
  const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
  return isMac ? '⌘' : 'Ctrl';
};

/**
 * Format keyboard shortcut for display
 */
export const formatShortcut = (shortcut: KeyboardShortcut): string => {
  const parts: string[] = [];

  if (shortcut.ctrlKey || shortcut.metaKey) {
    parts.push(getModifierKeyLabel());
  }
  if (shortcut.shiftKey) {
    parts.push('Shift');
  }
  if (shortcut.altKey) {
    parts.push('Alt');
  }

  parts.push(shortcut.key.toUpperCase());

  return parts.join(' + ');
};

/**
 * Common task shortcuts
 */
export const createTaskShortcuts = (actions: {
  onStart?: () => void;
  onStop?: () => void;
  onPause?: () => void;
  onResume?: () => void;
  onRerun?: () => void;
  onCopy?: () => void;
  onEdit?: () => void;
  onDelete?: () => void;
}): KeyboardShortcut[] => {
  const shortcuts: KeyboardShortcut[] = [];

  if (actions.onStart) {
    shortcuts.push({
      key: 's',
      ctrlKey: true,
      action: actions.onStart,
      description: 'Start task',
    });
  }

  if (actions.onStop) {
    shortcuts.push({
      key: 'x',
      ctrlKey: true,
      action: actions.onStop,
      description: 'Stop task',
    });
  }

  if (actions.onPause) {
    shortcuts.push({
      key: 'p',
      ctrlKey: true,
      action: actions.onPause,
      description: 'Pause task',
    });
  }

  if (actions.onResume) {
    shortcuts.push({
      key: 'r',
      ctrlKey: true,
      shiftKey: true,
      action: actions.onResume,
      description: 'Resume task',
    });
  }

  if (actions.onRerun) {
    shortcuts.push({
      key: 'r',
      ctrlKey: true,
      action: actions.onRerun,
      description: 'Rerun task',
    });
  }

  if (actions.onCopy) {
    shortcuts.push({
      key: 'd',
      ctrlKey: true,
      action: actions.onCopy,
      description: 'Copy task',
    });
  }

  if (actions.onEdit) {
    shortcuts.push({
      key: 'e',
      ctrlKey: true,
      action: actions.onEdit,
      description: 'Edit task',
    });
  }

  if (actions.onDelete) {
    shortcuts.push({
      key: 'Delete',
      action: actions.onDelete,
      description: 'Delete task',
    });
  }

  return shortcuts;
};
