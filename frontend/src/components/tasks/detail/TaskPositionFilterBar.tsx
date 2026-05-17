import React from 'react';
import {
  IconButton,
  InputAdornment,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
} from '@mui/material';
import { Search as SearchIcon, Clear as ClearIcon } from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import type { InitialPositionFilter } from '../../../hooks/useTaskPositions';
import { DateRangeFilter } from '../../common/DateRangeFilter';
import { TableFilterBar } from '../../common/TableFilterBar';
import {
  tableFilterDateRangeSx,
  tableFilterFieldSx,
} from '../../common/tableFilterLayout';

interface TaskPositionFilterBarProps {
  cycleIdFilter: string;
  onCycleIdFilterChange: (value: string) => void;
  hasCycleIdFilter: boolean;
  isCycleIdFilterValid: boolean;
  positionIdFilter: string;
  onPositionIdFilterChange: (value: string) => void;
  hasPositionIdFilter: boolean;
  isPositionIdFilterValid: boolean;
  initialPositionFilter: InitialPositionFilter;
  onInitialPositionFilterChange: (value: InitialPositionFilter) => void;
  dateFrom?: string;
  dateTo?: string;
  onDateFromChange?: (value: string) => void;
  onDateToChange?: (value: string) => void;
}

export const TaskPositionFilterBar: React.FC<TaskPositionFilterBarProps> = ({
  cycleIdFilter,
  onCycleIdFilterChange,
  hasCycleIdFilter,
  isCycleIdFilterValid,
  positionIdFilter,
  onPositionIdFilterChange,
  hasPositionIdFilter,
  isPositionIdFilterValid,
  initialPositionFilter,
  onInitialPositionFilterChange,
  dateFrom,
  dateTo,
  onDateFromChange,
  onDateToChange,
}) => {
  const { t } = useTranslation('common');
  const showDateRange =
    dateFrom !== undefined &&
    dateTo !== undefined &&
    onDateFromChange !== undefined &&
    onDateToChange !== undefined;

  return (
    <TableFilterBar>
      <TextField
        size="small"
        placeholder={t('tables.positions.cycleIdFilter')}
        value={cycleIdFilter}
        onChange={(e) => onCycleIdFilterChange(e.target.value)}
        error={hasCycleIdFilter && !isCycleIdFilterValid}
        helperText={
          hasCycleIdFilter && !isCycleIdFilterValid
            ? t('tables.positions.invalidCycleId')
            : undefined
        }
        sx={tableFilterFieldSx}
        slotProps={{
          input: {
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon fontSize="small" />
              </InputAdornment>
            ),
            endAdornment: cycleIdFilter ? (
              <InputAdornment position="end">
                <IconButton
                  size="small"
                  onClick={() => onCycleIdFilterChange('')}
                  edge="end"
                >
                  <ClearIcon fontSize="small" />
                </IconButton>
              </InputAdornment>
            ) : null,
          },
        }}
      />
      <TextField
        size="small"
        placeholder={t('tables.positions.positionIdFilter')}
        value={positionIdFilter}
        onChange={(e) => onPositionIdFilterChange(e.target.value)}
        error={hasPositionIdFilter && !isPositionIdFilterValid}
        helperText={
          hasPositionIdFilter && !isPositionIdFilterValid
            ? t('tables.positions.invalidPositionId')
            : undefined
        }
        sx={tableFilterFieldSx}
        slotProps={{
          input: {
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon fontSize="small" />
              </InputAdornment>
            ),
            endAdornment: positionIdFilter ? (
              <InputAdornment position="end">
                <IconButton
                  size="small"
                  onClick={() => onPositionIdFilterChange('')}
                  edge="end"
                >
                  <ClearIcon fontSize="small" />
                </IconButton>
              </InputAdornment>
            ) : null,
          },
        }}
      />
      <ToggleButtonGroup
        size="small"
        exclusive
        value={initialPositionFilter}
        onChange={(_, value: InitialPositionFilter | null) => {
          if (value) onInitialPositionFilterChange(value);
        }}
        aria-label={t('tables.positions.initialPositionFilter.label')}
        sx={{
          flex: { xs: '1 1 100%', sm: '0 0 auto' },
          '& .MuiToggleButton-root': {
            px: 1.25,
            whiteSpace: 'nowrap',
          },
        }}
      >
        <ToggleButton value="all">
          {t('tables.positions.initialPositionFilter.all')}
        </ToggleButton>
        <ToggleButton value="initial">
          {t('tables.positions.initialPositionFilter.initial')}
        </ToggleButton>
        <ToggleButton value="normal">
          {t('tables.positions.initialPositionFilter.normal')}
        </ToggleButton>
      </ToggleButtonGroup>
      {showDateRange && (
        <DateRangeFilter
          from={dateFrom}
          to={dateTo}
          onFromChange={onDateFromChange}
          onToChange={onDateToChange}
          sx={tableFilterDateRangeSx}
        />
      )}
    </TableFilterBar>
  );
};
