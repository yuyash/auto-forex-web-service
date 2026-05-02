import {
  Alert,
  Box,
  CircularProgress,
  Divider,
  Typography,
  type TypographyProps,
} from '@mui/material';
import { useTranslation } from 'react-i18next';
import type { TaskSummary } from '../../../hooks/useTaskSummary';
import type {
  StrategySnapshotCard,
  StrategySnapshotResponse,
} from '../../../types/strategyVisualization';
import type { MetricPoint } from '../../../utils/fetchMetrics';
import {
  currencySymbol,
  formatAppNumber,
  formatAppPercent,
  type NumberFormatSeparators,
} from '../../../utils/numberFormat';
import { useNumberFormatter } from '../../../hooks/useNumberFormatter';

type DetailNamespace = 'backtest' | 'trading';

export interface ExecutionStatusExtraItem {
  id: string;
  label: string;
  value: string;
  color?: TypographyProps['color'];
}

interface ExecutionStatusSummaryProps {
  taskNamespace: DetailNamespace;
  summary: TaskSummary;
  latestMetrics?: MetricPoint | null;
  pnlCurrency: string;
  displayedMarginRatio?: number | null;
  snapshot?: StrategySnapshotResponse | null;
  isSnapshotLoading?: boolean;
  snapshotError?: Error | null;
  extraItems?: ExecutionStatusExtraItem[];
}

interface ExecutionStatusItem {
  id: string;
  label: string;
  value: string;
  color?: TypographyProps['color'];
}

const METRIC_KEYS: Array<{
  key: 'win_rate' | 'winning_trades' | 'losing_trades' | 'total_return';
  format: 'pct' | 'int';
}> = [
  { key: 'win_rate', format: 'pct' },
  { key: 'winning_trades', format: 'int' },
  { key: 'losing_trades', format: 'int' },
  { key: 'total_return', format: 'pct' },
];

export function ExecutionStatusSummary({
  taskNamespace,
  summary,
  latestMetrics = null,
  pnlCurrency,
  displayedMarginRatio,
  snapshot = null,
  isSnapshotLoading = false,
  snapshotError = null,
  extraItems = [],
}: ExecutionStatusSummaryProps) {
  const { t } = useTranslation(['common', 'strategy', taskNamespace]);
  const { separators } = useNumberFormatter();
  const cards = snapshot?.snapshot.cards ?? [];
  const snapshotCardIds = new Set(cards.map((card) => card.id));
  const accountCurrency = summary.execution.accountCurrency || pnlCurrency;
  const items = [
    ...buildResultItems({
      taskNamespace,
      summary,
      latestMetrics,
      pnlCurrency,
      displayedMarginRatio,
      hiddenIds: snapshotCardIds,
      separators,
      t,
    }),
    ...extraItems,
    ...cards.map((card) =>
      snapshotCardToItem(card, accountCurrency, pnlCurrency, t, separators)
    ),
  ];
  const status = formatSnapshotStatus(snapshot?.snapshot.status ?? null, t);

  if (items.length === 0 && !snapshotError && !isSnapshotLoading) {
    return null;
  }

  return (
    <Box>
      <Divider sx={{ my: 2 }} />
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          flexWrap: 'wrap',
          mb: 1.5,
        }}
      >
        <Typography variant="h6">
          {t('common:labels.executionStatus', 'Execution Status')}
        </Typography>
        {status ? (
          <Typography variant="body2" color="text.secondary">
            {status}
          </Typography>
        ) : null}
        {isSnapshotLoading ? <CircularProgress size={18} /> : null}
      </Box>

      {snapshotError ? (
        <Alert severity="warning" sx={{ mb: 1.5 }}>
          {snapshotError.message}
        </Alert>
      ) : null}

      <Box
        sx={{
          display: 'grid',
          gap: 1,
          gridTemplateColumns: {
            xs: 'repeat(2, minmax(0, 1fr))',
            sm: 'repeat(3, minmax(0, 1fr))',
            lg: 'repeat(4, minmax(0, 1fr))',
            xl: 'repeat(6, minmax(0, 1fr))',
          },
        }}
      >
        {items.map((item) => (
          <ExecutionStatusTile key={item.id} item={item} />
        ))}
      </Box>
    </Box>
  );
}

function ExecutionStatusTile({ item }: { item: ExecutionStatusItem }) {
  return (
    <Box
      sx={{
        border: 1,
        borderColor: 'divider',
        borderRadius: 1,
        p: 1.25,
        minWidth: 0,
        minHeight: 68,
      }}
    >
      <Typography
        variant="caption"
        color="text.secondary"
        sx={{
          display: 'block',
          lineHeight: 1.25,
          overflowWrap: 'anywhere',
        }}
      >
        {item.label}
      </Typography>
      <Typography
        variant="body2"
        color={item.color}
        sx={{
          fontWeight: 600,
          lineHeight: 1.35,
          overflowWrap: 'anywhere',
          wordBreak: 'break-word',
        }}
      >
        {item.value}
      </Typography>
    </Box>
  );
}

function buildResultItems({
  taskNamespace,
  summary,
  latestMetrics,
  pnlCurrency,
  displayedMarginRatio,
  hiddenIds,
  separators,
  t,
}: {
  taskNamespace: DetailNamespace;
  summary: TaskSummary;
  latestMetrics: MetricPoint | null;
  pnlCurrency: string;
  displayedMarginRatio?: number | null;
  hiddenIds?: Set<string>;
  separators: NumberFormatSeparators;
  t: ReturnType<typeof useTranslation>['t'];
}): ExecutionStatusItem[] {
  const detailLabel = (key: string) => t(`${taskNamespace}:detail.${key}`);
  const items: ExecutionStatusItem[] = [
    {
      id: 'realized_pnl',
      label: detailLabel('realizedPnl'),
      value: formatCurrency(
        summary.pnl.realized,
        pnlCurrency,
        true,
        separators
      ),
      color: summary.pnl.realized >= 0 ? 'success.main' : 'error.main',
    },
    {
      id: 'unrealized_pnl',
      label: detailLabel('unrealizedPnl'),
      value: formatCurrency(
        summary.pnl.unrealized,
        pnlCurrency,
        true,
        separators
      ),
      color: summary.pnl.unrealized >= 0 ? 'success.main' : 'error.main',
    },
    ...buildCurrentBalanceItems(summary, pnlCurrency, detailLabel, separators),
    {
      id: 'total_trades',
      label: detailLabel('totalTradesCount'),
      value: formatWholeNumber(summary.counts.totalTrades, separators),
    },
    {
      id: 'open_positions',
      label: detailLabel('openPositions'),
      value: formatWholeNumber(summary.counts.openPositions, separators),
    },
    {
      id: 'closed_positions',
      label: detailLabel('closedPositions'),
      value: formatWholeNumber(summary.counts.closedPositions, separators),
    },
    {
      id: 'open_long_units',
      label: detailLabel('openLongUnits'),
      value: formatQuantity(summary.counts.openLongUnits ?? 0, separators),
    },
    {
      id: 'open_short_units',
      label: detailLabel('openShortUnits'),
      value: formatQuantity(summary.counts.openShortUnits ?? 0, separators),
    },
  ];

  if (summary.execution.ticksProcessed > 0) {
    items.push({
      id: 'ticks_processed',
      label: detailLabel('ticksProcessed'),
      value: formatWholeNumber(summary.execution.ticksProcessed, separators),
    });
  }

  if (displayedMarginRatio != null) {
    items.push({
      id: 'margin_ratio',
      label: t('common:labels.marginRatio'),
      value: formatRatio(displayedMarginRatio, separators),
    });
  }

  if (summary.execution.currentAtr != null) {
    items.push({
      id: 'current_atr',
      label: t('common:labels.currentAtr'),
      value: formatDecimal(summary.execution.currentAtr, separators),
    });
  }

  items.push(...buildMetricItems(latestMetrics, summary, t, separators));
  return items.filter((item) => !hiddenIds?.has(item.id));
}

function buildCurrentBalanceItems(
  summary: TaskSummary,
  pnlCurrency: string,
  detailLabel: (key: string) => string,
  separators: NumberFormatSeparators
): ExecutionStatusItem[] {
  if (summary.execution.currentBalance == null) return [];

  const accountCurrency = summary.execution.accountCurrency || pnlCurrency;
  const displayCurrency = summary.execution.displayCurrency;
  const hasConvertedBalance =
    summary.execution.currentBalanceDisplay != null &&
    displayCurrency != null &&
    displayCurrency !== accountCurrency;

  const value = hasConvertedBalance
    ? `${formatCurrency(
        summary.execution.currentBalanceDisplay as number,
        displayCurrency,
        false,
        separators
      )} (${formatCurrency(
        summary.execution.currentBalance,
        accountCurrency,
        false,
        separators
      )})`
    : formatCurrency(
        summary.execution.currentBalance,
        accountCurrency,
        false,
        separators
      );

  return [
    {
      id: 'current_balance',
      label: detailLabel('currentBalance'),
      value,
    },
  ];
}

function buildMetricItems(
  latestMetrics: MetricPoint | null,
  summary: TaskSummary,
  t: ReturnType<typeof useTranslation>['t'],
  separators: NumberFormatSeparators
): ExecutionStatusItem[] {
  return METRIC_KEYS.flatMap(({ key, format }) => {
    const value = metricValueForKey(key, latestMetrics, summary);
    if (value == null) return [];

    const color =
      key === 'losing_trades'
        ? 'error.main'
        : key === 'winning_trades'
          ? 'success.main'
          : undefined;

    return [
      {
        id: key,
        label: t(`common:metrics.${key}`, {
          defaultValue: key.replace(/_/g, ' '),
        }),
        value:
          format === 'pct'
            ? formatPercent(value, separators)
            : formatWholeNumber(value, separators),
        color,
      },
    ];
  });
}

function metricValueForKey(
  key: string,
  latestMetrics: MetricPoint | null,
  summary: TaskSummary
): number | null {
  const winningTrades = summary.counts.winningTrades;
  const losingTrades = summary.counts.losingTrades;

  if (key === 'winning_trades') return winningTrades;
  if (key === 'losing_trades') return losingTrades;
  if (key === 'win_rate') {
    const decidedTrades = winningTrades + losingTrades;
    return decidedTrades > 0 ? (winningTrades / decidedTrades) * 100 : 0;
  }

  if (!latestMetrics) return null;
  const raw = latestMetrics.metrics[key];
  if (raw == null || raw === '') return null;
  const value = Number(raw);
  return Number.isFinite(value) ? value : null;
}

function snapshotCardToItem(
  card: StrategySnapshotCard,
  accountCurrency: string,
  pnlCurrency: string,
  t: ReturnType<typeof useTranslation>['t'],
  separators: NumberFormatSeparators
): ExecutionStatusItem {
  const fallbackLabel = card.id.replace(/_/g, ' ');
  const labelKey = normalizeStrategyLabelKey(card.label_key);
  const label = labelKey
    ? t(`strategy:${labelKey}`, { defaultValue: fallbackLabel })
    : fallbackLabel;

  return {
    id: `snapshot_${card.id}`,
    label,
    value: formatSnapshotValue(
      card.id,
      card.value,
      accountCurrency,
      pnlCurrency,
      t,
      separators
    ),
  };
}

function normalizeStrategyLabelKey(labelKey?: string | null): string | null {
  if (!labelKey) return null;
  return labelKey.startsWith('strategy.')
    ? labelKey.slice('strategy.'.length)
    : labelKey;
}

function formatSnapshotValue(
  id: string,
  value: unknown,
  accountCurrency: string,
  pnlCurrency: string,
  t: ReturnType<typeof useTranslation>['t'],
  separators: NumberFormatSeparators
): string {
  if (value == null || value === '') return '-';

  if (typeof value === 'boolean') {
    return value ? t('common:labels.yes') : t('common:labels.no');
  }

  if (Array.isArray(value)) {
    return value.length === 0 ? '-' : value.map(String).join(', ');
  }

  if (typeof value === 'object') {
    return JSON.stringify(value);
  }

  const numericValue =
    typeof value === 'number' ? value : Number(String(value).trim());
  if (Number.isFinite(numericValue)) {
    if (isPercentKey(id)) return formatRatio(numericValue, separators);
    if (isCurrencyKey(id)) {
      return formatCurrency(
        numericValue,
        id.includes('pnl') ? pnlCurrency : accountCurrency,
        false,
        separators
      );
    }
    if (isCountKey(id)) return formatWholeNumber(numericValue, separators);
    return formatDecimal(numericValue, separators);
  }

  const stringValue = String(value);
  return t(`strategy:snapshotValues.${id}.${stringValue}`, {
    defaultValue: stringValue,
  });
}

function formatSnapshotStatus(
  status: string | null,
  t: ReturnType<typeof useTranslation>['t']
): string | null {
  if (!status) return null;
  return t(`strategy:snapshotValues.protection_level.${status}`, {
    defaultValue: status,
  });
}

function formatCurrency(
  value: number,
  currencyCode: string | null | undefined,
  signed = false,
  separators?: NumberFormatSeparators
): string {
  const symbol = currencySymbol(currencyCode);
  const formatted = formatAppNumber(
    Math.abs(value),
    {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    },
    separators
  );
  const sign = signed ? (value >= 0 ? '+' : '-') : value < 0 ? '-' : '';
  return symbol ? `${sign}${symbol} ${formatted}` : `${sign}${formatted}`;
}

function formatWholeNumber(
  value: number,
  separators?: NumberFormatSeparators
): string {
  return formatAppNumber(
    value,
    {
      maximumFractionDigits: 0,
    },
    separators
  );
}

function formatQuantity(
  value: number,
  separators?: NumberFormatSeparators
): string {
  return formatAppNumber(
    value,
    {
      maximumFractionDigits: 2,
    },
    separators
  );
}

function formatDecimal(
  value: number,
  separators?: NumberFormatSeparators
): string {
  return formatAppNumber(
    value,
    {
      maximumFractionDigits: 2,
    },
    separators
  );
}

function formatPercent(
  value: number,
  separators?: NumberFormatSeparators
): string {
  return formatAppPercent(value, 2, false, separators);
}

function formatRatio(
  value: number,
  separators?: NumberFormatSeparators
): string {
  const percentValue = Math.abs(value) <= 1 ? value * 100 : value;
  return formatPercent(percentValue, separators);
}

function isPercentKey(id: string): boolean {
  return (
    id.endsWith('_rate') ||
    id.endsWith('_ratio') ||
    id.endsWith('_return') ||
    id.includes('drawdown')
  );
}

function isCurrencyKey(id: string): boolean {
  return (
    id.includes('balance') ||
    id.includes('nav') ||
    id.includes('pnl') ||
    id.includes('profit') ||
    id.includes('loss')
  );
}

function isCountKey(id: string): boolean {
  return (
    id.endsWith('_count') ||
    id.endsWith('_cycles') ||
    id.endsWith('_entries') ||
    id.includes('trades') ||
    id.includes('positions') ||
    id.includes('ticks')
  );
}
