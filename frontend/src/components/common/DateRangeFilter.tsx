/**
 * DateRangeFilter — reusable date-range filter row for data tables.
 *
 * Renders two datetime-local inputs (from / to) in a compact row that
 * wraps gracefully on mobile.
 */

import { Box, TextField } from '@mui/material';
import { useTranslation } from 'react-i18next';

export interface DateRangeFilterProps {
  from: string;
  to: string;
  onFromChange: (value: string) => void;
  onToChange: (value: string) => void;
  fromLabel?: string;
  toLabel?: string;
}

export function DateRangeFilter({
  from,
  to,
  onFromChange,
  onToChange,
  fromLabel,
  toLabel,
}: DateRangeFilterProps) {
  const { t } = useTranslation('common');

  return (
    <Box
      sx={{
        display: 'flex',
        gap: 1,
        flexWrap: 'wrap',
        alignItems: 'center',
      }}
    >
      <TextField
        label={fromLabel ?? t('filters.dateFrom')}
        type="datetime-local"
        size="small"
        value={from}
        onChange={(e) => onFromChange(e.target.value)}
        slotProps={{ inputLabel: { shrink: true } }}
        sx={{ minWidth: { xs: 160, sm: 200 } }}
      />
      <TextField
        label={toLabel ?? t('filters.dateTo')}
        type="datetime-local"
        size="small"
        value={to}
        onChange={(e) => onToChange(e.target.value)}
        slotProps={{ inputLabel: { shrink: true } }}
        sx={{ minWidth: { xs: 160, sm: 200 } }}
      />
    </Box>
  );
}
