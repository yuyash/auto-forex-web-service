import type { TFunction } from 'i18next';
import type { CurrencyConversionContext } from '../types/money';
import { formatAppNumber, type NumberFormatSeparators } from './numberFormat';
import { formatDateTimeInTimezone } from './timezone';

export interface CurrencyConversionFormatOptions {
  t: TFunction;
  timezone?: string;
  language?: string;
  separators?: NumberFormatSeparators;
}

export function formatCurrencyConversionContext(
  context: CurrencyConversionContext | null | undefined,
  options: CurrencyConversionFormatOptions
): string {
  if (!context) return '';

  const source = context.source_currency || '-';
  const target = context.target_currency || '-';
  if (!context.conversion_available) {
    return options.t('common:currencyConversion.unavailable', {
      source,
      target,
      defaultValue: 'Conversion unavailable for {{source}} to {{target}}',
    });
  }

  const rate = formatRate(context.rate, options.separators);
  const rateAsOf = context.rate_as_of
    ? formatDateTimeInTimezone(
        context.rate_as_of,
        options.timezone || 'UTC',
        options.language,
        { includeTimezone: true }
      )
    : options.t('common:currencyConversion.rateTimeUnavailable', {
        defaultValue: 'rate time unavailable',
      });
  const ratePath =
    context.rate_path.length > 0
      ? context.rate_path.join(' / ')
      : `${source}/${target}`;
  const policy = options.t(
    `common:currencyConversion.policies.${context.conversion_policy}`,
    {
      defaultValue: context.conversion_policy.replace(/_/g, ' '),
    }
  );

  return options.t('common:currencyConversion.tooltip', {
    source,
    target,
    rate,
    rateSource: context.rate_source || '-',
    rateAsOf,
    ratePath,
    policy,
    defaultValue:
      '{{policy}}: {{source}} to {{target}}, rate {{rate}}, source {{rateSource}}, as of {{rateAsOf}}, path {{ratePath}}',
  });
}

function formatRate(
  value: string | number | null | undefined,
  separators?: NumberFormatSeparators
): string {
  if (value == null || value === '') return '-';
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return String(value);
  return formatAppNumber(
    numeric,
    {
      maximumFractionDigits: 8,
      minimumFractionDigits: 0,
    },
    separators
  );
}
