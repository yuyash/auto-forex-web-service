import { api } from '../../api/apiClient';
import type { Granularity } from '../../types/chart';

export interface TickDataRange {
  instrument: string;
  has_data: boolean;
  min_timestamp: string | null;
  max_timestamp: string | null;
}

export interface TickDataPoint {
  instrument: string;
  timestamp: string;
  bid: string;
  ask: string;
  mid: string;
}

interface TicksResponse {
  count: number;
  instrument: string;
  next_cursor: string | null;
  ticks: TickDataPoint[];
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

export interface MarketStatusResponse {
  is_open: boolean;
  current_session?: string;
  next_event?: {
    type: string;
    time: string;
  };
  sessions?: Record<string, unknown>[];
}

/**
 * Fetch the available tick data date range for a given instrument.
 */
export async function fetchTickDataRange(
  instrument: string
): Promise<TickDataRange> {
  return api.get<TickDataRange>('/api/market/ticks/range/', { instrument });
}

/**
 * Fetch the first tick in a backtest period for a given instrument.
 */
export async function fetchFirstTick(
  instrument: string,
  fromTime: string,
  toTime: string
): Promise<TickDataPoint | null> {
  const response = await api.get<TicksResponse>('/api/market/ticks/', {
    instrument,
    from_time: fromTime,
    to_time: toTime,
    page_size: 1,
    ordering: 'timestamp',
  });
  return response.ticks[0] ?? null;
}

export const marketApi = {
  getSupportedInstruments: () =>
    api.get<InstrumentsResponse>('/api/market/instruments/'),
  getSupportedGranularities: () =>
    api.get<GranularitiesResponse>('/api/market/candles/granularities/'),
  getCandles: (params: Record<string, string | number | undefined>) =>
    api.get<CandlesResponse>('/api/market/candles/', params),
  getTickDataRange: fetchTickDataRange,
  getFirstTick: fetchFirstTick,
  getMarketStatus: () =>
    api.get<MarketStatusResponse>('/api/market/market/status/'),
};
