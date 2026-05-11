import { Tooltip, Typography, type TypographyProps } from '@mui/material';
import { useTranslation } from 'react-i18next';
import type {
  CurrencyConversionContext,
  MoneyAmountLike,
} from '../../types/money';
import { formatCurrencyConversionContext } from '../../utils/currencyConversion';
import {
  formatMoneyAmount,
  formatMoneyPayload,
  type FormatMoneyAmountOptions,
  type NumberFormatSeparators,
} from '../../utils/numberFormat';

interface MoneyAmountTextProps {
  money?: MoneyAmountLike | null;
  fallbackAmount?: number | null;
  fallbackCurrency?: string | null;
  options?: FormatMoneyAmountOptions;
  separators?: NumberFormatSeparators;
  tooltip?: string;
  conversionContext?: CurrencyConversionContext | null;
  timezone?: string;
  language?: string;
  typographyProps?: TypographyProps;
}

export function MoneyAmountText({
  money,
  fallbackAmount,
  fallbackCurrency,
  options,
  separators,
  tooltip,
  conversionContext,
  timezone,
  language,
  typographyProps,
}: MoneyAmountTextProps) {
  const { t, i18n } = useTranslation('common');
  const text = money
    ? formatMoneyPayload(money, options, separators)
    : fallbackAmount == null
      ? '-'
      : formatMoneyAmount(
          fallbackAmount,
          fallbackCurrency,
          options,
          separators
        );
  const conversionTooltip = formatCurrencyConversionContext(conversionContext, {
    t,
    timezone,
    language: language ?? i18n.language,
    separators,
  });
  const resolvedTooltip = tooltip || conversionTooltip;
  const content = (
    <Typography component="span" {...typographyProps}>
      {text}
    </Typography>
  );
  if (!resolvedTooltip) return content;
  return (
    <Tooltip title={resolvedTooltip} arrow>
      {content}
    </Tooltip>
  );
}
