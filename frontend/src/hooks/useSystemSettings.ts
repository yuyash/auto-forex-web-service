import { useState, useEffect } from 'react';

export interface SystemSettings {
  registration_enabled: boolean;
  login_enabled: boolean;
}

interface UseSystemSettingsReturn {
  settings: SystemSettings | null;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

export const useSystemSettings = (): UseSystemSettingsReturn => {
  const [settings, setSettings] = useState<SystemSettings | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSettings = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/system/settings/public');

      if (!response.ok) {
        throw new Error('Failed to fetch system settings');
      }

      const data = await response.json();
      setSettings(data);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'An unexpected error occurred';
      setError(errorMessage);
      console.error('Error fetching system settings:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSettings();
  }, []);

  return {
    settings,
    loading,
    error,
    refetch: fetchSettings,
  };
};
