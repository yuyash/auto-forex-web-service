/**
 * LatestMetricsSummary - Displays latest metric values inline in the overview results section.
 *
 * Win/loss counts and win rate are sourced from the DB-backed ``summary``
 * payload when available so they stay consistent with the numbers surfaced
 * elsewhere in the UI.  The metrics-point stream is still used for the
 * remaining fields (total_return) because those come from the runtime
 * tracker's rolling computations.
 */

import { Box, Typography } from '@mui/material';
import { useTranslation } from 'react-i18next';
import type { MetricPoint } from '../../../utils/fetchMetrics';
import type { TaskSummary } from '../../../hooks/useTaskSummary';
import { useNumberFormatter } from '../../../hooks/useNumberFormatter';

interface LatestMetricsSummaryProps {
  latest: MetricPoint | null;
  pnlCurrency: string;
  /**
   * Optional DB-backed summary.  When provided, win/loss counts and win rate
   * are taken from here instead of the (runtime) latest metric point so
   * restarts that reset the runtime counters cannot desync the display
   * from the authoritative database aggregation.
   */
  summary?: TaskSummary | null;
}

const DISPLAY_KEYS: {
  key: string;
  format: 'pct' | 'int' | 'currency' | 'number';
}[] = [
  { key: 'win_rate', format: 'pct' },
  { key: 'winning_trades', format: 'int' },
  { key: 'losing_trades', format: 'int' },
  { key: 'total_return', format: 'pct' },
];

function metricValueForKey(
  key: string,
  latest: MetricPoint | null,
  summary?: TaskSummary | null
): number | null {
  if (summary) {
    const w = summary.counts.winningTrades;
    const l = summary.counts.losingTrades;
    if (key === 'winning_trades') return w;
    if (key === 'losing_trades') return l;
    if (key === 'win_rate') {
      const decided = w + l;
      return decided > 0 ? (w / decided) * 100 : 0;
    }
  }

  if (!latest) return null;
  const raw = latest.metrics[key];
  if (raw == null || raw === '') return null;
  const num = Number(raw);
  return isNaN(num) ? null : num;
}

export function LatestMetricsSummary({
  latest,
  pnlCurrency,
  summary,
}: LatestMetricsSummaryProps) {
  const { t } = useTranslation('common');
  const { formatNumber, formatPercent } = useNumberFormatter();

  if (!latest && !summary) return null;

  const items = DISPLAY_KEYS.map(({ key, format }) => {
    const num = metricValueForKey(key, latest, summary);
    if (num == null) return null;

    let display: string;
    if (format === 'pct') display = formatPercent(num, 2);
    else if (format === 'int')
      display = formatNumber(Math.round(num), { maximumFractionDigits: 0 });
    else if (format === 'currency')
      display = `${formatNumber(num, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })} ${pnlCurrency}`;
    else
      display = formatNumber(num, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      });

    const color =
      key === 'losing_trades'
        ? 'error.main'
        : key === 'winning_trades'
          ? 'success.main'
          : undefined;

    return (
      <Box key={key}>
        <Typography variant="caption" color="text.secondary">
          {t(`metrics.${key}`, { defaultValue: key.replace(/_/g, ' ') })}
        </Typography>
        <Typography variant="body1" color={color}>
          {display}
        </Typography>
      </Box>
    );
  }).filter(Boolean);

  if (items.length === 0) return null;

  return <>{items}</>;
}
