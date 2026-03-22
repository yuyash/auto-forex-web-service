import { queryClient, queryKeys } from '../config/reactQuery';
import { TaskType } from '../types/common';

export function getTaskExecutionsKey(
  taskId: string,
  taskType: TaskType,
  params?: { page?: number; page_size?: number; include_metrics?: boolean }
) {
  return taskType === TaskType.BACKTEST
    ? queryKeys.backtestTasks.executions(taskId, params)
    : queryKeys.tradingTasks.executions(taskId, params);
}

export function getTaskExecutionKey(
  taskId: string,
  executionId: string,
  taskType: TaskType
) {
  return taskType === TaskType.BACKTEST
    ? queryKeys.backtestTasks.execution(taskId, executionId)
    : queryKeys.tradingTasks.execution(taskId, executionId);
}

export function refreshTaskExecutions(
  taskId: string,
  taskType: TaskType,
  params?: { page?: number; page_size?: number; include_metrics?: boolean }
) {
  return queryClient.invalidateQueries({
    queryKey: getTaskExecutionsKey(taskId, taskType, params),
  });
}

export function refreshTaskExecution(
  taskId: string,
  executionId: string,
  taskType: TaskType
) {
  return queryClient.invalidateQueries({
    queryKey: getTaskExecutionKey(taskId, executionId, taskType),
  });
}

export function refreshTaskSummary(
  taskId: string,
  taskType: TaskType,
  executionRunId?: string
) {
  return queryClient.invalidateQueries({
    queryKey: queryKeys.taskResources.summary(taskType, taskId, executionRunId),
  });
}

export function refreshTaskStrategyEvents(
  taskId: string,
  taskType: TaskType,
  executionRunId?: string
) {
  return queryClient.invalidateQueries({
    queryKey: queryKeys.taskResources.strategyEvents(
      taskType,
      taskId,
      executionRunId
    ),
  });
}

export async function invalidateTaskDerivedResources(
  taskId: string,
  taskType: TaskType
): Promise<void> {
  await Promise.all([
    refreshTaskExecutions(taskId, taskType),
    refreshTaskSummary(taskId, taskType),
    refreshTaskStrategyEvents(taskId, taskType),
  ]);
}

export function invalidateTaskDerivedByKind(
  taskId: string,
  taskKind: 'backtest' | 'trading'
): Promise<void> {
  return invalidateTaskDerivedResources(
    taskId,
    taskKind === 'backtest' ? TaskType.BACKTEST : TaskType.TRADING
  );
}
