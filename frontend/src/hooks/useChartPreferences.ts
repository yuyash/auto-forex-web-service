import { useState, useEffect, useCallback } from 'react';
import type { Granularity } from '../types/chart';

interface ChartPreferences {
  instrument: string;
  granularity: Granularity;
  autoRefreshEnabled: boolean;
  refreshInterval: number; // in seconds
}

const DEFAULT_PREFERENCES: ChartPreferences = {
  instrument: 'USD_JPY',
  granularity: 'H1',
  autoRefreshEnabled: false,
  refreshInterval: 60,
};

const STORAGE_KEY = 'dashboard_chart_preferences';

/**
 * Hook to manage chart preferences with localStorage persistence
 * Automatically saves preferences when they change
 */
export function useChartPreferences() {
  const [preferences, setPreferences] = useState<ChartPreferences>(() => {
    // Load preferences from localStorage on mount
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        console.log(
          '[useChartPreferences] Loaded preferences from localStorage',
          parsed
        );
        return { ...DEFAULT_PREFERENCES, ...parsed };
      }
    } catch (err) {
      console.error('[useChartPreferences] Failed to load preferences', err);
    }
    console.log(
      '[useChartPreferences] Using default preferences',
      DEFAULT_PREFERENCES
    );
    return DEFAULT_PREFERENCES;
  });

  // Save preferences to localStorage whenever they change
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences));
      console.log(
        '[useChartPreferences] Saved preferences to localStorage',
        preferences
      );
    } catch (err) {
      console.error('[useChartPreferences] Failed to save preferences', err);
    }
  }, [preferences]);

  // Update individual preference values
  const updatePreference = useCallback(
    <K extends keyof ChartPreferences>(key: K, value: ChartPreferences[K]) => {
      setPreferences((prev) => ({
        ...prev,
        [key]: value,
      }));
    },
    []
  );

  // Update multiple preferences at once
  const updatePreferences = useCallback(
    (updates: Partial<ChartPreferences>) => {
      setPreferences((prev) => ({
        ...prev,
        ...updates,
      }));
    },
    []
  );

  // Reset to default preferences
  const resetPreferences = useCallback(() => {
    console.log('[useChartPreferences] Resetting to default preferences');
    setPreferences(DEFAULT_PREFERENCES);
  }, []);

  return {
    preferences,
    updatePreference,
    updatePreferences,
    resetPreferences,
  };
}
