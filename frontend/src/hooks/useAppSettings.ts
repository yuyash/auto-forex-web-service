import { useState, useEffect, useCallback } from 'react';
import { z } from 'zod';
import type { Granularity } from '../types/chart';
import { readStoredValue, writeStoredValue } from '../utils/persistentState';

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

const DEFAULT_APP_SETTINGS: AppSettings = {
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

const STORAGE_KEY = 'app_settings';
const appSettingsSchema = z.object({
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

export function useAppSettings() {
  const [settings, setSettings] = useState<AppSettings>(() =>
    readStoredValue(
      STORAGE_KEY,
      appSettingsSchema.transform((value) => ({
        ...DEFAULT_APP_SETTINGS,
        ...value,
      })),
      DEFAULT_APP_SETTINGS
    )
  );

  useEffect(() => {
    writeStoredValue(STORAGE_KEY, settings);
  }, [settings]);

  const updateSetting = useCallback(
    <K extends keyof AppSettings>(key: K, value: AppSettings[K]) => {
      setSettings((prev) => ({ ...prev, [key]: value }));
    },
    []
  );

  const resetSettings = useCallback(() => {
    setSettings(DEFAULT_APP_SETTINGS);
  }, []);

  return { settings, updateSetting, resetSettings, DEFAULT_APP_SETTINGS };
}
