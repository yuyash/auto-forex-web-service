import React, { useRef } from 'react';
import { Alert, Box } from '@mui/material';
import { useTheme } from '@mui/material/styles';
import { useTranslation } from 'react-i18next';
import { type TaskSummary } from '../../../hooks/useTaskSummary';
import { useAuth } from '../../../contexts/AuthContext';
import { TaskType } from '../../../types/common';
import { POLLING_INTERVAL_OPTIONS } from './taskTrendPanel/shared';
import { TaskTrendAlerts } from './taskTrendPanel/TaskTrendAlerts';
import { TaskTrendChartSection } from './taskTrendPanel/TaskTrendChartSection';
import { TaskTrendTablesSection } from './taskTrendPanel/TaskTrendTablesSection';
import { TaskTrendToolbar } from './taskTrendPanel/TaskTrendToolbar';
import { useTaskTrendViewModel } from './taskTrendPanel/useTaskTrendViewModel';

interface TaskTrendPanelProps {
  taskId: string | number;
  taskType: TaskType;
  instrument: string;
  executionRunId?: string;
  startTime?: string;
  endTime?: string;
  enableRealTimeUpdates?: boolean;
  currentTick?: { timestamp: string; price: string | null } | null;
  latestExecution?: {
    total_trades?: number;
  };
  summary?: TaskSummary;
  pipSize?: number | null;
  configId?: string;
}

export const TaskTrendPanel: React.FC<TaskTrendPanelProps> = ({
  taskId,
  taskType,
  instrument,
  executionRunId,
  startTime,
  endTime,
  enableRealTimeUpdates = false,
  currentTick,
  latestExecution,
  summary,
  pipSize,
}) => {
  const panelRootRef = useRef<HTMLDivElement | null>(null);
  const { user } = useAuth();
  const { t } = useTranslation('common');
  const muiTheme = useTheme();
  const isDark = muiTheme.palette.mode === 'dark';
  const timezone = user?.timezone || 'UTC';

  const {
    panelState,
    candleState,
    alertsProps,
    toolbarProps,
    chartSectionProps,
    tablesSectionProps,
  } = useTaskTrendViewModel({
    taskId,
    taskType,
    instrument,
    executionRunId,
    startTime,
    endTime,
    enableRealTimeUpdates,
    currentTick,
    latestExecution,
    summary,
    pipSize,
    timezone,
    isDark,
    t,
  });

  if (panelState.candleErrorMessage && candleState.candles.length === 0) {
    return (
      <Box ref={panelRootRef} sx={{ p: 3 }}>
        <Alert severity={panelState.candleErrorSeverity}>
          {panelState.candleErrorMessage}
        </Alert>
      </Box>
    );
  }

  return (
    <Box
      ref={panelRootRef}
      sx={{ p: 2, pt: 0, pb: 2, boxSizing: 'border-box' }}
    >
      <TaskTrendAlerts {...alertsProps} />

      <TaskTrendToolbar
        {...toolbarProps}
        pollingIntervalOptions={POLLING_INTERVAL_OPTIONS}
      />

      <TaskTrendChartSection {...chartSectionProps} />

      <Box
        onMouseDown={panelState.handleSeparatorMouseDown}
        onTouchStart={panelState.handleSeparatorMouseDown}
        sx={{
          height: 8,
          cursor: 'row-resize',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          '&:hover': { '& > div': { backgroundColor: 'primary.main' } },
        }}
      >
        <Box
          sx={{
            width: 40,
            height: 3,
            borderRadius: 1.5,
            backgroundColor: 'divider',
            transition: 'background-color 0.15s',
          }}
        />
      </Box>

      <TaskTrendTablesSection {...tablesSectionProps} />
    </Box>
  );
};

export default TaskTrendPanel;
