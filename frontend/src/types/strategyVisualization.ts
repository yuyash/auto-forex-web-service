import type {
  CurrencyConversionContext,
  MoneyAmountLike,
  TaskMoneyContext,
} from './money';

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
  is_initial_position_seed?: boolean;
  pnl?: string | null;
  pnl_money?: MoneyAmountLike | null;
  pnl_display_money?: MoneyAmountLike | null;
  display_conversion_context?: CurrencyConversionContext | null;
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
  is_initial_position_seed?: boolean;
  initial_position_seed_count?: number;
  position_ids?: string[];
  realized_pnl?: string;
  unrealized_pnl?: string;
  realized_pnl_money?: MoneyAmountLike | null;
  unrealized_pnl_money?: MoneyAmountLike | null;
  total_pnl_money?: MoneyAmountLike | null;
  realized_pnl_display_money?: MoneyAmountLike | null;
  unrealized_pnl_display_money?: MoneyAmountLike | null;
  total_pnl_display_money?: MoneyAmountLike | null;
  display_conversion_context?: CurrencyConversionContext | null;
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

export interface StrategyCyclesPagination {
  page: number;
  page_size: number;
  total_count: number;
  total_pages: number;
}

export interface StrategyCyclesResponse {
  execution_id: string | null;
  visualization?: {
    kind?: 'none' | 'timeline' | 'cycle_grid' | string;
    cycle_statuses?: boolean;
    grid?: boolean;
  };
  cycles: StrategyCycle[];
  summary: StrategyCyclesSummary;
  pagination: StrategyCyclesPagination | null;
  last_tick_timestamp: string | null;
  strategy_type?: string;
  money_context?: TaskMoneyContext | null;
}

export interface StrategySnapshotCard {
  id: string;
  label_key?: string | null;
  value: unknown;
}

export interface StrategySnapshotResponse {
  execution_id: string | null;
  strategy_type: string;
  instrument?: string | null;
  timestamp?: string | null;
  snapshot: {
    status?: string | null;
    cards: StrategySnapshotCard[];
    state: Record<string, unknown>;
  };
}

export interface StrategyHistoryEntry {
  id: string;
  timestamp?: string | null;
  t?: number | null;
  source: string;
  category: string;
  action?: string | null;
  label?: string | null;
  severity?: string | null;
  details: Record<string, unknown>;
}

export interface StrategyHistoryResponse {
  execution_id: string | null;
  strategy_type: string;
  instrument?: string | null;
  count: number;
  next: string | null;
  previous: string | null;
  page: number;
  page_size: number;
  ordering: string;
  granularity: string;
  results: StrategyHistoryEntry[];
}

export interface StrategyMetricsResponse {
  execution_id: string | null;
  strategy_type: string;
  instrument?: string | null;
  count: number;
  next: string | null;
  previous: string | null;
  page: number;
  page_size: number;
  ordering: string;
  granularity: string;
  data_source: string;
  resume_cursor_timestamp: string | null;
  consistency_warnings: Array<Record<string, unknown>>;
  ohlc_layers?: StrategyOhlcLayers | null;
  results: Array<{
    t: number;
    timestamp?: string;
    metrics: Record<string, unknown>;
  }>;
}

export type StrategyOhlcLineStyle =
  | 'solid'
  | 'dashed'
  | 'dotted'
  | 'large_dashed'
  | 'sparse_dotted'
  | number;

export interface StrategyOhlcPoint {
  time: string | number;
  value: number | string;
}

export interface StrategyOhlcPriceSeries {
  id: string;
  label?: string | null;
  label_key?: string | null;
  color: string;
  line_style?: StrategyOhlcLineStyle;
  points: StrategyOhlcPoint[];
}

export interface StrategyOhlcBandPoint {
  time: string | number;
  from: number | string;
  to: number | string;
}

export interface StrategyOhlcPriceBandSeries {
  id: string;
  label?: string | null;
  label_key?: string | null;
  color: string;
  points: StrategyOhlcBandPoint[];
}

export interface StrategyOhlcLayers {
  price_series: StrategyOhlcPriceSeries[];
  price_band_series: StrategyOhlcPriceBandSeries[];
  pagination?: {
    count: number;
    page: number;
    page_size: number;
    ordering: string;
    granularity?: string | null;
    since?: string | null;
    until?: string | null;
  };
}

export interface SnowballNetCandle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

export interface SnowballNetLinePoint {
  time: number;
  value: number;
}

export interface SnowballNetLineSeries {
  id: string;
  label?: string | null;
  label_key?: string | null;
  color: string;
  line_style?: StrategyOhlcLineStyle;
  points: SnowballNetLinePoint[];
}

export interface SnowballNetMarker {
  id: string;
  time: number;
  timestamp?: string | null;
  action: 'open' | 'close' | string;
  direction?: string | null;
  units: number;
  price?: number | null;
  count: number;
  label?: string | null;
  description?: string | null;
  trade_ids?: string[];
  position_id?: string | null;
}

export interface SnowballNetChartResponse {
  execution_id: string | null;
  strategy_type: string;
  instrument?: string | null;
  window: {
    granularity: string;
    granularity_seconds: number;
    center: string;
    since: string;
    until: string;
    follow: boolean;
    merge_markers: boolean;
  };
  current: Record<string, unknown>;
  candles: SnowballNetCandle[];
  price_lines: SnowballNetLineSeries[];
  oscillator_lines: SnowballNetLineSeries[];
  markers: SnowballNetMarker[];
}
