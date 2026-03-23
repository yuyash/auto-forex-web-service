import { useState, useEffect, useCallback } from 'react';
import { z } from 'zod';
import type { Granularity } from '../types/chart';
import { logger } from '../utils/logger';
import { readStoredValue, writeStoredValue } from '../utils/persistentState';

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

const defaultsSnapshotSchema = z.object({
  instrument: z.string().min(1),
  granularity: z.string().min(1),
});

const storedAppSettingsSchema = z.object({
  defaultInstrument: z.string().min(1).optional(),
  defaultGranularity: z.string().min(1).optional(),
});

const chartPreferencesSchema = z.object({
  instrument: z.string().min(1),
  granularity: z.custom<Granularity>((value) => typeof value === 'string'),
  autoRefreshEnabled: z.boolean(),
  refreshInterval: z.number(),
});

function readAppDefaults(): DefaultsSnapshot {
  const parsed = readStoredValue('app_settings', storedAppSettingsSchema, {});
  if (parsed.defaultInstrument || parsed.defaultGranularity) {
    return {
      instrument: parsed.defaultInstrument || 'USD_JPY',
      granularity: parsed.defaultGranularity || 'H1',
    };
  }
  return { instrument: 'USD_JPY', granularity: 'H1' };
}

function readPreviousSnapshot(): DefaultsSnapshot | null {
  return readStoredValue(DEFAULTS_SNAPSHOT_KEY, defaultsSnapshotSchema, null);
}

function saveSnapshot(snapshot: DefaultsSnapshot) {
  writeStoredValue(DEFAULTS_SNAPSHOT_KEY, snapshot);
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

    const stored = readStoredValue(STORAGE_KEY, chartPreferencesSchema, null);
    if (stored) {
      base = { ...base, ...stored };
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
      writeStoredValue(STORAGE_KEY, preferences);
      logger.debug('Saved chart preferences to localStorage', { preferences });
    } catch (err) {
      logger.error('Failed to save chart preferences', {
        error: err instanceof Error ? err.message : String(err),
      });
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
