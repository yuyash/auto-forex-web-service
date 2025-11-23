import { useState, useEffect } from 'react';
import { apiClient } from '../services/api';
import type { Granularity } from '../types/chart';

interface GranularityOption {
  value: Granularity;
  label: string;
}

interface InstrumentsResponse {
  instruments: string[];
  count: number;
}

interface GranularitiesResponse {
  granularities: GranularityOption[];
  count: number;
}

/**
 * Hook to fetch supported currency pairs from backend
 */
export const useSupportedInstruments = () => {
  const [instruments, setInstruments] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchInstruments = async () => {
      try {
        setIsLoading(true);
        const response = await apiClient.get<InstrumentsResponse>(
          '/api/trading/instruments/'
        );
        setInstruments(response.instruments);
        setError(null);
      } catch (err) {
        console.error('Failed to fetch instruments:', err);
        setError('Failed to load currency pairs');
        // Fallback to default list
        setInstruments([
          'EUR_USD',
          'GBP_USD',
          'USD_JPY',
          'USD_CHF',
          'AUD_USD',
          'USD_CAD',
          'NZD_USD',
          'EUR_GBP',
          'EUR_JPY',
          'GBP_JPY',
          'EUR_CHF',
          'AUD_JPY',
          'GBP_CHF',
          'EUR_AUD',
          'EUR_CAD',
        ]);
      } finally {
        setIsLoading(false);
      }
    };

    fetchInstruments();
  }, []);

  return { instruments, isLoading, error };
};

/**
 * Hook to fetch supported granularities from backend
 */
export const useSupportedGranularities = () => {
  const [granularities, setGranularities] = useState<GranularityOption[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchGranularities = async () => {
      try {
        setIsLoading(true);
        const response = await apiClient.get<GranularitiesResponse>(
          '/api/trading/granularities/'
        );
        setGranularities(response.granularities);
        setError(null);
      } catch (err) {
        console.error('Failed to fetch granularities:', err);
        setError('Failed to load timeframes');
        // Fallback to default list
        setGranularities([
          { value: 'S5', label: '5 Seconds' },
          { value: 'S10', label: '10 Seconds' },
          { value: 'S15', label: '15 Seconds' },
          { value: 'S30', label: '30 Seconds' },
          { value: 'M1', label: '1 Minute' },
          { value: 'M2', label: '2 Minutes' },
          { value: 'M4', label: '4 Minutes' },
          { value: 'M5', label: '5 Minutes' },
          { value: 'M10', label: '10 Minutes' },
          { value: 'M15', label: '15 Minutes' },
          { value: 'M30', label: '30 Minutes' },
          { value: 'H1', label: '1 Hour' },
          { value: 'H2', label: '2 Hours' },
          { value: 'H3', label: '3 Hours' },
          { value: 'H4', label: '4 Hours' },
          { value: 'H6', label: '6 Hours' },
          { value: 'H8', label: '8 Hours' },
          { value: 'H12', label: '12 Hours' },
          { value: 'D', label: 'Daily' },
          { value: 'W', label: 'Weekly' },
          { value: 'M', label: 'Monthly' },
        ]);
      } finally {
        setIsLoading(false);
      }
    };

    fetchGranularities();
  }, []);

  return { granularities, isLoading, error };
};
