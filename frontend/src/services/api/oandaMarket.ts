import { api } from '../../api/apiClient';
import { withRetry } from '../../api/client';

export interface OandaPosition {
  id: string;
  instrument: string;
  direction: string;
  units: string;
  entry_price: string;
  unrealized_pnl: string;
  open_time: string | null;
  close_time?: string | null;
  state: string;
  account_name: string;
  account_db_id: number;
  status: string;
}

export interface OandaOrder {
  id: string;
  instrument: string;
  type: string;
  direction: string;
  units: string;
  price: string | null;
  state: string;
  time_in_force: string;
  create_time: string | null;
  take_profit: string | null;
  stop_loss: string | null;
  account_name: string;
  account_db_id: number;
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface OpenPositionRequest {
  account_id: number;
  instrument: string;
  direction: 'long' | 'short';
  units: number;
  take_profit?: number;
  stop_loss?: number;
}

export interface ClosePositionRequest {
  account_id: number;
  units?: number;
}

export const oandaMarketApi = {
  getPositions: async (params: {
    account_id?: number;
    instrument?: string;
    status?: string;
    page?: number;
    page_size?: number;
    ordering?: string;
    range_from?: string;
    range_to?: string;
    timestamp_from?: string;
    timestamp_to?: string;
  }) => {
    return withRetry(() =>
      api.get<PaginatedResponse<OandaPosition>>(
        '/api/market/positions/',
        params as Record<string, unknown>
      )
    );
  },

  openPosition: async (data: OpenPositionRequest) => {
    return withRetry(() =>
      api.put<Record<string, unknown>>('/api/market/positions/', data)
    );
  },

  closePosition: async (positionId: string, data: ClosePositionRequest) => {
    return withRetry(() =>
      api.patch<Record<string, unknown>>(
        `/api/market/positions/${positionId}/`,
        data
      )
    );
  },

  getOrders: async (params: {
    account_id?: number;
    instrument?: string;
    status?: string;
    page?: number;
    page_size?: number;
    ordering?: string;
    timestamp_from?: string;
    timestamp_to?: string;
    create_time_from?: string;
    create_time_to?: string;
  }) => {
    return withRetry(() =>
      api.get<PaginatedResponse<OandaOrder>>(
        '/api/market/orders/',
        params as Record<string, unknown>
      )
    );
  },
};
