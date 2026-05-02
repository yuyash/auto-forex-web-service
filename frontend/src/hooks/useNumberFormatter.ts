import { useCallback, useMemo } from 'react';
import { useAppSettings } from './useAppSettings';
import {
  formatAppNumber,
  formatAppPercent,
  type FormatAppNumberOptions,
} from '../utils/numberFormat';

export function useNumberFormatter() {
  const { settings } = useAppSettings();
  const separators = useMemo(
    () => ({
      decimalSeparator: settings.decimalSeparator,
      thousandsSeparator: settings.thousandsSeparator,
    }),
    [settings.decimalSeparator, settings.thousandsSeparator]
  );

  const formatNumber = useCallback(
    (value: number, options?: FormatAppNumberOptions) =>
      formatAppNumber(value, options, separators),
    [separators]
  );

  const formatPercent = useCallback(
    (value: number, fractionDigits = 2, signed = false) =>
      formatAppPercent(value, fractionDigits, signed, separators),
    [separators]
  );

  return {
    formatNumber,
    formatPercent,
    separators,
  };
}
