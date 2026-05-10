function normalizedInstrumentParts(instrument?: string | null): string[] {
  const raw = String(instrument ?? '')
    .trim()
    .toUpperCase();
  if (!raw) return [];
  const withoutPrefix = raw.includes(':') ? raw.split(':').pop() || raw : raw;
  const separated = withoutPrefix.replace(/[-/]/g, '_');
  if (separated.includes('_')) {
    return separated.split('_').filter(Boolean);
  }
  const compact = separated.replace(/_/g, '');
  return compact.length === 6 ? [compact.slice(0, 3), compact.slice(3)] : [];
}

export function baseCurrencyFromInstrument(
  instrument?: string | null
): string | null {
  return normalizedInstrumentParts(instrument)[0] ?? null;
}

export function quoteCurrencyFromInstrument(
  instrument?: string | null
): string | null {
  const parts = normalizedInstrumentParts(instrument);
  return parts.length >= 2 ? parts[parts.length - 1] : null;
}
