export interface Position extends Record<string, unknown> {
  id: string;
  position_id: string;
  instrument: string;
  direction: 'LONG' | 'SHORT';
  units: number;
  entry_price: number;
  current_price: number;
  unrealized_pnl: number;
  realized_pnl?: number;
  status: 'OPEN' | 'CLOSED';
  layer?: number;
  opened_at: string;
  closed_at: string | null;
  account: number;
  user: number;
  strategy?: string;
}

export interface PositionFilters {
  start_date?: string;
  end_date?: string;
  instrument?: string;
  status?: 'OPEN' | 'CLOSED';
  layer?: string;
}

export interface PositionsResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: Position[];
}
