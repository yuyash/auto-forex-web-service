import { api } from '../../api/apiClient';
import type { Granularity } from '../../types/chart';

export interface TickDataRange {
  instrument: string;
  has_data: boolean;
  min_timestamp: string | null;
  max_timestamp: string | null;
}

export interface CandlesResponse {
  candles?: unknown[];
}

export interface GranularityOption {
  value: Granularity;
  label: string;
}

interface InstrumentsResponse {
  instruments?: string[];
}

interface GranularitiesResponse {
  granularities?: GranularityOption[];
}

/**
 * Fetch the available tick data date range for a given instrument.
 */
export async function fetchTickDataRange(
  instrument: string
): Promise<TickDataRange> {
  return api.get<TickDataRange>('/api/market/ticks/range/', { instrument });
}

export const marketApi = {
  getSupportedInstruments: () =>
    api.get<InstrumentsResponse>('/api/market/instruments/'),
  getSupportedGranularities: () =>
    api.get<GranularitiesResponse>('/api/market/candles/granularities/'),
  getCandles: (params: Record<string, string | number | undefined>) =>
    api.get<CandlesResponse>('/api/market/candles/', params),
  getTickDataRange: fetchTickDataRange,
};
