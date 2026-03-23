/**
 * useTaskControls — unified hook that wires up task lifecycle mutations
 * and returns ready-to-use callbacks for TaskControlButtons.
 *
 * Eliminates the repeated pattern of instantiating 5-6 individual mutation
 * hooks in every BacktestTaskCard, BacktestTaskDetail, TradingTaskCard, and
 * TradingTaskDetail component.
 */
import { useCallback } from 'react';
import {
  useStartBacktestTask,
  useStopBacktestTask,
  usePauseBacktestTask,
  useResumeBacktestTask,
  useRerunBacktestTask,
} from './useBacktestTaskMutations';
import {
  useStartTradingTask,
  useStopTradingTask,
  usePauseTradingTask,
  useResumeTradingTask,
  useRestartTradingTask,
} from './useTradingTaskMutations';

type TaskKind = 'backtest' | 'trading';

interface TaskControlActions {
  onStart: (taskId: string) => void;
  onStop: (taskId: string) => void;
  onPause: (taskId: string) => void;
  onResume: (taskId: string) => void;
  onRestart: (taskId: string) => void;
  isLoading: boolean;
}

export function useTaskControls(kind: TaskKind): TaskControlActions {
  // Both hook sets must always be called (rules of hooks).
  const backtest = useBacktestControls();
  const trading = useTradingControls();
  return kind === 'backtest' ? backtest : trading;
}

function useBacktestControls(): TaskControlActions {
  const start = useStartBacktestTask();
  const stop = useStopBacktestTask();
  const pause = usePauseBacktestTask();
  const resume = useResumeBacktestTask();
  const restart = useRerunBacktestTask();

  const isLoading =
    start.isLoading ||
    stop.isLoading ||
    pause.isLoading ||
    resume.isLoading ||
    restart.isLoading;

  return {
    onStart: useCallback((id: string) => start.mutate(id), [start]),
    onStop: useCallback((id: string) => stop.mutate(id), [stop]),
    onPause: useCallback((id: string) => pause.mutate(id), [pause]),
    onResume: useCallback((id: string) => resume.mutate(id), [resume]),
    onRestart: useCallback((id: string) => restart.mutate(id), [restart]),
    isLoading,
  };
}

function useTradingControls(): TaskControlActions {
  const start = useStartTradingTask();
  const stop = useStopTradingTask();
  const pause = usePauseTradingTask();
  const resume = useResumeTradingTask();
  const restart = useRestartTradingTask();

  const isLoading =
    start.isLoading ||
    stop.isLoading ||
    pause.isLoading ||
    resume.isLoading ||
    restart.isLoading;

  return {
    onStart: useCallback((id: string) => start.mutate(id), [start]),
    onStop: useCallback(
      (id: string) => stop.mutate({ id, mode: 'graceful' }),
      [stop]
    ),
    onPause: useCallback((id: string) => pause.mutate(id), [pause]),
    onResume: useCallback((id: string) => resume.mutate(id), [resume]),
    onRestart: useCallback((id: string) => restart.mutate(id), [restart]),
    isLoading,
  };
}
