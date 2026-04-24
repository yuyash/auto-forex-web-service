import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { TaskMetricsTab } from '../../../src/components/tasks/detail/TaskMetricsTab';
import type { MetricPoint } from '../../../src/utils/fetchMetrics';

vi.mock('@mui/x-charts/LineChart', () => ({
  LineChart: () => <div data-testid="line-chart" />,
}));

describe('TaskMetricsTab', () => {
  it('renders large metric series without overflowing the call stack', () => {
    const data: MetricPoint[] = Array.from({ length: 150_000 }, (_, index) => ({
      t: 1_700_000_000 + index * 60,
      metrics: {
        current_balance: 10_000 + index * 0.01,
      },
    }));

    render(
      <TaskMetricsTab
        data={data}
        isLoading={false}
        error={null}
        interval={1}
        since=""
        until=""
        onIntervalChange={vi.fn()}
        onSinceChange={vi.fn()}
        onUntilChange={vi.fn()}
        onRefresh={vi.fn()}
      />
    );

    expect(screen.getByTestId('line-chart')).toBeInTheDocument();
  });
});
