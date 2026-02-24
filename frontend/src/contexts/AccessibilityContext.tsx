import React, { useState, useEffect, type ReactNode } from 'react';
import { isHighContrastMode } from '../utils/contrastUtils';
import { AccessibilityContext } from './AccessibilityContextDefinition';
import type { ThemeMode } from './AccessibilityContextDefinition';

interface AccessibilityProviderProps {
  children: ReactNode;
}

export const AccessibilityProvider: React.FC<AccessibilityProviderProps> = ({
  children,
}) => {
  const [highContrastMode, setHighContrastMode] = useState(() => {
    const stored = localStorage.getItem('highContrastMode');
    if (stored !== null) {
      return stored === 'true';
    }
    return isHighContrastMode();
  });

  // Theme mode: 'light' | 'dark' | 'system'
  const [themeMode, setThemeModeState] = useState<ThemeMode>(() => {
    const stored = localStorage.getItem('themeMode');
    if (stored === 'light' || stored === 'dark' || stored === 'system') {
      return stored;
    }
    // Migrate from old boolean darkMode key
    const oldDark = localStorage.getItem('darkMode');
    if (oldDark !== null) {
      localStorage.removeItem('darkMode');
      const mode = oldDark === 'true' ? 'dark' : 'light';
      localStorage.setItem('themeMode', mode);
      return mode;
    }
    return 'system';
  });

  // Resolved system preference
  const [systemPrefersDark, setSystemPrefersDark] = useState(() => {
    if (typeof window === 'undefined') return false;
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
  });

  // Listen for system dark mode changes
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const handler = (e: MediaQueryListEvent) => setSystemPrefersDark(e.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

  // Resolved darkMode boolean
  const darkMode =
    themeMode === 'dark'
      ? true
      : themeMode === 'light'
        ? false
        : systemPrefersDark;

  const setThemeMode = (mode: ThemeMode) => {
    setThemeModeState(mode);
    localStorage.setItem('themeMode', mode);
  };

  const [reducedMotion, setReducedMotion] = useState(() => {
    if (typeof window === 'undefined') return false;
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  });

  const [fontSize, setFontSize] = useState<'normal' | 'large' | 'extra-large'>(
    () => {
      const stored = localStorage.getItem('fontSize');
      return (stored as 'normal' | 'large' | 'extra-large') || 'normal';
    }
  );

  // Listen for system high contrast mode changes
  useEffect(() => {
    if (typeof window === 'undefined') return;

    const mediaQuery = window.matchMedia('(prefers-contrast: high)');
    const handleChange = (e: MediaQueryListEvent) => {
      // Only update if user hasn't manually set a preference
      const stored = localStorage.getItem('highContrastMode');
      if (stored === null) {
        setHighContrastMode(e.matches);
      }
    };

    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, []);

  // Listen for reduced motion preference changes
  useEffect(() => {
    if (typeof window === 'undefined') return;

    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    const handleChange = (e: MediaQueryListEvent) => {
      setReducedMotion(e.matches);
    };

    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, []);

  // Apply high contrast mode to document
  useEffect(() => {
    if (highContrastMode) {
      document.documentElement.classList.add('high-contrast');
    } else {
      document.documentElement.classList.remove('high-contrast');
    }
  }, [highContrastMode]);

  // Apply font size to document
  useEffect(() => {
    document.documentElement.setAttribute('data-font-size', fontSize);
  }, [fontSize]);

  const toggleHighContrastMode = () => {
    setHighContrastMode((prev) => {
      const newValue = !prev;
      localStorage.setItem('highContrastMode', String(newValue));
      return newValue;
    });
  };

  const handleSetFontSize = (size: 'normal' | 'large' | 'extra-large') => {
    setFontSize(size);
    localStorage.setItem('fontSize', size);
  };

  return (
    <AccessibilityContext.Provider
      value={{
        highContrastMode,
        toggleHighContrastMode,
        darkMode,
        themeMode,
        setThemeMode,
        reducedMotion,
        fontSize,
        setFontSize: handleSetFontSize,
      }}
    >
      {children}
    </AccessibilityContext.Provider>
  );
};
