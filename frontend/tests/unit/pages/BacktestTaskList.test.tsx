/**
 * Unit tests for BacktestTasksPage (BacktestTaskList)
 *
 * Tests component rendering, button state logic, and control actions.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import BacktestTasksPage from '../../../src/pages/BacktestTasksPage';
import { TaskStatus } from '../../../src/types/common';

// Mock the generated API services
vi.mock('../../../src/api/generated/services/TradingService', () => ({
  TradingService: {
    tradingBacktestTasksStartCreate: vi.fn(),
    tradingBacktestTasksStopCreate: vi.fn(),
    tradingBacktestTasksResumeCreate: vi.fn(),
    tradingBacktestTasksRestartCreate: vi.fn(),
    tradingBacktestTasksDestroy: vi.fn(),
  },
}));

// Mock hooks
vi.mock('../../../src/hooks/useBacktestTasks', () => ({
  useBacktestTasks: vi.fn(() => ({
    data: {
      results: [
        {
          id: 1,
          name: 'Test Backtest 1',
          description: 'Test description',
          status: TaskStatus.RUNNING,
          config_name: 'Test Config',
          strategy_type: 'floor',
          start_time: '2024-01-01T00:00:00Z',
          end_time: '2024-01-02T00:00:00Z',
          created_at: '2024-01-01T00:00:00Z',
          updated_at: '2024-01-01T00:00:00Z',
          latest_execution: null,
        },
        {
          id: 2,
          name: 'Test Backtest 2',
          description: 'Test description 2',
          status: TaskStatus.COMPLETED,
          config_name: 'Test Config 2',
          strategy_type: 'floor',
          start_time: '2024-01-01T00:00:00Z',
          end_time: '2024-01-02T00:00:00Z',
          created_at: '2024-01-01T00:00:00Z',
          updated_at: '2024-01-01T00:00:00Z',
          latest_execution: {
            total_return: '10.5',
            win_rate: '65.0',
            total_trades: 25,
          },
        },
      ],
      count: 2,
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  })),
}));

vi.mock('../../../src/hooks/useStrategies', () => ({
  useStrategies: vi.fn(() => ({
    strategies: [
      { id: 'floor', name: 'Floor Strategy', description: 'Test strategy' },
    ],
  })),
  getStrategyDisplayName: vi.fn((strategies, type) => {
    const strategy = strategies?.find((s: { id: string }) => s.id === type);
    return strategy?.name || type;
  }),
}));

vi.mock('../../../src/hooks/useTaskPolling', () => ({
  useTaskPolling: vi.fn(() => ({
    status: null,
  })),
}));

vi.mock('../../../src/components/common', () => ({
  LoadingSpinner: () => <div>Loading...</div>,
  Breadcrumbs: () => <div>Breadcrumbs</div>,
  useToast: () => ({
    showError: vi.fn(),
    showSuccess: vi.fn(),
  }),
}));

vi.mock('../../../src/components/common/TaskControlButtons', () => ({
  TaskControlButtons: () => <div>Task Control Buttons</div>,
}));

vi.mock('../../../src/components/backtest/BacktestTaskActions', () => ({
  default: () => <div>Backtest Task Actions</div>,
}));

vi.mock('../../../src/components/tasks/display/StatusBadge', () => ({
  StatusBadge: ({ status }: { status: string }) => <div>{status}</div>,
}));

vi.mock('../../../src/components/tasks/TaskProgress', () => ({
  TaskProgress: () => <div>Task Progress</div>,
}));

vi.mock('../../../src/components/tasks/display/MetricCard', () => ({
  MetricCard: ({ title, value }: { title: string; value: string }) => (
    <div>
      {title}: {value}
    </div>
  ),
}));

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>{children}</BrowserRouter>
    </QueryClientProvider>
  );
};

describe('BacktestTasksPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the page title', async () => {
    render(<BacktestTasksPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Backtest Tasks')).toBeInTheDocument();
    });
  });

  it('renders task cards for each task', async () => {
    render(<BacktestTasksPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Test Backtest 1')).toBeInTheDocument();
      expect(screen.getByText('Test Backtest 2')).toBeInTheDocument();
    });
  });

  it('displays task status badges', async () => {
    render(<BacktestTasksPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      // Status badges should be rendered
      const runningBadges = screen.getAllByText(/running/i);
      const completedBadges = screen.getAllByText(/completed/i);
      expect(runningBadges.length).toBeGreaterThan(0);
      expect(completedBadges.length).toBeGreaterThan(0);
    });
  });

  it('displays configuration names', async () => {
    render(<BacktestTasksPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Test Config')).toBeInTheDocument();
      expect(screen.getByText('Test Config 2')).toBeInTheDocument();
    });
  });

  it('displays metrics for completed tasks', async () => {
    render(<BacktestTasksPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText(/10\.5%/)).toBeInTheDocument();
      expect(screen.getByText(/65\.0%/)).toBeInTheDocument();
      expect(screen.getByText(/25/)).toBeInTheDocument();
    });
  });

  it('renders tabs for filtering tasks', async () => {
    render(<BacktestTasksPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('All')).toBeInTheDocument();
      expect(screen.getByText('Running')).toBeInTheDocument();
      expect(screen.getByText('Completed')).toBeInTheDocument();
      expect(screen.getByText('Failed')).toBeInTheDocument();
    });
  });

  it('renders search and filter controls', async () => {
    render(<BacktestTasksPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(
        screen.getByPlaceholderText('Search tasks...')
      ).toBeInTheDocument();
      const sortByElements = screen.getAllByText('Sort By');
      expect(sortByElements.length).toBeGreaterThan(0);
    });
  });

  it('renders action buttons', async () => {
    render(<BacktestTasksPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Refresh')).toBeInTheDocument();
      expect(screen.getByText('Manage Configurations')).toBeInTheDocument();
      expect(screen.getByText('New Task')).toBeInTheDocument();
    });
  });

  it('displays empty state when no tasks', async () => {
    const { useBacktestTasks } = await import(
      '../../../src/hooks/useBacktestTasks'
    );
    vi.mocked(useBacktestTasks).mockReturnValue({
      data: { results: [], count: 0 },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as never);

    render(<BacktestTasksPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('No backtest tasks found')).toBeInTheDocument();
      expect(
        screen.getByText('Create your first backtest task to get started')
      ).toBeInTheDocument();
    });
  });

  it('displays loading state', async () => {
    const { useBacktestTasks } = await import(
      '../../../src/hooks/useBacktestTasks'
    );
    vi.mocked(useBacktestTasks).mockReturnValue({
      data: null,
      isLoading: true,
      error: null,
      refetch: vi.fn(),
    } as never);

    render(<BacktestTasksPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Loading...')).toBeInTheDocument();
    });
  });

  it('displays error state', async () => {
    const { useBacktestTasks } = await import(
      '../../../src/hooks/useBacktestTasks'
    );
    vi.mocked(useBacktestTasks).mockReturnValue({
      data: null,
      isLoading: false,
      error: new Error('Failed to load tasks'),
      refetch: vi.fn(),
    } as never);

    render(<BacktestTasksPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(
        screen.getByText(/Error loading tasks: Failed to load tasks/i)
      ).toBeInTheDocument();
    });
  });
});
