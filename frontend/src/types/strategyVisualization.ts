export interface StrategyVisualizationSummary {
  group_count?: number;
  active_group_count?: number;
  completed_group_count?: number;
  intervened_group_count?: number;
  open_position_count?: number;
  closed_position_count?: number;
  counter_add_count?: number;
  counter_close_count?: number;
  protection_event_count?: number;
  display_cycle_count?: number;
  trend_cycle_count?: number;
  counter_cycle_count?: number;
}

export interface StrategyVisualizationStep {
  kind: string;
  event_type: string;
  entry_id?: number | null;
  parent_entry_id?: number | null;
  timestamp?: string | null;
  basket?: string;
  direction?: string | null;
  step?: number | null;
  price?: string | number | null;
  entry_price?: string | number | null;
  exit_price?: string | number | null;
  units?: string | number | null;
  layer_number?: number | null;
  retracement_count?: number | null;
  description?: string;
  expected_interval_pips?: string | null;
  actual_interval_pips?: string | null;
  expected_tp_pips?: string | null;
  actual_tp_pips?: string | null;
  expected_exit_price?: string | null;
  actual_exit_price?: string | null;
  validation_status?: string;
}

export interface SnowballRunGroup {
  group_id: string;
  root_entry_id?: number | null;
  started_at?: string | null;
  ended_at?: string | null;
  status: 'active' | 'completed' | 'intervened' | string;
  root_direction?: string | null;
  root_basket?: string | null;
  trigger_side?: string | null;
  config_snapshot?: Record<string, string>;
  checks?: Record<string, unknown>;
  steps: StrategyVisualizationStep[];
  protection_events?: Array<{
    kind: string;
    timestamp?: string | null;
    details?: Record<string, unknown>;
  }>;
}

export interface UnsupportedViewModel {
  kind: 'unsupported';
  groups: [];
}

export interface CycleSummary {
  step_count: number;
  open_count: number;
  close_count: number;
  max_retracement: number | null;
  max_layer: number | null;
  validation_fail_count: number;
}

export interface DisplayCycleStep {
  kind: string;
  event_type: 'open_position' | 'close_position';
  entry_id: number | null;
  parent_entry_id: number | null;
  timestamp: string | null;
  basket: 'trend' | 'counter';
  direction: 'long' | 'short' | null;
  step: number | null;
  entry_price: string | null;
  exit_price: string | null;
  units: string | null;
  layer_number: number | null;
  retracement_count: number | null;
  description: string;
  expected_interval_pips: string | null;
  actual_interval_pips: string | null;
  expected_tp_pips: string | null;
  actual_tp_pips: string | null;
  expected_exit_price: string | null;
  actual_exit_price: string | null;
  validation_status: 'pass' | 'fail' | 'not_applicable';
}

export interface DisplayCycle {
  cycle_id: string;
  parent_group_id: string;
  cycle_type: 'trend' | 'counter';
  display_label: string;
  status: 'active' | 'completed' | 'intervened';
  started_at: string | null;
  ended_at: string | null;
  root_entry_id: number | null;
  root_direction: 'long' | 'short' | null;
  steps: DisplayCycleStep[];
  cycle_summary: CycleSummary;
}

export interface SnowballRunsViewModel {
  kind: 'snowball_runs';
  groups: SnowballRunGroup[];
  display_cycles?: DisplayCycle[];
}

export interface FloorLayersViewModel {
  kind: 'floor_layers';
  groups: Array<Record<string, unknown>>;
}

export type StrategyVisualizationViewModel =
  | UnsupportedViewModel
  | SnowballRunsViewModel
  | FloorLayersViewModel;

export interface StrategyVisualizationResponse {
  strategy_type: string;
  supported: boolean;
  execution_id: string | null;
  generated_at: string | null;
  summary: StrategyVisualizationSummary;
  view_model: StrategyVisualizationViewModel;
  message?: string;
}
