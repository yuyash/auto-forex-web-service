import type { TFunction } from 'i18next';
import type { AccountSnapshotRefreshStatus } from '../../types/strategy';
import { formatAppNumber } from '../../utils/numberFormat';
import { formatDateTimeInTimezone } from '../../utils/timezone';

const DEFAULT_CURRENCY = 'USD';

export type SortOrder = 'asc' | 'desc';

export const toOrdering = (field: string, order: SortOrder): string =>
  order === 'desc' ? `-${field}` : field;

const resolveCurrency = (currency?: string | null) => {
  if (!currency) return DEFAULT_CURRENCY;
  const trimmed = currency.trim().toUpperCase();
  return trimmed.length === 3 ? trimmed : DEFAULT_CURRENCY;
};

const resolveQuoteCurrency = (instrument?: string | null) => {
  if (!instrument || !instrument.includes('_')) return null;
  const [, quoteCurrency] = instrument.split('_');
  const normalized = quoteCurrency?.trim().toUpperCase();
  return normalized && normalized.length === 3 ? normalized : null;
};

export const fmtBal = (
  value: string | number | null | undefined,
  currency?: string
) => {
  if (value == null) return '\u2014';
  const numericValue = typeof value === 'string' ? Number(value) : value;
  if (Number.isNaN(numericValue)) return '\u2014';
  const code = resolveCurrency(currency);
  try {
    return `${code} ${formatAppNumber(numericValue, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;
  } catch {
    return `${code} ${formatAppNumber(numericValue, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;
  }
};

export const fmtQuoteValue = (
  value: string | number | null | undefined,
  instrument?: string | null
) => {
  if (value == null) return '\u2014';
  const numericValue = typeof value === 'string' ? Number(value) : value;
  if (Number.isNaN(numericValue)) return '\u2014';
  const currency = resolveQuoteCurrency(instrument);
  const formatted = formatAppNumber(numericValue, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return currency ? `${formatted} ${currency}` : formatted;
};

export const fmtSignedQuoteValue = (
  value: string | number | null | undefined,
  instrument?: string | null
) => {
  if (value == null) return '\u2014';
  const numericValue = typeof value === 'string' ? Number(value) : value;
  if (Number.isNaN(numericValue)) return '\u2014';
  const sign = numericValue >= 0 ? '+' : '';
  return `${sign}${fmtQuoteValue(numericValue, instrument)}`;
};

export const fmtJson = (value: unknown) => {
  if (value == null) return '\u2014';
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
};

export const fmtTs = (
  timestamp: string | null,
  timezone = 'UTC',
  language?: string
): string => {
  if (!timestamp) return '\u2014';
  return formatDateTimeInTimezone(timestamp, timezone, language, {
    includeSeconds: true,
    includeTimezone: true,
  });
};

export const snapshotRefreshStatusLabel = (
  t: TFunction,
  status: AccountSnapshotRefreshStatus
) => {
  if (status === 'queued') {
    return t('settings:accounts.snapshotRefreshQueued', 'Refresh queued');
  }
  if (status === 'running') {
    return t('settings:accounts.snapshotRefreshRunning', 'Refreshing');
  }
  if (status === 'completed') {
    return t('settings:accounts.snapshotRefreshCompleted', 'Refresh complete');
  }
  if (status === 'failed') {
    return t('settings:accounts.snapshotRefreshFailed', 'Refresh failed');
  }
  return t('settings:accounts.snapshotRefreshIdle', 'Refresh idle');
};
