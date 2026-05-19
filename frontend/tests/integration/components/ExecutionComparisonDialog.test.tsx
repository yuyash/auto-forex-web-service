import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ExecutionComparisonDialog } from '../../../src/components/tasks/detail/ExecutionComparisonDialog';
import { TaskStatus, TaskType } from '../../../src/types/common';
import type { TaskExecution } from '../../../src/types/execution';
import {
  fetchPaginatedMetrics,
  type MetricPoint,
  type MetricsPage,
} from '../../../src/utils/fetchMetrics';

const lineChartProps = vi.hoisted(
  () =>
    [] as Array<{
      series?: Array<{ label?: string; data?: Array<number | null> }>;
    }>
);

vi.mock('@mui/x-charts/LineChart', () => ({
  LineChart: (props: {
    series?: Array<{ label?: string; data?: Array<number | null> }>;
  }) => {
    lineChartProps.push(props);
    return <div data-testid="comparison-line-chart" />;
  },
}));

vi.mock('../../../src/hooks/useStrategies', () => ({
  useStrategies: () => ({ strategies: [], isLoading: false, error: null }),
}));

vi.mock('../../../src/hooks/useDateTimeFormatter', () => ({
  useDateTimeFormatter: () => ({
    formatDateTime: (value: Date | string | null | undefined) =>
      value == null ? '' : new Date(value).toISOString(),
    formatDate: (value: Date | string | null | undefined) =>
      value == null ? '' : new Date(value).toISOString().slice(0, 10),
  }),
}));

vi.mock('../../../src/utils/fetchMetrics', () => ({
  fetchPaginatedMetrics: vi.fn(),
}));

const mockFetchPaginatedMetrics = vi.mocked(fetchPaginatedMetrics);

function createExecution(id: string, executionNumber: number): TaskExecution {
  return {
    id,
    task_type: TaskType.BACKTEST,
    task_id: 'task-1',
    execution_number: executionNumber,
    status: TaskStatus.COMPLETED,
    progress: 100,
    started_at: '2026-01-01T00:00:00Z',
    completed_at: '2026-01-02T00:00:00Z',
    created_at: '2026-01-01T00:00:00Z',
    metrics: {},
    task_config: {
      start_time: '2026-01-01T00:00:00Z',
      end_time: '2026-01-02T00:00:00Z',
    },
    strategy_config: null,
  };
}

function metricsPage(results: MetricPoint[]): MetricsPage {
  return {
    count: results.length,
    next: null,
    previous: null,
    data_source: 'aggregate',
    resume_cursor_timestamp: null,
    consistency_warnings: [],
    results,
  };
}

describe('ExecutionComparisonDialog', () => {
  beforeEach(() => {
    lineChartProps.length = 0;
    vi.clearAllMocks();
  });

  it('renders comparison metric charts as soon as the first metrics page arrives', async () => {
    const pendingFetches: Promise<MetricsPage>[] = [];
    const resolvers: Array<(value: MetricsPage) => void> = [];

    mockFetchPaginatedMetrics.mockImplementation((opts) => {
      const firstResults: MetricPoint[] =
        opts.executionRunId === 'exec-1'
          ? [
              { t: 1_767_225_600, metrics: { current_balance: 100 } },
              { t: 1_767_225_660, metrics: { current_balance: 101 } },
            ]
          : [
              { t: 1_767_225_600, metrics: { current_balance: 200 } },
              { t: 1_767_225_660, metrics: { current_balance: 201 } },
            ];

      opts.onProgress?.({
        page: 1,
        pageResults: firstResults,
        accumulatedResults: firstResults,
        response: {
          ...metricsPage(firstResults),
          count: 4,
          next: '/next',
        },
        hasMore: true,
      });

      const pending = new Promise<MetricsPage>((resolve) => {
        resolvers.push(resolve);
      });
      pendingFetches.push(pending);
      return pending;
    });

    const user = userEvent.setup();
    render(
      <ExecutionComparisonDialog
        open
        onClose={vi.fn()}
        executions={[
          createExecution('exec-1', 1),
          createExecution('exec-2', 2),
        ]}
        taskId="task-1"
        taskType={TaskType.BACKTEST}
      />
    );

    await user.click(
      await screen.findByRole('tab', { name: /Metrics Overlay|メトリクス/i })
    );

    await waitFor(() =>
      expect(mockFetchPaginatedMetrics).toHaveBeenCalledTimes(2)
    );
    await waitFor(() =>
      expect(
        lineChartProps.some((props) =>
          props.series?.some(
            (series) => series.data?.[0] === 100 && series.data?.[1] === 101
          )
        )
      ).toBe(true)
    );
    expect(screen.getAllByRole('progressbar').length).toBeGreaterThan(0);

    await act(async () => {
      resolvers.forEach((resolve, index) => {
        const base = index === 0 ? 100 : 200;
        resolve(
          metricsPage([
            { t: 1_767_225_600, metrics: { current_balance: base } },
            { t: 1_767_225_660, metrics: { current_balance: base + 1 } },
            { t: 1_767_225_720, metrics: { current_balance: base + 2 } },
          ])
        );
      });
      await Promise.all(pendingFetches);
    });

    await waitFor(() =>
      expect(
        lineChartProps.some((props) =>
          props.series?.some((series) => series.data?.includes(102))
        )
      ).toBe(true)
    );
  });
});
