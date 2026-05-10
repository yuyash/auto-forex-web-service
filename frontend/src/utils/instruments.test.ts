import { describe, expect, it } from 'vitest';
import {
  buildInstrumentMetadataMap,
  deriveInstrumentMetadata,
  normalizeInstrumentName,
} from './instruments';

describe('instrument utilities', () => {
  it('normalizes common instrument notations', () => {
    expect(normalizeInstrumentName('C:usd-jpy')).toBe('USD_JPY');
    expect(normalizeInstrumentName('eur/usd')).toBe('EUR_USD');
  });

  it('derives pip metadata from quote currency', () => {
    expect(deriveInstrumentMetadata('USD_JPY')).toMatchObject({
      base_currency: 'USD',
      quote_currency: 'JPY',
      pip_size: '0.01',
      is_high_value_quote: true,
    });
    expect(buildInstrumentMetadataMap(['EUR_USD']).EUR_USD).toMatchObject({
      base_currency: 'EUR',
      quote_currency: 'USD',
      pip_size: '0.0001',
    });
  });
});
