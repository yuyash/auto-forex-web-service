import { useState, useEffect, useCallback } from 'react';
import { z } from 'zod';
import type { Granularity } from '../types/chart';
import {
  readStoredValue,
  STORAGE_CHANGE_EVENT,
  writeStoredValue,
} from '../utils/persistentState';

export interface AppSettings {
  // Display: date & number format
  dateFormat: 'MM/DD/YYYY' | 'DD/MM/YYYY' | 'YYYY-MM-DD';
  decimalSeparator: '.' | ',';
  thousandsSeparator: ',' | '.' | ' ' | '';

  // Chart defaults
  defaultInstrument: string;
  defaultGranularity: Granularity;
  candleUpColor: string;
  candleDownColor: string;

  // Session
  sessionTimeoutMinutes: number;

  // Data refresh
  healthCheckIntervalSeconds: number;
}

export const DEFAULT_APP_SETTINGS: AppSettings = {
  dateFormat: 'YYYY-MM-DD',
  decimalSeparator: '.',
  thousandsSeparator: ',',
  defaultInstrument: 'USD_JPY',
  defaultGranularity: 'H1',
  candleUpColor: '#26a69a',
  candleDownColor: '#ef5350',
  sessionTimeoutMinutes: 30,
  healthCheckIntervalSeconds: 30,
};

export const APP_SETTINGS_STORAGE_KEY = 'app_settings';
export const appSettingsSchema = z.object({
  dateFormat: z.enum(['MM/DD/YYYY', 'DD/MM/YYYY', 'YYYY-MM-DD']),
  decimalSeparator: z.enum(['.', ',']),
  thousandsSeparator: z.enum([',', '.', ' ', '']),
  defaultInstrument: z.string().min(1),
  defaultGranularity: z.custom<Granularity>(
    (value) => typeof value === 'string'
  ),
  candleUpColor: z.string().min(1),
  candleDownColor: z.string().min(1),
  sessionTimeoutMinutes: z.number(),
  healthCheckIntervalSeconds: z.number(),
});

export function readAppSettings(): AppSettings {
  return readStoredValue(
    APP_SETTINGS_STORAGE_KEY,
    appSettingsSchema.transform((value) => ({
      ...DEFAULT_APP_SETTINGS,
      ...value,
    })),
    DEFAULT_APP_SETTINGS
  );
}

export function useAppSettings() {
  const [settings, setSettings] = useState<AppSettings>(() =>
    readAppSettings()
  );

  useEffect(() => {
    writeStoredValue(APP_SETTINGS_STORAGE_KEY, settings);
  }, [settings]);

  useEffect(() => {
    if (typeof window === 'undefined') return;

    const syncSettings = (event?: Event) => {
      if (
        event instanceof StorageEvent &&
        event.key &&
        event.key !== APP_SETTINGS_STORAGE_KEY
      ) {
        return;
      }
      if (event instanceof CustomEvent) {
        const key = (event.detail as { key?: string } | undefined)?.key;
        if (key && key !== APP_SETTINGS_STORAGE_KEY) {
          return;
        }
      }
      setSettings(readAppSettings());
    };

    window.addEventListener('storage', syncSettings);
    window.addEventListener(
      STORAGE_CHANGE_EVENT,
      syncSettings as EventListener
    );

    return () => {
      window.removeEventListener('storage', syncSettings);
      window.removeEventListener(
        STORAGE_CHANGE_EVENT,
        syncSettings as EventListener
      );
    };
  }, []);

  const updateSetting = useCallback(
    <K extends keyof AppSettings>(key: K, value: AppSettings[K]) => {
      setSettings((prev) => ({ ...prev, [key]: value }));
    },
    []
  );

  const updateSettings = useCallback((updates: Partial<AppSettings>) => {
    setSettings((prev) => ({ ...prev, ...updates }));
  }, []);

  const resetSettings = useCallback(() => {
    setSettings(DEFAULT_APP_SETTINGS);
  }, []);

  return {
    settings,
    updateSetting,
    updateSettings,
    resetSettings,
    DEFAULT_APP_SETTINGS,
  };
}
