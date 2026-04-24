import React from 'react';
import { Box, IconButton, InputAdornment, TextField } from '@mui/material';
import { Search as SearchIcon, Clear as ClearIcon } from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import { DateRangeFilter } from '../../common/DateRangeFilter';

interface TaskPositionFilterBarProps {
  cycleIdFilter: string;
  onCycleIdFilterChange: (value: string) => void;
  hasCycleIdFilter: boolean;
  isCycleIdFilterValid: boolean;
  positionIdFilter: string;
  onPositionIdFilterChange: (value: string) => void;
  hasPositionIdFilter: boolean;
  isPositionIdFilterValid: boolean;
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
    <Box
      sx={{
        mb: 2,
        display: 'flex',
        gap: 1,
        flexWrap: 'wrap',
        alignItems: 'center',
      }}
    >
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
        sx={{ width: 280 }}
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
        sx={{ width: 280 }}
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
      {showDateRange && (
        <DateRangeFilter
          from={dateFrom}
          to={dateTo}
          onFromChange={onDateFromChange}
          onToChange={onDateToChange}
        />
      )}
    </Box>
  );
};
