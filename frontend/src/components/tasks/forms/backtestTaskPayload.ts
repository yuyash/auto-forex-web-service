import { DataSource } from '../../../types/common';
import type {
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
    commission_per_trade: data.commission_per_trade,
    ...(data.pip_size != null && { pip_size: data.pip_size }),
    instrument: data.instrument,
    tick_granularity: data.tick_granularity,
    tick_window_value_mode: data.tick_window_value_mode,
    sell_on_stop: data.sell_at_completion,
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
  };
}

export function buildBacktestTaskCreatePayload(
  data: BacktestTaskPayloadFormData & { name: string }
): BacktestTaskCreateData {
  return {
    ...sharedBacktestTaskPayload(data),
    name: data.name,
    description: data.description,
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
    debug_options: options
      ? { tracemalloc: Boolean(options.tracemalloc) }
      : undefined,
  };
}
