import type { PaginatedResponse } from '../types';
import { TaskStatus, type TaskType } from '../types/common';

interface TaskStatusTransition {
  status: TaskStatus;
  settleOn: Set<TaskStatus>;
  expiresAt: number;
}

type TaskLike = {
  id: string;
  status: TaskStatus;
};

const TRANSITION_WINDOW_MS = 30_000;
const SETTLED_TRANSITION_GRACE_MS = 5_000;
const taskStatusTransitions = new Map<string, TaskStatusTransition>();

function transitionKey(taskType: TaskType, taskId: string): string {
  return `${taskType}:${taskId}`;
}

function readTransition(
  taskType: TaskType,
  taskId: string
): TaskStatusTransition | null {
  const key = transitionKey(taskType, taskId);
  const transition = taskStatusTransitions.get(key);
  if (!transition) {
    return null;
  }
  if (transition.expiresAt <= Date.now()) {
    taskStatusTransitions.delete(key);
    return null;
  }
  return transition;
}

export function markTaskStatusTransition(
  taskType: TaskType,
  taskId: string,
  status: TaskStatus,
  settleOn: TaskStatus[] = []
): void {
  taskStatusTransitions.set(transitionKey(taskType, taskId), {
    status,
    settleOn: new Set(settleOn),
    expiresAt: Date.now() + TRANSITION_WINDOW_MS,
  });
}

export function clearTaskStatusTransition(
  taskType: TaskType,
  taskId: string
): void {
  taskStatusTransitions.delete(transitionKey(taskType, taskId));
}

export function applyTaskStatusTransition<TTask extends TaskLike>(
  taskType: TaskType,
  task: TTask
): TTask {
  const transition = readTransition(taskType, task.id);
  if (!transition) {
    return task;
  }

  if (transition.settleOn.has(task.status)) {
    transition.expiresAt = Math.min(
      transition.expiresAt,
      Date.now() + SETTLED_TRANSITION_GRACE_MS
    );
    return task;
  }

  if (task.status !== TaskStatus.CREATED) {
    return task;
  }

  return {
    ...task,
    status: transition.status,
  };
}

export function applyPaginatedTaskStatusTransitions<TTask extends TaskLike>(
  taskType: TaskType,
  data: PaginatedResponse<TTask>
): PaginatedResponse<TTask> {
  return {
    ...data,
    results: data.results.map((task) =>
      applyTaskStatusTransition(taskType, task)
    ),
  };
}
