import { describe, expect, it } from 'vitest';
import type { TFunction } from 'i18next';
import { formatCurrencyConversionContext } from '../../../src/utils/currencyConversion';
import type { CurrencyConversionContext } from '../../../src/types/money';

const t = ((key: string, options?: Record<string, unknown>) => {
  if (key.endsWith('policies.runtime_fx_rate')) return 'Runtime FX conversion';
  if (key.endsWith('policies.identity')) return 'No conversion';
  if (typeof options?.defaultValue !== 'string') return key;
  return options.defaultValue.replace(/\{\{(\w+)\}\}/g, (_match, token) =>
    String(options[token] ?? '')
  );
}) as TFunction;

describe('formatCurrencyConversionContext', () => {
  it('formats available runtime conversion metadata', () => {
    const context: CurrencyConversionContext = {
      source_currency: 'USD',
      target_currency: 'JPY',
      rate: '150.123456789',
      rate_source: 'instrument_mid',
      rate_as_of: '2026-01-01T00:00:00Z',
      rate_path: ['USD/JPY', 'direct'],
      conversion_available: true,
      conversion_policy: 'runtime_fx_rate',
    };

    const label = formatCurrencyConversionContext(context, {
      language: 'en',
      separators: { decimalSeparator: '.', thousandsSeparator: ',' },
      t,
      timezone: 'UTC',
    });

    expect(label).toContain('Runtime FX conversion');
    expect(label).toContain('USD to JPY');
    expect(label).toContain('150.12345679');
    expect(label).toContain('instrument_mid');
    expect(label).toContain('USD/JPY / direct');
  });

  it('formats unavailable conversion metadata', () => {
    const context: CurrencyConversionContext = {
      source_currency: 'EUR',
      target_currency: 'JPY',
      rate: null,
      rate_source: 'unavailable',
      rate_as_of: null,
      rate_path: [],
      conversion_available: false,
      conversion_policy: 'unavailable',
    };

    const label = formatCurrencyConversionContext(context, { t });

    expect(label).toBe('Conversion unavailable for EUR to JPY');
  });
});
