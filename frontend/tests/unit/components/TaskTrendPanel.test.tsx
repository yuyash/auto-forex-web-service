import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import TaskTrendPanel from '../../../src/components/tasks/detail/TaskTrendPanel';
import { TaskType } from '../../../src/types/common';
import { buildTaskTrendViewModel } from '../../fixtures/taskTrendViewModel';

const { mockUseTaskTrendViewModel } = vi.hoisted(() => ({
  mockUseTaskTrendViewModel: vi.fn(),
}));

vi.mock(
  '../../../src/components/tasks/detail/taskTrendPanel/useTaskTrendViewModel',
  () => ({
    useTaskTrendViewModel: mockUseTaskTrendViewModel,
  })
);

vi.mock('../../../src/contexts/AuthContext', () => ({
  useAuth: () => ({ user: { timezone: 'UTC' } }),
}));

vi.mock('@mui/material/styles', async () => {
  const actual = await vi.importActual('@mui/material/styles');
  return {
    ...actual,
    useTheme: () => ({ palette: { mode: 'light' } }),
  };
});

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock(
  '../../../src/components/tasks/detail/taskTrendPanel/TaskTrendAlerts',
  () => ({
    TaskTrendAlerts: () => <div>trend-alerts</div>,
  })
);

vi.mock(
  '../../../src/components/tasks/detail/taskTrendPanel/TaskTrendToolbar',
  () => ({
    TaskTrendToolbar: () => <div>trend-toolbar</div>,
  })
);

vi.mock(
  '../../../src/components/tasks/detail/taskTrendPanel/TaskTrendChartSection',
  () => ({
    TaskTrendChartSection: () => <div>trend-chart</div>,
  })
);

vi.mock(
  '../../../src/components/tasks/detail/taskTrendPanel/TaskTrendTablesSection',
  () => ({
    TaskTrendTablesSection: () => <div>trend-tables</div>,
  })
);

describe('TaskTrendPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders child sections from the shared view-model fixture', () => {
    mockUseTaskTrendViewModel.mockReturnValue(buildTaskTrendViewModel());

    render(
      <TaskTrendPanel
        taskId="task-1"
        taskType={TaskType.BACKTEST}
        instrument="USD_JPY"
      />
    );

    expect(screen.getByText('trend-alerts')).toBeInTheDocument();
    expect(screen.getByText('trend-toolbar')).toBeInTheDocument();
    expect(screen.getByText('trend-chart')).toBeInTheDocument();
    expect(screen.getByText('trend-tables')).toBeInTheDocument();
  });

  it('renders the full layout during initial loading state', () => {
    mockUseTaskTrendViewModel.mockReturnValue(
      buildTaskTrendViewModel({
        candleState: {
          isInitialLoading: true,
          candles: [],
        },
      })
    );

    render(
      <TaskTrendPanel
        taskId="task-1"
        taskType={TaskType.TRADING}
        instrument="USD_JPY"
      />
    );

    // The full layout is always rendered; the chart section handles its own loading overlay
    expect(screen.getByText('trend-alerts')).toBeInTheDocument();
    expect(screen.getByText('trend-toolbar')).toBeInTheDocument();
    expect(screen.getByText('trend-chart')).toBeInTheDocument();
    expect(screen.getByText('trend-tables')).toBeInTheDocument();
  });
});
