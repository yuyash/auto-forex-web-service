import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '../config/reactQuery';
import { logger } from '../utils/logger';
import { marketApi, type GranularityOption } from '../services/api/market';

const FALLBACK_INSTRUMENTS = [
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
];

const FALLBACK_GRANULARITIES: GranularityOption[] = [
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
];

/**
 * Hook to fetch supported currency pairs from backend
 */
export const useSupportedInstruments = () => {
  const query = useQuery({
    queryKey: queryKeys.marketConfig.instruments(),
    queryFn: async () => {
      const response = await marketApi.getSupportedInstruments();
      return response.instruments ?? [];
    },
  });

  if (query.error) {
    logger.error('Failed to fetch instruments', {
      error:
        query.error instanceof Error
          ? query.error.message
          : String(query.error),
    });
  }

  return {
    instruments: query.data ?? FALLBACK_INSTRUMENTS,
    isLoading: query.isLoading,
    error: query.error instanceof Error ? query.error.message : null,
    usingFallback: !query.isLoading && !query.data && !!query.error,
  };
};

/**
 * Hook to fetch supported granularities from backend
 */
export const useSupportedGranularities = () => {
  const query = useQuery({
    queryKey: queryKeys.marketConfig.granularities(),
    queryFn: async () => {
      const response = await marketApi.getSupportedGranularities();
      return (response.granularities ?? []).filter(
        (granularity) => !granularity.value.startsWith('S')
      );
    },
  });

  if (query.error) {
    logger.error('Failed to fetch granularities', {
      error:
        query.error instanceof Error
          ? query.error.message
          : String(query.error),
    });
  }

  return {
    granularities: query.data ?? FALLBACK_GRANULARITIES,
    isLoading: query.isLoading,
    error: query.error instanceof Error ? query.error.message : null,
    usingFallback: !query.isLoading && !query.data && !!query.error,
  };
};
