export type StrategyGridSlotState = 'filled' | 'stopped' | 'rebuilt' | 'empty';

export interface StrategyGridSlot {
  slot: number;
  state: StrategyGridSlotState;
  position_id?: string | null;
}

export interface StrategyGridLayer {
  layer: number;
  slots: StrategyGridSlot[];
}

export interface StrategyGridSummary {
  filled: number;
  stopped: number;
  rebuilt: number;
  empty: number;
  layer_count: number;
  slot_count_per_layer: number;
}

export interface StrategyGridState {
  layers: StrategyGridLayer[];
  summary: StrategyGridSummary;
}

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
  volatility?: string | null;
  margin_ratio?: string | null;
  is_rebuild?: boolean;
  pnl?: string | null;
}

export interface StrategyCycle {
  cycle_id: string;
  direction: string;
  status: 'active' | 'pending' | 'completed';
  started_at: string | null;
  ended_at: string | null;
  trade_count: number;
  open_count: number;
  close_count: number;
  open_units_total?: number;
  has_protection?: boolean;
  protection_count?: number;
  rebuild_count?: number;
  position_ids?: string[];
  realized_pnl?: string;
  unrealized_pnl?: string;
  grid_state?: StrategyGridState | null;
  trades: CycleTrade[];
}

export interface StrategyCyclesSummary {
  cycle_count: number;
  active_count: number;
  pending_count: number;
  completed_count: number;
  total_trades: number;
}

export interface StrategyCyclesResponse {
  execution_id: string | null;
  visualization?: {
    kind?: 'none' | 'timeline' | 'cycle_grid' | string;
    cycle_statuses?: boolean;
    grid?: boolean;
  };
  strategy_state?: AdaptiveNetStrategyState | null;
  cycles: StrategyCycle[];
  summary: StrategyCyclesSummary;
  last_tick_timestamp: string | null;
}

export interface AdaptiveNetMetricSignal {
  name: string;
  direction_score: string;
  confidence: string;
  size_multiplier: string;
  reason?: string;
}

export interface AdaptiveNetDecision {
  target_net_units: number;
  order_units: number;
  probability_long: string;
  probability_short: string;
  edge: string;
  confidence: string;
  risk_multiplier: string;
  metric_signals: AdaptiveNetMetricSignal[];
  reason?: string;
}

export interface AdaptiveNetDecisionHistoryPoint {
  timestamp: string;
  current_net_units: number;
  target_net_units: number;
  order_units: number;
  action: 'hold' | 'increase' | 'reduce' | 'reverse' | string;
  edge: string;
  confidence: string;
  probability_long: string;
  probability_short: string;
  risk_multiplier: string;
  metric_signals: AdaptiveNetMetricSignal[];
  position_transition?: AdaptiveNetPositionTransition | null;
}

export interface AdaptiveNetPositionTransition {
  timestamp: string;
  order_direction: 'buy' | 'sell' | 'hold' | string;
  order_units: number;
  order_abs_units: number;
  order_price: string;
  position_before_net_units: number;
  position_before_abs_units: number;
  position_before_avg_entry_price?: string | null;
  position_after_net_units: number;
  position_after_abs_units: number;
  position_after_avg_entry_price?: string | null;
  position_delta_net_units: number;
  position_delta_abs_units: number;
  action: 'hold' | 'increase' | 'reduce' | 'reverse' | string;
}

export interface AdaptiveNetStrategyState {
  current_net_units?: number;
  target_net_units?: number;
  open_units?: number;
  open_direction?: string;
  open_position_id?: string | null;
  latest_decision?: AdaptiveNetDecision | null;
  metric_signals?: AdaptiveNetMetricSignal[];
  published_metric_signals?: AdaptiveNetMetricSignal[];
  published_metric_names?: string[];
  decision_history?: AdaptiveNetDecisionHistoryPoint[];
  latest_position_transition?: AdaptiveNetPositionTransition | null;
  metric_publish_count?: number;
  last_metric_publish_tick?: number;
  last_metric_publish_at?: string | null;
  last_decision_metric_publish_count?: number;
  last_decision_at?: string | null;
  last_price?: string;
  last_spread_pips?: string;
  last_fill_price?: string | null;
  previous_net_units?: number;
  lookback_points?: number;
  window_seconds?: number;
  window_started_at?: string | null;
  last_rebalance_at?: string | null;
  rebalance_tick_delta?: number;
  rebalance_elapsed_seconds?: number | null;
}
