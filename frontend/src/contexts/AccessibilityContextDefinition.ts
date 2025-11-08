import { createContext } from 'react';

export interface AccessibilityContextType {
  highContrastMode: boolean;
  toggleHighContrastMode: () => void;
  reducedMotion: boolean;
  fontSize: 'normal' | 'large' | 'extra-large';
  setFontSize: (size: 'normal' | 'large' | 'extra-large') => void;
}

export const AccessibilityContext = createContext<
  AccessibilityContextType | undefined
>(undefined);
