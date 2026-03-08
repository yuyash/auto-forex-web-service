import { useState, useEffect, useCallback } from 'react';
import type { Granularity } from '../types/chart';

interface ChartPreferences {
  instrument: string;
  granularity: Granularity;
  autoRefreshEnabled: boolean;
  refreshInterval: number; // in seconds
}

const STORAGE_KEY = 'dashboard_chart_preferences';
const DEFAULTS_SNAPSHOT_KEY = 'dashboard_chart_defaults_snapshot';

interface DefaultsSnapshot {
  instrument: string;
  granularity: string;
}

function readAppDefaults(): DefaultsSnapshot {
  try {
    const raw = localStorage.getItem('app_settings');
    if (raw) {
      const parsed = JSON.parse(raw);
      return {
        instrument: parsed.defaultInstrument || 'USD_JPY',
        granularity: parsed.defaultGranularity || 'H1',
      };
    }
  } catch {
    // ignore
  }
  return { instrument: 'USD_JPY', granularity: 'H1' };
}

function readPreviousSnapshot(): DefaultsSnapshot | null {
  try {
    const raw = localStorage.getItem(DEFAULTS_SNAPSHOT_KEY);
    if (raw) return JSON.parse(raw);
  } catch {
    // ignore
  }
  return null;
}

function saveSnapshot(snapshot: DefaultsSnapshot) {
  localStorage.setItem(DEFAULTS_SNAPSHOT_KEY, JSON.stringify(snapshot));
}

/**
 * Hook to manage chart preferences with localStorage persistence.
 *
 * When the user changes defaultInstrument / defaultGranularity in app
 * settings, those changes are detected on next mount and propagated into
 * the chart preferences automatically.
 */
export function useChartPreferences() {
  const [preferences, setPreferences] = useState<ChartPreferences>(() => {
    const currentDefaults = readAppDefaults();
    const previousSnapshot = readPreviousSnapshot();

    // Base preferences: stored or fallback
    let base: ChartPreferences = {
      instrument: currentDefaults.instrument,
      granularity: currentDefaults.granularity as Granularity,
      autoRefreshEnabled: true,
      refreshInterval: 60,
    };

    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        base = { ...base, ...JSON.parse(stored) };
      }
    } catch {
      // ignore
    }

    // Detect if app-settings defaults changed since last snapshot
    if (previousSnapshot) {
      if (previousSnapshot.instrument !== currentDefaults.instrument) {
        base.instrument = currentDefaults.instrument;
      }
      if (previousSnapshot.granularity !== currentDefaults.granularity) {
        base.granularity = currentDefaults.granularity as Granularity;
      }
    }

    // Persist the current snapshot for next comparison
    saveSnapshot(currentDefaults);

    return base;
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
    const defaults = readAppDefaults();
    setPreferences({
      instrument: defaults.instrument,
      granularity: defaults.granularity as Granularity,
      autoRefreshEnabled: true,
      refreshInterval: 60,
    });
    saveSnapshot(defaults);
  }, []);

  return {
    preferences,
    updatePreference,
    updatePreferences,
    resetPreferences,
  };
}
