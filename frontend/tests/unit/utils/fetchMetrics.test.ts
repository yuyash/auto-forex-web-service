import { beforeEach, describe, expect, it, vi } from 'vitest';
import { TaskType } from '../../../src/types/common';

const mockGet = vi.hoisted(() => vi.fn());

vi.mock('../../../src/api/apiClient', () => ({
  api: {
    get: mockGet,
  },
}));

import {
  fetchMetrics,
  intervalToGranularity,
} from '../../../src/utils/fetchMetrics';

describe('fetchMetrics', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGet.mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      data_source: 'strategy_metrics',
      resume_cursor_timestamp: null,
      consistency_warnings: [],
      results: [],
    });
  });

  it('converts one-minute intervals to M1 instead of raw metrics', async () => {
    await fetchMetrics({
      taskId: 'task-1',
      taskType: TaskType.BACKTEST,
      executionRunId: 'exec-1',
      interval: 1,
      metricKeys: ['total_pnl', 'margin_ratio'],
      pageSize: 500,
    });

    expect(mockGet).toHaveBeenCalledWith(
      '/api/trading/tasks/backtest/task-1/strategy/metrics/',
      expect.objectContaining({
        execution_id: 'exec-1',
        granularity: 'M1',
        metric_keys: 'total_pnl,margin_ratio',
        page_size: '500',
      })
    );
  });

  it('lets an explicit granularity override the interval', async () => {
    await fetchMetrics({
      taskId: 'task-1',
      taskType: TaskType.TRADING,
      interval: 1,
      granularity: 'raw',
    });

    expect(mockGet).toHaveBeenCalledWith(
      '/api/trading/tasks/trading/task-1/strategy/metrics/',
      expect.objectContaining({ granularity: 'raw' })
    );
  });
});

describe('intervalToGranularity', () => {
  it('returns OANDA minute tokens for positive intervals', () => {
    expect(intervalToGranularity(1)).toBe('M1');
    expect(intervalToGranularity(15)).toBe('M15');
    expect(intervalToGranularity(1440)).toBe('M1440');
  });

  it('omits non-positive intervals', () => {
    expect(intervalToGranularity(0)).toBeUndefined();
    expect(intervalToGranularity(undefined)).toBeUndefined();
  });
});
