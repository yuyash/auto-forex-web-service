import { describe, expect, it } from 'vitest';
import {
  buildBacktestTaskSettingDefinitions,
  buildTradingTaskSettingDefinitions,
} from './taskSettingDefinitions';

const t = (key: string, fallback?: string) => fallback ?? key;

describe('task setting definition contracts', () => {
  it('backtest definitions contain core lifecycle/config fields', () => {
    const definitions = buildBacktestTaskSettingDefinitions(t as never, 'UTC');
    const keys = new Set(definitions.map((d) => d.key));
    expect(keys.has('strategy_type')).toBe(true);
    expect(keys.has('start_time')).toBe(true);
    expect(keys.has('end_time')).toBe(true);
    expect(keys.has('execution_id')).toBe(true);
    expect(keys.has('celery_task_id')).toBe(true);
  });

  it('trading definitions contain core lifecycle/config fields', () => {
    const definitions = buildTradingTaskSettingDefinitions(t as never);
    const keys = new Set(definitions.map((d) => d.key));
    expect(keys.has('strategy_type')).toBe(true);
    expect(keys.has('dry_run')).toBe(true);
    expect(keys.has('execution_id')).toBe(true);
    expect(keys.has('celery_task_id')).toBe(true);
  });
});
