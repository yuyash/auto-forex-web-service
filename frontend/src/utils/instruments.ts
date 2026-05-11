import type { InstrumentMetadata } from '../types/instrument';

const HIGH_VALUE_QUOTE_CURRENCIES = new Set(['JPY', 'HUF']);
export const DEFAULT_PIP_SIZE = '0.0001';
export const HIGH_VALUE_QUOTE_PIP_SIZE = '0.01';

export function normalizeInstrumentName(instrument: string): string {
  const raw = String(instrument ?? '')
    .trim()
    .toUpperCase();
  const symbol = raw.includes(':') ? (raw.split(':').pop() ?? raw) : raw;
  return symbol.replaceAll('/', '_').replaceAll('-', '_');
}

export function deriveInstrumentMetadata(
  instrumentName: string
): InstrumentMetadata {
  const normalizedName = normalizeInstrumentName(instrumentName);
  const parts = normalizedName.split('_').filter(Boolean);
  const compact = normalizedName.replaceAll('_', '');
  const baseCurrency =
    parts.length >= 2
      ? parts[0]
      : compact.length === 6
        ? compact.slice(0, 3)
        : normalizedName;
  const quoteCurrency =
    parts.length >= 2
      ? parts[parts.length - 1]
      : compact.length === 6
        ? compact.slice(3)
        : '';
  const isHighValueQuote = HIGH_VALUE_QUOTE_CURRENCIES.has(quoteCurrency);

  return {
    normalized_name: normalizedName,
    base_currency: baseCurrency,
    quote_currency: quoteCurrency,
    pip_size: isHighValueQuote ? HIGH_VALUE_QUOTE_PIP_SIZE : DEFAULT_PIP_SIZE,
    is_high_value_quote: isHighValueQuote,
  };
}

export function decimalPlacesForPipSize(
  pipSize: string | number | null | undefined,
  fallback = 4
): number {
  const numeric = Number(pipSize);
  if (!Number.isFinite(numeric) || numeric <= 0) return fallback;
  const fixed = numeric.toFixed(10).replace(/0+$/, '');
  const decimalIndex = fixed.indexOf('.');
  return decimalIndex === -1 ? 0 : fixed.length - decimalIndex - 1;
}

export function buildInstrumentMetadataMap(
  instruments: string[]
): Record<string, InstrumentMetadata> {
  return Object.fromEntries(
    instruments.map((instrument) => {
      const metadata = deriveInstrumentMetadata(instrument);
      return [metadata.normalized_name, metadata];
    })
  );
}
