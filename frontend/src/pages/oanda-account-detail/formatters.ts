import type { TFunction } from 'i18next';
import type { AccountSnapshotRefreshStatus } from '../../types/strategy';
import { DEFAULT_ACCOUNT_CURRENCY } from '../../constants/currencies';
import { quoteCurrencyFromInstrument } from '../../utils/instrumentCurrency';
import {
  formatAppNumber,
  formatMoneyAmount,
  normalizeCurrencyCode,
} from '../../utils/numberFormat';
import { formatDateTimeInTimezone } from '../../utils/timezone';

export type SortOrder = 'asc' | 'desc';

export const toOrdering = (field: string, order: SortOrder): string =>
  order === 'desc' ? `-${field}` : field;

const resolveCurrency = (currency?: string | null) => {
  return normalizeCurrencyCode(currency, DEFAULT_ACCOUNT_CURRENCY);
};

const resolveQuoteCurrency = (instrument?: string | null) => {
  return quoteCurrencyFromInstrument(instrument);
};

export const fmtBal = (
  value: string | number | null | undefined,
  currency?: string
) => {
  if (value == null) return '\u2014';
  const numericValue = typeof value === 'string' ? Number(value) : value;
  if (Number.isNaN(numericValue)) return '\u2014';
  return formatMoneyAmount(numericValue, resolveCurrency(currency), {
    useCurrencySymbol: false,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
};

export const fmtQuoteValue = (
  value: string | number | null | undefined,
  instrument?: string | null
) => {
  if (value == null) return '\u2014';
  const numericValue = typeof value === 'string' ? Number(value) : value;
  if (Number.isNaN(numericValue)) return '\u2014';
  const currency = resolveQuoteCurrency(instrument);
  if (currency) {
    return formatMoneyAmount(numericValue, currency, {
      useCurrencySymbol: false,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }
  const formatted = formatAppNumber(numericValue, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return formatted;
};

export const fmtSignedQuoteValue = (
  value: string | number | null | undefined,
  instrument?: string | null
) => {
  if (value == null) return '\u2014';
  const numericValue = typeof value === 'string' ? Number(value) : value;
  if (Number.isNaN(numericValue)) return '\u2014';
  const currency = resolveQuoteCurrency(instrument);
  if (currency) {
    return formatMoneyAmount(numericValue, currency, {
      useCurrencySymbol: false,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
      signed: true,
    });
  }
  const sign = numericValue >= 0 ? '+' : '';
  const formatted = formatAppNumber(numericValue, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return `${sign}${formatted}`;
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
