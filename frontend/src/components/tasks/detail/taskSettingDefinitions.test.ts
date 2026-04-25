import { describe, expect, it } from 'vitest';
import {
  buildBacktestTaskSettingDefinitions,
  buildTradingTaskSettingDefinitions,
} from './taskSettingDefinitions';

const t = (key: string, fallback?: string) => fallback ?? key;

describe('task setting definition contracts', () => {
  it('backtest definitions contain user-facing lifecycle/config fields', () => {
    const definitions = buildBacktestTaskSettingDefinitions(t as never, 'UTC');
    const keys = new Set(definitions.map((d) => d.key));
    expect(keys.has('strategy_type')).toBe(true);
    expect(keys.has('start_time')).toBe(true);
    expect(keys.has('end_time')).toBe(true);
    expect(keys.has('execution_id')).toBe(true);
    expect(keys.has('celery_task_id')).toBe(false);
  });

  it('formats backtest pip size and initial balance for task information', () => {
    const definitions = buildBacktestTaskSettingDefinitions(t as never, 'UTC');
    const pipSize = definitions.find(
      (definition) => definition.key === 'pip_size'
    );
    const initialBalance = definitions.find(
      (definition) => definition.key === 'initial_balance'
    );

    expect(pipSize?.format?.('0.01')).toBe('0.01');
    expect(pipSize?.format?.('0.1234')).toBe('0.12');
    expect(
      initialBalance?.render?.('10000', {
        task: { account_currency: 'USD' },
        snapshot: null,
        source: { initial_balance: '10000', account_currency: 'USD' },
      })
    ).toBe('10,000 USD');
  });

  it('trading definitions contain user-facing lifecycle/config fields', () => {
    const definitions = buildTradingTaskSettingDefinitions(t as never);
    const keys = new Set(definitions.map((d) => d.key));
    expect(keys.has('strategy_type')).toBe(true);
    expect(keys.has('dry_run')).toBe(true);
    expect(keys.has('execution_id')).toBe(true);
    expect(keys.has('celery_task_id')).toBe(false);
  });
});
