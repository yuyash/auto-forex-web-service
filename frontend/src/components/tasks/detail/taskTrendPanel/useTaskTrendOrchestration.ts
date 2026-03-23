import type { TaskSummary } from '../../../../hooks/useTaskSummary';
import { TaskType } from '../../../../types/common';
import { useTaskTrendChartModel } from './useTaskTrendChartModel';
import { useTaskTrendTableModel } from './useTaskTrendTableModel';

export interface TaskTrendOrchestrationParams {
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
  timezone: string;
  isDark: boolean;
  t: (key: string, options?: Record<string, unknown>) => string;
}

export function useTaskTrendOrchestration({
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
  timezone,
  isDark,
  t,
}: TaskTrendOrchestrationParams) {
  const chartModel = useTaskTrendChartModel({
    taskId,
    taskType,
    executionRunId,
    instrument,
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
  const tableModel = useTaskTrendTableModel({
    trades: chartModel.replayData.trades,
    allPositions: chartModel.derivedData.allPositions,
    longPositions: chartModel.derivedData.longPositions,
    shortPositions: chartModel.derivedData.shortPositions,
    currentPrice: chartModel.derivedData.currentPrice,
    pipSize,
    timezone,
    panelState: chartModel.panelState,
    chartState: chartModel.chartState,
  });

  return {
    ...chartModel,
    ...tableModel,
  };
}
