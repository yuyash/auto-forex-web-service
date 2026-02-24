import { createContext } from 'react';

export type ThemeMode = 'light' | 'dark' | 'system';

export interface AccessibilityContextType {
  highContrastMode: boolean;
  toggleHighContrastMode: () => void;
  /** Resolved dark mode state (true = dark is active) */
  darkMode: boolean;
  /** Current theme mode preference */
  themeMode: ThemeMode;
  setThemeMode: (mode: ThemeMode) => void;
  reducedMotion: boolean;
  fontSize: 'normal' | 'large' | 'extra-large';
  setFontSize: (size: 'normal' | 'large' | 'extra-large') => void;
}

export const AccessibilityContext = createContext<
  AccessibilityContextType | undefined
>(undefined);
