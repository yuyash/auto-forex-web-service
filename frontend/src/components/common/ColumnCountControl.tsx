import { useId } from 'react';
import {
  Box,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
  useMediaQuery,
} from '@mui/material';
import { useTheme } from '@mui/material/styles';
import ViewColumnIcon from '@mui/icons-material/ViewColumn';
import { useTranslation } from 'react-i18next';
import {
  GRID_COLUMN_COUNTS,
  normalizeGridColumnCount,
  type GridColumnCount,
} from '../../utils/gridColumns';

type VisibilityBreakpoint = 'xs' | 'sm' | 'md' | 'lg' | 'xl';

interface ColumnCountControlProps {
  value: GridColumnCount;
  onChange: (value: GridColumnCount) => void;
  label?: string;
  fullWidth?: boolean;
  visibleFrom?: VisibilityBreakpoint;
}

export function ColumnCountControl({
  value,
  onChange,
  label,
  fullWidth = false,
  visibleFrom = 'lg',
}: ColumnCountControlProps) {
  const { t } = useTranslation('common');
  const theme = useTheme();
  const matchesMd = useMediaQuery(theme.breakpoints.up('md'));
  const matchesLg = useMediaQuery(theme.breakpoints.up('lg'));
  const matchesXl = useMediaQuery(theme.breakpoints.up('xl'));
  const labelId = useId();
  const resolvedLabel = label ?? t('labels.columns');
  const maxSelectableColumns: GridColumnCount = matchesXl
    ? 4
    : matchesLg
      ? 3
      : matchesMd
        ? 2
        : 1;
  const effectiveColumnCount =
    value > maxSelectableColumns ? maxSelectableColumns : value;
  const display =
    maxSelectableColumns <= 1
      ? 'none'
      : visibleFrom === 'xs'
        ? 'flex'
        : { xs: 'none', [visibleFrom]: 'flex' };

  return (
    <Box
      sx={{
        display,
        alignItems: 'center',
        gap: 0.75,
        flexWrap: 'nowrap',
        minWidth: 0,
        width: fullWidth ? '100%' : 'auto',
        overflowX: 'auto',
      }}
    >
      <Typography
        id={labelId}
        variant="caption"
        color="text.secondary"
        sx={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 0.35,
          flexShrink: 0,
          fontWeight: 600,
          whiteSpace: 'nowrap',
        }}
      >
        <ViewColumnIcon sx={{ fontSize: 16 }} />
        {resolvedLabel}
      </Typography>
      <ToggleButtonGroup
        exclusive
        size="small"
        value={effectiveColumnCount}
        aria-labelledby={labelId}
        onChange={(_, nextValue) => {
          const nextColumnCount = normalizeGridColumnCount(
            nextValue,
            effectiveColumnCount
          );
          if (nextValue !== null && nextColumnCount <= maxSelectableColumns) {
            onChange(nextColumnCount);
          }
        }}
        sx={{
          flex: '1 1 136px',
          display: 'flex',
          minWidth: 112,
          maxWidth: 160,
          '& .MuiToggleButtonGroup-grouped': {
            flex: '1 1 0',
            minWidth: 0,
            px: 0,
            py: 0.25,
            lineHeight: 1.25,
          },
        }}
      >
        {GRID_COLUMN_COUNTS.map((count) => (
          <Tooltip
            key={count}
            title={t('labels.columnCount', { count })}
            enterDelay={400}
          >
            <ToggleButton
              value={count}
              disabled={count > maxSelectableColumns}
              aria-label={t('labels.columnCount', { count })}
            >
              {count}
            </ToggleButton>
          </Tooltip>
        ))}
      </ToggleButtonGroup>
    </Box>
  );
}
