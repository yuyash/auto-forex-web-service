import { api } from '../../api/apiClient';

export interface TickDataRange {
  instrument: string;
  has_data: boolean;
  min_timestamp: string | null;
  max_timestamp: string | null;
}

/**
 * Fetch the available tick data date range for a given instrument.
 */
export async function fetchTickDataRange(
  instrument: string
): Promise<TickDataRange> {
  return api.get<TickDataRange>('/api/market/ticks/range/', { instrument });
}
