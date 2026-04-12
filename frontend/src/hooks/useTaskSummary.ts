/**
 * Hook for fetching task summary from the backend API.
 *
 * Returns comprehensive task summary grouped into logical sections:
 * - pnl: realized/unrealized PnL
 * - counts: trade/position counts
 * - execution: balance, ticks processed
 * - tick: last tick prices (bid, ask, mid) with timestamp
 * - task: status, timing, progress
 *
 * Supports optional polling for real-time updates.
 */

import { TaskType } from '../types/common';
import { refreshTaskSummary } from './taskResourceCache';
import { createTaskSummaryQuery } from './taskResourceQueries';
import { usePollingPolicy } from './usePollingPolicy';
import { usePolledTaskResource } from './useTaskCollections';

export interface TickInfo {
  timestamp: string | null;
  bid: number | null;
  ask: number | null;
  mid: number | null;
}

export interface PnlInfo {
  realized: number;
  unrealized: number;
}

export interface CountsInfo {
  totalTrades: number;
  openPositions: number;
  closedPositions: number;
  openLongUnits: number;
  openShortUnits: number;
}

export interface ExecutionInfo {
  currentBalance: number | null;
  ticksProcessed: number;
  accountCurrency: string | null;
  currentBalanceDisplay: number | null;
  displayCurrency: string | null;
  marginRatio: number | null;
  currentAtr: number | null;
}

export interface TaskInfo {
  status: string;
  startedAt: string | null;
  completedAt: string | null;
  errorMessage: string | null;
  progress: number;
}

export interface TaskSummary {
  timestamp: string | null;
  pnl: PnlInfo;
  counts: CountsInfo;
  execution: ExecutionInfo;
  tick: TickInfo;
  task: TaskInfo;
}

export interface UseTaskSummaryOptions {
  polling?: boolean;
  interval?: number;
}

export interface UseTaskSummaryResult {
  data: TaskSummary;
  summary: TaskSummary;
  isLoading: boolean;
  error: Error | null;
  refresh: () => Promise<unknown>;
}

const INITIAL_SUMMARY: TaskSummary = {
  timestamp: null,
  pnl: { realized: 0, unrealized: 0 },
  counts: {
    totalTrades: 0,
    openPositions: 0,
    closedPositions: 0,
    openLongUnits: 0,
    openShortUnits: 0,
  },
  execution: {
    currentBalance: null,
    ticksProcessed: 0,
    accountCurrency: null,
    currentBalanceDisplay: null,
    displayCurrency: null,
    marginRatio: null,
    currentAtr: null,
  },
  tick: { timestamp: null, bid: null, ask: null, mid: null },
  task: {
    status: '',
    startedAt: null,
    completedAt: null,
    errorMessage: null,
    progress: 0,
  },
};

export function useTaskSummary(
  taskId: string,
  taskType: TaskType,
  executionRunId?: string,
  options: UseTaskSummaryOptions = {}
): UseTaskSummaryResult {
  const { polling = false, interval = 10_000 } = options;
  const pollingPolicy = usePollingPolicy({
    enabled: polling && Boolean(taskId),
    baseIntervalMs: interval,
  });
  const refresh = () => refreshTaskSummary(taskId, taskType, executionRunId);
  const resource = usePolledTaskResource(
    createTaskSummaryQuery(taskId, taskType, executionRunId, INITIAL_SUMMARY),
    refresh,
    {
      pollingEnabled: pollingPolicy.isActive,
      intervalMs: pollingPolicy.intervalMs,
    }
  );

  return {
    ...resource,
    data: resource.data ?? INITIAL_SUMMARY,
    summary: resource.data ?? INITIAL_SUMMARY,
  };
}
