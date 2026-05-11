import { Tooltip, Typography, type TypographyProps } from '@mui/material';
import type { MoneyAmountLike } from '../../types/money';
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
  typographyProps?: TypographyProps;
}

export function MoneyAmountText({
  money,
  fallbackAmount,
  fallbackCurrency,
  options,
  separators,
  tooltip,
  typographyProps,
}: MoneyAmountTextProps) {
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
  const content = (
    <Typography component="span" {...typographyProps}>
      {text}
    </Typography>
  );
  if (!tooltip) return content;
  return (
    <Tooltip title={tooltip} arrow>
      {content}
    </Tooltip>
  );
}
