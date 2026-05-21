import { DataSource } from '../../../types/common';
import type {
  BacktestInitialPositionCycle,
  BacktestTaskCreateData,
  BacktestTaskUpdateData,
} from '../../../types/backtestTask';

export interface BacktestTaskPayloadFormData {
  config_id: string;
  name?: string;
  description?: string;
  start_time: string;
  end_time: string;
  initial_balance: number | string;
  account_currency?: string;
  display_currency?: string;
  commission_per_trade?: number | string;
  pip_size?: number | string;
  instrument: string;
  tick_granularity?: string;
  tick_window_value_mode?: string;
  sell_at_completion?: boolean;
  hedging_enabled?: boolean;
  drain_duration_hours?: number;
  market_idle_pre_close_minutes?: number;
  market_idle_resume_delay_minutes?: number;
  market_close_enabled?: boolean;
  market_close_weekday?: number;
  market_close_hour_utc?: number;
  market_open_weekday?: number;
  market_open_hour_utc?: number;
  max_tick_gap_hours?: number;
  spread_filter_enabled?: boolean;
  max_spread_pips?: number | string;
  oanda_candle_filter_enabled?: boolean;
  oanda_candle_filter_account?: number | null;
  oanda_candle_filter_granularity?: string;
  oanda_candle_filter_tolerance_pips?: number | string;
  holidays_enabled?: boolean;
  excluded_dates?: string[];
  initial_positions_enabled?: boolean;
  initial_position_cycles?: BacktestInitialPositionCycle[];
  in_memory_mode?: boolean;
}

function sharedBacktestTaskPayload(data: BacktestTaskPayloadFormData) {
  return {
    config: data.config_id,
    name: data.name,
    description: data.description,
    data_source: DataSource.POSTGRESQL,
    start_time: data.start_time,
    end_time: data.end_time,
    initial_balance: data.initial_balance,
    account_currency: data.account_currency,
    display_currency: data.display_currency,
    commission_per_trade: data.commission_per_trade,
    ...(data.pip_size != null && { pip_size: data.pip_size }),
    instrument: data.instrument,
    tick_granularity: data.tick_granularity,
    tick_window_value_mode: data.tick_window_value_mode,
    sell_on_stop: data.sell_at_completion ?? false,
    hedging_enabled: data.hedging_enabled,
    drain_duration_hours: data.drain_duration_hours,
    market_idle_pre_close_minutes: data.market_idle_pre_close_minutes,
    market_idle_resume_delay_minutes: data.market_idle_resume_delay_minutes,
    market_close_enabled: data.market_close_enabled,
    market_close_weekday: data.market_close_weekday,
    market_close_hour_utc: data.market_close_hour_utc,
    market_open_weekday: data.market_open_weekday,
    market_open_hour_utc: data.market_open_hour_utc,
    max_tick_gap_hours: data.max_tick_gap_hours,
    spread_filter_enabled: data.spread_filter_enabled ?? false,
    max_spread_pips: data.max_spread_pips,
    oanda_candle_filter_enabled: data.oanda_candle_filter_enabled ?? false,
    oanda_candle_filter_account: data.oanda_candle_filter_enabled
      ? (data.oanda_candle_filter_account ?? null)
      : null,
    oanda_candle_filter_granularity:
      data.oanda_candle_filter_granularity ?? 'M1',
    oanda_candle_filter_tolerance_pips: data.oanda_candle_filter_tolerance_pips,
    holidays_enabled: data.holidays_enabled,
    excluded_dates: data.excluded_dates,
    in_memory_mode: data.in_memory_mode ?? false,
    initial_positions_enabled: data.in_memory_mode
      ? false
      : (data.initial_positions_enabled ?? false),
    initial_position_cycles:
      !data.in_memory_mode && data.initial_positions_enabled
        ? (data.initial_position_cycles ?? [])
        : [],
  };
}

export function buildBacktestTaskCreatePayload(
  data: BacktestTaskPayloadFormData & { name: string },
  options?: { tracemalloc?: boolean }
): BacktestTaskCreateData {
  return {
    ...sharedBacktestTaskPayload(data),
    name: data.name,
    description: data.description,
    debug_options: options
      ? { tracemalloc: Boolean(options.tracemalloc) }
      : undefined,
  };
}

export function buildBacktestTaskUpdatePayload(
  data: BacktestTaskPayloadFormData,
  options?: { tracemalloc?: boolean }
): BacktestTaskUpdateData {
  const payload = sharedBacktestTaskPayload(data);
  return {
    ...payload,
    initial_balance: String(payload.initial_balance),
    commission_per_trade:
      payload.commission_per_trade == null
        ? undefined
        : String(payload.commission_per_trade),
    pip_size: payload.pip_size == null ? undefined : String(payload.pip_size),
    max_spread_pips:
      payload.max_spread_pips == null
        ? undefined
        : String(payload.max_spread_pips),
    oanda_candle_filter_tolerance_pips:
      payload.oanda_candle_filter_tolerance_pips == null
        ? undefined
        : String(payload.oanda_candle_filter_tolerance_pips),
    debug_options: options
      ? { tracemalloc: Boolean(options.tracemalloc) }
      : undefined,
  };
}
