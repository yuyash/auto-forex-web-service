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
  const [retryCount, setRetryCount] = useState<number>(0);

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
      setRetryCount(0); // Reset retry count on success
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'An unexpected error occurred';
      setError(errorMessage);
      console.error('Failed to fetch system settings');

      // Don't retry automatically - just show error
      setRetryCount((prev) => prev + 1);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Only fetch once on mount, don't retry automatically
    if (retryCount === 0) {
      fetchSettings();
    }
  }, [retryCount]);

  return {
    settings,
    loading,
    error,
    refetch: fetchSettings,
  };
};
