import { useMemo } from 'react';
import type { TaskSummary } from '../../../../hooks/useTaskSummary';
import { TaskType } from '../../../../types/common';
import { useTaskTrendChartModel } from './useTaskTrendChartModel';
import { useTaskTrendTableModel } from './useTaskTrendTableModel';
import type { ReplayTrade, TrendPosition } from './shared';

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
  // Filter trades and positions by active cycle when filter is enabled
  const activeCycleFilter = chartModel.panelState.activeCycleFilter;
  const activeCycleSets = chartModel.activeCycleSets;

  const filteredTrades = useMemo<ReplayTrade[]>(() => {
    if (activeCycleFilter === 'off') return chartModel.replayData.trades;
    const cycleIds = activeCycleSets[activeCycleFilter];
    if (cycleIds.size === 0) return [];
    return chartModel.replayData.trades.filter(
      (t) => t.cycle_id != null && cycleIds.has(t.cycle_id)
    );
  }, [activeCycleFilter, activeCycleSets, chartModel.replayData.trades]);

  // Build a set of position IDs that belong to the filtered trades
  const filteredPositionIds = useMemo<Set<string>>(() => {
    if (activeCycleFilter === 'off') return new Set();
    const ids = new Set<string>();
    for (const t of filteredTrades) {
      if (t.position_id) ids.add(t.position_id);
    }
    return ids;
  }, [activeCycleFilter, filteredTrades]);

  const filterPositions = (positions: TrendPosition[]): TrendPosition[] => {
    if (activeCycleFilter === 'off') return positions;
    return positions.filter((p) => filteredPositionIds.has(p.id));
  };

  const filteredAllPositions = useMemo(
    () => filterPositions(chartModel.derivedData.allPositions),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [
      activeCycleFilter,
      filteredPositionIds,
      chartModel.derivedData.allPositions,
    ]
  );
  const filteredLongPositions = useMemo(
    () => filterPositions(chartModel.derivedData.longPositions),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [
      activeCycleFilter,
      filteredPositionIds,
      chartModel.derivedData.longPositions,
    ]
  );
  const filteredShortPositions = useMemo(
    () => filterPositions(chartModel.derivedData.shortPositions),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [
      activeCycleFilter,
      filteredPositionIds,
      chartModel.derivedData.shortPositions,
    ]
  );

  const tableModel = useTaskTrendTableModel({
    trades: filteredTrades,
    allPositions: filteredAllPositions,
    longPositions: filteredLongPositions,
    shortPositions: filteredShortPositions,
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
