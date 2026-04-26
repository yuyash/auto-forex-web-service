/**
 * DateRangeFilter — reusable date-range filter row for data tables.
 *
 * Renders two datetime-local inputs (from / to) in a compact row that
 * wraps gracefully on mobile.
 */

import { Box, TextField, type SxProps, type Theme } from '@mui/material';
import { useTranslation } from 'react-i18next';

export interface DateRangeFilterProps {
  from: string;
  to: string;
  onFromChange: (value: string) => void;
  onToChange: (value: string) => void;
  fromLabel?: string;
  toLabel?: string;
  sx?: SxProps<Theme>;
  fieldSx?: SxProps<Theme>;
}

export function DateRangeFilter({
  from,
  to,
  onFromChange,
  onToChange,
  fromLabel,
  toLabel,
  sx,
  fieldSx,
}: DateRangeFilterProps) {
  const { t } = useTranslation('common');
  const rootSx = Array.isArray(sx) ? sx : [sx];
  const inputSx = Array.isArray(fieldSx) ? fieldSx : [fieldSx];

  return (
    <Box
      sx={[
        {
          display: { xs: 'grid', sm: 'flex' },
          gridTemplateColumns: { xs: '1fr', sm: 'unset' },
          gap: 1,
          flexWrap: 'wrap',
          alignItems: 'center',
          width: { xs: '100%', sm: 'auto' },
          minWidth: 0,
        },
        ...rootSx,
      ]}
    >
      <TextField
        label={fromLabel ?? t('filters.dateFrom')}
        type="datetime-local"
        size="small"
        value={from}
        onChange={(e) => onFromChange(e.target.value)}
        slotProps={{ inputLabel: { shrink: true } }}
        sx={[
          {
            minWidth: 0,
            width: { xs: '100%', sm: 200 },
          },
          ...inputSx,
        ]}
      />
      <TextField
        label={toLabel ?? t('filters.dateTo')}
        type="datetime-local"
        size="small"
        value={to}
        onChange={(e) => onToChange(e.target.value)}
        slotProps={{ inputLabel: { shrink: true } }}
        sx={[
          {
            minWidth: 0,
            width: { xs: '100%', sm: 200 },
          },
          ...inputSx,
        ]}
      />
    </Box>
  );
}
