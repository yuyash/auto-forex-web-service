export interface CycleTrade {
  id: string;
  direction: 'buy' | 'sell' | null;
  units: number;
  price: string;
  execution_method: string;
  layer_index?: number | null;
  retracement_count?: number | null;
  description?: string;
  timestamp: string | null;
  position_id?: string | null;
}

export interface StrategyCycle {
  cycle_id: string;
  direction: string;
  status: 'active' | 'completed';
  started_at: string | null;
  ended_at: string | null;
  trade_count: number;
  open_count: number;
  close_count: number;
  trades: CycleTrade[];
}

export interface StrategyCyclesSummary {
  cycle_count: number;
  active_count: number;
  completed_count: number;
  total_trades: number;
}

export interface StrategyCyclesResponse {
  execution_id: string | null;
  cycles: StrategyCycle[];
  summary: StrategyCyclesSummary;
}
