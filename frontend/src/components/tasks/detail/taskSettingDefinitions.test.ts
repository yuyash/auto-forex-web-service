import { describe, expect, it } from 'vitest';
import {
  buildBacktestTaskSettingDefinitions,
  buildTradingTaskSettingDefinitions,
} from './taskSettingDefinitions';

const t = (
  key: string,
  fallback?: string | { defaultValue?: string; [key: string]: unknown }
) => {
  if (fallback && typeof fallback === 'object') {
    return Object.entries(fallback).reduce(
      (text, [name, value]) =>
        text.replaceAll(`{{${name}}}`, value == null ? '' : String(value)),
      fallback.defaultValue ?? key
    );
  }
  return fallback ?? key;
};

describe('task setting definition contracts', () => {
  it('backtest definitions contain user-facing lifecycle/config fields', () => {
    const definitions = buildBacktestTaskSettingDefinitions(t as never, 'UTC');
    const orderedKeys = definitions.map((d) => d.key);
    const keys = new Set(definitions.map((d) => d.key));
    expect(orderedKeys.slice(0, 2)).toEqual(['id', 'execution_id']);
    expect(keys.has('id')).toBe(true);
    expect(keys.has('strategy_type')).toBe(true);
    expect(keys.has('start_time')).toBe(true);
    expect(keys.has('end_time')).toBe(true);
    expect(keys.has('sell_at_completion')).toBe(true);
    expect(keys.has('sell_on_stop')).toBe(false);
    expect(keys.has('execution_id')).toBe(true);
    expect(keys.has('celery_task_id')).toBe(false);
  });

  it('formats backtest pip size and initial balance for task information', () => {
    const definitions = buildBacktestTaskSettingDefinitions(t as never, 'UTC');
    const pipSize = definitions.find(
      (definition) => definition.key === 'pip_size'
    );
    const closeWeekday = definitions.find(
      (definition) => definition.key === 'market_close_weekday'
    );
    const openWeekday = definitions.find(
      (definition) => definition.key === 'market_open_weekday'
    );
    const initialBalance = definitions.find(
      (definition) => definition.key === 'initial_balance'
    );
    const commission = definitions.find(
      (definition) => definition.key === 'commission_per_trade'
    );

    expect(
      pipSize?.render?.('0.0001', {
        task: {},
        snapshot: null,
        source: { pip_size: '0.0001' },
      })
    ).toBe('0.0001');
    expect(
      pipSize?.render?.('0.02', {
        task: {},
        snapshot: null,
        source: {
          pip_size: '0.02',
          instrument_context: {
            instrument: 'EUR_USD',
            instrument_metadata: {
              normalized_name: 'EUR_USD',
              base_currency: 'EUR',
              quote_currency: 'USD',
              pip_size: '0.0001',
              is_high_value_quote: false,
            },
            configured_pip_size: '0.02',
            default_pip_size: '0.0001',
            effective_pip_size: '0.02',
            pip_size_source: 'task_override',
            pip_size_matches_instrument: false,
          },
        },
      })
    ).toBe('0.02 (override, default 0.0001)');
    expect(closeWeekday?.format?.(4)).toBe('Friday');
    expect(closeWeekday?.format?.(6)).toBe('Sunday');
    expect(openWeekday?.format?.(0)).toBe('Monday');
    expect(openWeekday?.format?.(6)).toBe('Sunday');
    expect(
      initialBalance?.render?.('10000', {
        task: { account_currency: 'USD' },
        snapshot: null,
        source: { initial_balance: '10000', account_currency: 'USD' },
      })
    ).toBe('10,000.00 $');
    expect(
      initialBalance?.render?.('10000', {
        task: { account_currency: 'USD' },
        snapshot: null,
        source: {
          initial_balance: '10000',
          initial_balance_money: { amount: '10000', currency: 'JPY' },
        },
      })
    ).toBe('10,000 ¥');
    expect(
      commission?.render?.('1.5', {
        task: { account_currency: 'USD' },
        snapshot: null,
        source: {
          commission_per_trade: '1.5',
          commission_per_trade_money: { amount: '1.5', currency: 'EUR' },
        },
      })
    ).toBe('1.50 €');
  });

  it('trading definitions contain user-facing lifecycle/config fields', () => {
    const definitions = buildTradingTaskSettingDefinitions(t as never);
    const orderedKeys = definitions.map((d) => d.key);
    const keys = new Set(definitions.map((d) => d.key));
    expect(orderedKeys.slice(0, 2)).toEqual(['id', 'execution_id']);
    expect(keys.has('id')).toBe(true);
    expect(keys.has('strategy_type')).toBe(true);
    expect(keys.has('dry_run')).toBe(true);
    expect(keys.has('execution_id')).toBe(true);
    expect(keys.has('celery_task_id')).toBe(false);
  });

  it('uses translated labels for overview execution, account, and API retry fields', () => {
    const jaLabels: Record<string, string> = {
      'common:labels.executionId': '実行ID',
      'trading:detail.account': 'アカウント',
      'trading:detail.accountType': 'アカウント種別',
      'trading:form.apiRetryMaxAttempts': 'OANDA API リトライ回数',
      'trading:form.apiRetryBaseSeconds': 'リトライ初期待機 (秒)',
      'trading:form.apiRetryMaxSeconds': 'リトライ最大待機 (秒)',
    };
    const translate = (key: string, fallback?: string) =>
      jaLabels[key] ?? fallback ?? key;

    const tradingDefinitions = buildTradingTaskSettingDefinitions(
      translate as never
    );
    const backtestDefinitions = buildBacktestTaskSettingDefinitions(
      translate as never,
      'UTC'
    );
    const tradingLabelByKey = Object.fromEntries(
      tradingDefinitions.map((definition) => [definition.key, definition.label])
    );
    const backtestLabelByKey = Object.fromEntries(
      backtestDefinitions.map((definition) => [
        definition.key,
        definition.label,
      ])
    );

    expect(tradingLabelByKey.account_name).toBe('アカウント');
    expect(tradingLabelByKey.account_type).toBe('アカウント種別');
    expect(tradingLabelByKey.execution_id).toBe('実行ID');
    expect(backtestLabelByKey.execution_id).toBe('実行ID');
    expect(tradingLabelByKey.api_retry_max_attempts).toBe(
      'OANDA API リトライ回数'
    );
    expect(tradingLabelByKey.api_retry_backoff_base_seconds).toBe(
      'リトライ初期待機 (秒)'
    );
    expect(tradingLabelByKey.api_retry_backoff_max_seconds).toBe(
      'リトライ最大待機 (秒)'
    );
  });
});
