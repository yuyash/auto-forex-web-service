import type { TaskPosition } from '../../../hooks/useTaskPositions';
import type { CopyValueExtractors } from '../../../utils/tableCopyUtils';
import {
  currencySymbol,
  formatAppNumber,
  formatMoneyAmount,
  formatMoneyPayload,
} from '../../../utils/numberFormat';

type PositionDirection = 'long' | 'short';

interface TaskPositionCopyExtractorOptions {
  currentPrice?: number | null;
  pipSize?: number | null;
  formatTimestamp: (value: string) => string;
  formatPrice: (
    value: string | number | null | undefined,
    digits?: number
  ) => string;
}

export function createClosedPositionCopyExtractors(
  direction: PositionDirection,
  options: TaskPositionCopyExtractorOptions
): CopyValueExtractors<TaskPosition> {
  const { formatTimestamp, formatPrice, pipSize } = options;
  return {
    ...baseCopyExtractors(formatTimestamp, formatPrice),
    exit_time: (row) => (row.exit_time ? formatTimestamp(row.exit_time) : '-'),
    exit_price: (row) =>
      formatPriceWithCurrency(
        row.exit_price,
        row.unrealized_pnl_currency,
        formatPrice
      ),
    pips: (row) =>
      formatPositionPips(row, direction, {
        pipSize,
        formatPrice,
      }),
    realized_pnl: (row) =>
      formatClosedPositionPnl(row, direction, { signed: false }),
    close_reason: (row) => row.close_reason ?? '-',
  };
}

export function createOpenPositionCopyExtractors(
  direction: PositionDirection,
  options: TaskPositionCopyExtractorOptions
): CopyValueExtractors<TaskPosition> {
  const { currentPrice, formatTimestamp, formatPrice, pipSize } = options;
  return {
    ...baseCopyExtractors(formatTimestamp, formatPrice),
    pips: (row) =>
      formatOpenPositionPips(row, direction, {
        currentPrice,
        pipSize,
        formatPrice,
      }),
    unrealized_pnl: (row) =>
      formatOpenPositionPnl(row, direction, { currentPrice, signed: false }),
  };
}

export function createGenericPositionCopyExtractors(
  options: TaskPositionCopyExtractorOptions
): CopyValueExtractors<TaskPosition> {
  const { currentPrice, formatTimestamp, formatPrice, pipSize } = options;
  return {
    ...baseCopyExtractors(formatTimestamp, formatPrice),
    direction: (row) => row.direction ?? '-',
    is_open: (row) => (row.is_open ? 'Open' : 'Closed'),
    exit_time: (row) => (row.exit_time ? formatTimestamp(row.exit_time) : '-'),
    exit_price: (row) =>
      formatPriceWithCurrency(
        row.exit_price,
        row.unrealized_pnl_currency,
        formatPrice
      ),
    pips: (row) => {
      const direction = row.direction;
      if (row.exit_price) {
        return formatPositionPips(row, direction, {
          pipSize,
          formatPrice,
        });
      }
      return formatOpenPositionPips(row, direction, {
        currentPrice,
        pipSize,
        formatPrice,
      });
    },
    pnl: (row) =>
      row.is_open
        ? formatOpenPositionPnl(row, row.direction, {
            currentPrice,
            signed: false,
          })
        : formatClosedPositionPnl(row, row.direction, { signed: false }),
    close_reason: (row) => row.close_reason ?? '-',
  };
}

function baseCopyExtractors(
  formatTimestamp: (value: string) => string,
  formatPrice: (
    value: string | number | null | undefined,
    digits?: number
  ) => string
): CopyValueExtractors<TaskPosition> {
  return {
    id: (row) => (row.id ? String(row.id).slice(0, 8) : '-'),
    replayed_at: (row) =>
      row.replayed_at ? formatTimestamp(row.replayed_at) : '-',
    entry_time: (row) =>
      row.entry_time ? formatTimestamp(row.entry_time) : '-',
    instrument: (row) => row.instrument ?? '-',
    units: (row) => formatAppNumber(Math.abs(row.units)),
    layer_index: (row) =>
      row.layer_index != null ? String(row.layer_index) : '-',
    retracement_count: (row) =>
      row.retracement_count != null ? String(row.retracement_count) : '-',
    entry_price: (row) =>
      formatPriceWithCurrency(
        row.entry_price,
        row.unrealized_pnl_currency,
        formatPrice
      ),
    planned_exit_price: (row) =>
      formatPriceWithCurrency(
        row.planned_exit_price,
        row.unrealized_pnl_currency,
        formatPrice
      ),
    planned_exit_price_formula: (row) => row.planned_exit_price_formula ?? '-',
    oanda_trade_id: (row) => row.oanda_trade_id ?? '-',
    stop_loss_price: (row) =>
      formatPriceWithCurrency(
        row.stop_loss_price,
        row.unrealized_pnl_currency,
        formatPrice
      ),
    is_rebuild: (row) => (row.is_rebuild ? 'Yes' : '-'),
  };
}

function formatPositionPips(
  row: TaskPosition,
  direction: PositionDirection,
  options: Pick<TaskPositionCopyExtractorOptions, 'formatPrice' | 'pipSize'>
): string {
  const entryPrice = parseOptionalFloat(row.entry_price);
  const exitPrice = parseOptionalFloat(row.exit_price);
  if (entryPrice == null || exitPrice == null || !options.pipSize) return '-';
  const pips =
    (direction === 'long' ? exitPrice - entryPrice : entryPrice - exitPrice) /
    options.pipSize;
  return Number.isFinite(pips) ? options.formatPrice(pips, 1) : '-';
}

function formatOpenPositionPips(
  row: TaskPosition,
  direction: PositionDirection,
  options: Pick<
    TaskPositionCopyExtractorOptions,
    'currentPrice' | 'formatPrice' | 'pipSize'
  >
): string {
  const entryPrice = parseOptionalFloat(row.entry_price);
  if (entryPrice == null || options.currentPrice == null || !options.pipSize) {
    return '-';
  }
  const pips =
    (direction === 'long'
      ? options.currentPrice - entryPrice
      : entryPrice - options.currentPrice) / options.pipSize;
  return Number.isFinite(pips) ? options.formatPrice(pips, 1) : '-';
}

function formatClosedPositionPnl(
  row: TaskPosition,
  direction: PositionDirection,
  options: { signed: boolean }
): string {
  const money = row.realized_pnl_display_money ?? row.realized_pnl_money;
  if (money) {
    return formatMoneyPayload(money, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
      signed: options.signed,
    });
  }
  const entryPrice = parseOptionalFloat(row.entry_price);
  const exitPrice = parseOptionalFloat(row.exit_price);
  if (entryPrice == null || exitPrice == null) return '-';
  const value =
    parseOptionalFloat(row.realized_pnl) ??
    (() => {
      const units = Math.abs(row.units ?? 0);
      return direction === 'long'
        ? (exitPrice - entryPrice) * units
        : (entryPrice - exitPrice) * units;
    })();
  return formatMoney(
    value,
    row.realized_pnl_currency || row.unrealized_pnl_currency,
    {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
      signed: options.signed,
    }
  );
}

function formatOpenPositionPnl(
  row: TaskPosition,
  direction: PositionDirection,
  options: { currentPrice?: number | null; signed: boolean }
): string {
  const money = row.unrealized_pnl_display_money ?? row.unrealized_pnl_money;
  if (money) {
    return formatMoneyPayload(money, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
      signed: options.signed,
    });
  }
  const storedValue = parseOptionalFloat(row.unrealized_pnl);
  if (storedValue != null) {
    return formatMoney(storedValue, row.unrealized_pnl_currency, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
      signed: options.signed,
    });
  }
  const entryPrice = parseOptionalFloat(row.entry_price);
  if (entryPrice == null || options.currentPrice == null) return '-';
  const units = Math.abs(row.units ?? 0);
  const value =
    direction === 'long'
      ? (options.currentPrice - entryPrice) * units
      : (entryPrice - options.currentPrice) * units;
  return formatMoney(value, row.unrealized_pnl_currency, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
    signed: options.signed,
  });
}

function formatPriceWithCurrency(
  value: string | number | null | undefined,
  currency: string | null | undefined,
  formatPrice: (
    value: string | number | null | undefined,
    digits?: number
  ) => string
): string {
  const formatted = value == null || value === '' ? '-' : formatPrice(value, 3);
  return formatted === '-'
    ? formatted
    : `${currencyPrefix(currency)}${formatted}`;
}

function formatMoney(
  value: number,
  currency: string | null | undefined,
  options: Parameters<typeof formatAppNumber>[1]
): string {
  return formatMoneyAmount(value, currency, options);
}

function currencyPrefix(currency: string | null | undefined): string {
  const symbol = currency ? currencySymbol(currency) : '';
  return symbol.length > 2 ? `${symbol} ` : symbol;
}

function parseOptionalFloat(value: string | number | null | undefined) {
  if (value == null || value === '') return null;
  const parsed = typeof value === 'number' ? value : Number.parseFloat(value);
  return Number.isFinite(parsed) ? parsed : null;
}
