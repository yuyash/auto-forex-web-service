import React, { useState, useEffect, type ReactNode } from 'react';
import { isHighContrastMode } from '../utils/contrastUtils';
import { AccessibilityContext } from './AccessibilityContextDefinition';

interface AccessibilityProviderProps {
  children: ReactNode;
}

export const AccessibilityProvider: React.FC<AccessibilityProviderProps> = ({
  children,
}) => {
  const [highContrastMode, setHighContrastMode] = useState(() => {
    // Check localStorage first, then system preference
    const stored = localStorage.getItem('highContrastMode');
    if (stored !== null) {
      return stored === 'true';
    }
    return isHighContrastMode();
  });

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
        reducedMotion,
        fontSize,
        setFontSize: handleSetFontSize,
      }}
    >
      {children}
    </AccessibilityContext.Provider>
  );
};
