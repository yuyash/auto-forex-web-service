import { useState, useEffect, useCallback } from 'react';
import type { Granularity } from '../types/chart';

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

export function useAppSettings() {
  const [settings, setSettings] = useState<AppSettings>(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        return { ...DEFAULT_APP_SETTINGS, ...JSON.parse(stored) };
      }
    } catch {
      // ignore
    }
    return DEFAULT_APP_SETTINGS;
  });

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
    } catch {
      // ignore
    }
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
