import { renderHook, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import { useTaskLogComponents } from '../../../src/hooks/useTaskLogComponents';
import { TaskType } from '../../../src/types/common';
import * as taskResourcesApi from '../../../src/services/api/taskResources';
import { createQueryHookWrapper } from '../../utils/queryHookTestUtils';

vi.mock('../../../src/services/api/taskResources', () => ({
  fetchTaskResourceObject: vi.fn(),
  isApiErrorWithStatus: vi.fn(() => false),
}));

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
      { wrapper: createQueryHookWrapper().wrapper }
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
      { wrapper: createQueryHookWrapper().wrapper }
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.components).toEqual([]);
    expect(result.current.data).toEqual([]);
  });
});
