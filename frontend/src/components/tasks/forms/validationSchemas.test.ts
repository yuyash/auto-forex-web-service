import { describe, expect, it } from 'vitest';
import { DataSource } from '../../../types/common';
import { backtestTaskSchema } from './validationSchemas';

const baseBacktestTask = {
  config_id: '9f2d791a-9f31-4f8e-ae7a-c49f3cc8a915',
  name: 'Backtest',
  data_source: DataSource.POSTGRESQL,
  start_time: '2026-01-01T00:00:00.000Z',
  end_time: '2026-01-02T00:00:00.000Z',
  initial_balance: 10000,
  account_currency: 'JPY',
  display_currency: 'USD',
  instrument: 'USD_JPY',
  tick_granularity: '1m',
  tick_window_value_mode: 'last',
};

describe('backtestTaskSchema', () => {
  it('accepts recurring MM-DD holiday exclusions', () => {
    const result = backtestTaskSchema.safeParse({
      ...baseBacktestTask,
      excluded_dates: ['12-25', '01-01', '2026-02-11'],
    });

    expect(result.success).toBe(true);
    expect(result.data?.excluded_dates).toEqual([
      '12-25',
      '01-01',
      '2026-02-11',
    ]);
  });

  it('rejects malformed holiday exclusions', () => {
    const result = backtestTaskSchema.safeParse({
      ...baseBacktestTask,
      excluded_dates: ['2026/12/25'],
    });

    expect(result.success).toBe(false);
  });
});
