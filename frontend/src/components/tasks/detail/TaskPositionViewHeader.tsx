import type React from 'react';
import {
  Box,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import { useTranslation } from 'react-i18next';
import type { PositionViewMode } from './useTaskPositionViewMode';

interface TaskPositionViewHeaderProps {
  viewMode: PositionViewMode;
  onViewModeChange: (
    event: React.MouseEvent<HTMLElement>,
    nextMode: PositionViewMode | null
  ) => void;
  totalPnl: number;
  formattedTotalPnl: string;
}

export function TaskPositionViewHeader({
  viewMode,
  onViewModeChange,
  totalPnl,
  formattedTotalPnl,
}: TaskPositionViewHeaderProps) {
  const { t } = useTranslation('common');

  return (
    <Box
      sx={{
        mb: 3,
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: 1,
      }}
    >
      <ToggleButtonGroup
        value={viewMode}
        exclusive
        onChange={onViewModeChange}
        size="small"
      >
        <ToggleButton value="all">
          {t('tables.positions.viewMode.all')}
        </ToggleButton>
        <ToggleButton value="byDirection">
          {t('tables.positions.viewMode.byDirection')}
        </ToggleButton>
        <ToggleButton value="byStatus">
          {t('tables.positions.viewMode.byStatus')}
        </ToggleButton>
      </ToggleButtonGroup>
      {viewMode !== 'byStatus' && (
        <Typography
          variant="subtitle1"
          fontWeight="bold"
          color={totalPnl >= 0 ? 'success.main' : 'error.main'}
        >
          {t('tables.positions.totalPnl')}: {formattedTotalPnl}
        </Typography>
      )}
    </Box>
  );
}
