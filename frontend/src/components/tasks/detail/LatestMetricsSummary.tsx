/**
 * LatestMetricsSummary - Displays latest metric values inline in the overview results section.
 */

import { Box, Typography } from '@mui/material';
import { useTranslation } from 'react-i18next';
import type { MetricPoint } from '../../../utils/fetchMetrics';

interface LatestMetricsSummaryProps {
  latest: MetricPoint | null;
  pnlCurrency: string;
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

export function LatestMetricsSummary({
  latest,
  pnlCurrency,
}: LatestMetricsSummaryProps) {
  const { t } = useTranslation('common');

  if (!latest) return null;

  const items = DISPLAY_KEYS.map(({ key, format }) => {
    const raw = latest.metrics[key];
    if (raw == null || raw === '') return null;
    const num = Number(raw);
    if (isNaN(num)) return null;

    let display: string;
    if (format === 'pct') display = `${num.toFixed(2)}%`;
    else if (format === 'int') display = Math.round(num).toLocaleString();
    else if (format === 'currency')
      display = `${num.toFixed(2)} ${pnlCurrency}`;
    else display = num.toFixed(2);

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
