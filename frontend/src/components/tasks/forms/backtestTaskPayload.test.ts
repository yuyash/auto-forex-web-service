import { describe, expect, it } from 'vitest';
import {
  buildBacktestTaskCreatePayload,
  buildBacktestTaskUpdatePayload,
} from './backtestTaskPayload';
import { DataSource } from '../../../types/common';

const baseFormData = {
  config_id: '9f2d791a-9f31-4f8e-ae7a-c49f3cc8a915',
  name: 'Backtest',
  description: 'Regression run',
  start_time: '2026-01-01T00:00:00.000Z',
  end_time: '2026-01-02T00:00:00.000Z',
  initial_balance: 10000,
  commission_per_trade: 1.25,
  pip_size: 0.01,
  instrument: 'USD_JPY',
  tick_granularity: '1m',
  tick_window_value_mode: 'last',
  sell_at_completion: true,
  hedging_enabled: false,
  drain_duration_hours: 4,
  market_idle_pre_close_minutes: 30,
  market_idle_resume_delay_minutes: 15,
  market_close_enabled: true,
  market_close_weekday: 4,
  market_close_hour_utc: 21,
  market_open_weekday: 6,
  market_open_hour_utc: 21,
  max_tick_gap_hours: 120,
};

describe('backtest task payload builders', () => {
  it('maps create form data to the backend payload', () => {
    expect(buildBacktestTaskCreatePayload(baseFormData)).toMatchObject({
      config: baseFormData.config_id,
      name: baseFormData.name,
      description: baseFormData.description,
      data_source: DataSource.POSTGRESQL,
      initial_balance: 10000,
      commission_per_trade: 1.25,
      pip_size: 0.01,
      sell_on_stop: true,
      hedging_enabled: false,
      market_close_enabled: true,
      max_tick_gap_hours: 120,
    });
  });

  it('stringifies decimal fields and preserves debug options for updates', () => {
    expect(
      buildBacktestTaskUpdatePayload(baseFormData, { tracemalloc: true })
    ).toMatchObject({
      config: baseFormData.config_id,
      data_source: DataSource.POSTGRESQL,
      initial_balance: '10000',
      commission_per_trade: '1.25',
      pip_size: '0.01',
      sell_on_stop: true,
      debug_options: { tracemalloc: true },
    });
  });
});
