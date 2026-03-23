import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { vi } from 'vitest';
import { useTaskLogComponents } from '../../../src/hooks/useTaskLogComponents';
import { TaskType } from '../../../src/types/common';
import * as taskResourcesApi from '../../../src/services/api/taskResources';

vi.mock('../../../src/services/api/taskResources', () => ({
  fetchTaskResourceObject: vi.fn(),
  isApiErrorWithStatus: vi.fn(() => false),
}));

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe('useTaskLogComponents', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('maps component response into the shared query state shape', async () => {
    vi.mocked(taskResourcesApi.fetchTaskResourceObject).mockResolvedValueOnce({
      components: ['executor', 'strategy'],
    });

    const { result } = renderHook(
      () =>
        useTaskLogComponents({
          taskId: 'task-1',
          taskType: TaskType.TRADING,
          executionRunId: 'exec-1',
        }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.components).toEqual(['executor', 'strategy']);
    expect(result.current.data).toEqual(['executor', 'strategy']);
    expect(result.current.error).toBeNull();
  });

  it('falls back to an empty component list when the response omits components', async () => {
    vi.mocked(taskResourcesApi.fetchTaskResourceObject).mockResolvedValueOnce(
      {}
    );

    const { result } = renderHook(
      () =>
        useTaskLogComponents({
          taskId: 'task-1',
          taskType: TaskType.BACKTEST,
        }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.components).toEqual([]);
    expect(result.current.data).toEqual([]);
  });
});
