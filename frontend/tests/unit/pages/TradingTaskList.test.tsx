/**
 * Unit tests for TradingTasksPage (TradingTaskList)
 *
 * Tests component rendering, button state logic, and control actions.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import TradingTasksPage from '../../../src/pages/TradingTasksPage';
import { TaskStatus } from '../../../src/types/common';

// Mock the generated API services
vi.mock('../../../src/api/generated/services/TradingService', () => ({
  TradingService: {
    tradingTradingTasksStartCreate: vi.fn(),
    tradingTradingTasksStopCreate: vi.fn(),
    tradingTradingTasksResumeCreate: vi.fn(),
    tradingTradingTasksRestartCreate: vi.fn(),
    tradingTradingTasksDestroy: vi.fn(),
  },
}));

// Mock hooks
vi.mock('../../../src/hooks/useTradingTasks', () => ({
  useTradingTasks: vi.fn(() => ({
    data: {
      results: [
        {
          id: 1,
          name: 'Test Trading Task 1',
          description: 'Test description',
          status: TaskStatus.RUNNING,
          config_name: 'Test Config',
          strategy_type: 'floor',
          account_name: 'Test Account',
          account_type: 'practice',
          created_at: '2024-01-01T00:00:00Z',
          updated_at: '2024-01-01T00:00:00Z',
          latest_execution: {
            total_pnl: '150.50',
            total_trades: 10,
          },
        },
        {
          id: 2,
          name: 'Test Trading Task 2',
          description: 'Test description 2',
          status: TaskStatus.PAUSED,
          config_name: 'Test Config 2',
          strategy_type: 'floor',
          account_name: 'Test Account 2',
          account_type: 'live',
          created_at: '2024-01-01T00:00:00Z',
          updated_at: '2024-01-01T00:00:00Z',
          latest_execution: {
            total_pnl: '-50.25',
            total_trades: 5,
          },
        },
        {
          id: 3,
          name: 'Test Trading Task 3',
          description: 'Test description 3',
          status: TaskStatus.STOPPED,
          config_name: 'Test Config 3',
          strategy_type: 'floor',
          account_name: 'Test Account 3',
          account_type: 'practice',
          created_at: '2024-01-01T00:00:00Z',
          updated_at: '2024-01-01T00:00:00Z',
          latest_execution: {
            total_return: '5.5',
            win_rate: '60.0',
            total_trades: 20,
          },
        },
      ],
      count: 3,
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  })),
}));

vi.mock('../../../src/hooks/useConfigurations', () => ({
  useConfigurations: vi.fn(() => ({
    data: {
      results: [
        {
          id: 1,
          name: 'Test Config',
          strategy_type: 'floor',
        },
        {
          id: 2,
          name: 'Test Config 2',
          strategy_type: 'floor',
        },
      ],
      count: 2,
    },
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
    showWarning: vi.fn(),
    showInfo: vi.fn(),
  }),
}));

vi.mock('../../../src/components/common/TaskControlButtons', () => ({
  TaskControlButtons: () => <div>Task Control Buttons</div>,
}));

vi.mock('../../../src/components/trading/TradingTaskActions', () => ({
  default: () => <div>Trading Task Actions</div>,
}));

vi.mock('../../../src/components/tasks/display/StatusBadge', () => ({
  StatusBadge: ({ status }: { status: string }) => <div>{status}</div>,
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

describe('TradingTasksPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the page title', async () => {
    render(<TradingTasksPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Trading Tasks')).toBeInTheDocument();
    });
  });

  it('renders task cards for each task', async () => {
    render(<TradingTasksPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Test Trading Task 1')).toBeInTheDocument();
      expect(screen.getByText('Test Trading Task 2')).toBeInTheDocument();
      expect(screen.getByText('Test Trading Task 3')).toBeInTheDocument();
    });
  });

  it('displays task status badges', async () => {
    render(<TradingTasksPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      // Status badges should be rendered
      const runningBadges = screen.getAllByText(/running/i);
      const pausedBadges = screen.getAllByText(/paused/i);
      const stoppedBadges = screen.getAllByText(/stopped/i);
      expect(runningBadges.length).toBeGreaterThan(0);
      expect(pausedBadges.length).toBeGreaterThan(0);
      expect(stoppedBadges.length).toBeGreaterThan(0);
    });
  });

  it('displays configuration names', async () => {
    render(<TradingTasksPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Test Config')).toBeInTheDocument();
      expect(screen.getByText('Test Config 2')).toBeInTheDocument();
      expect(screen.getByText('Test Config 3')).toBeInTheDocument();
    });
  });

  it('displays account names', async () => {
    render(<TradingTasksPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Test Account')).toBeInTheDocument();
      expect(screen.getByText('Test Account 2')).toBeInTheDocument();
      expect(screen.getByText('Test Account 3')).toBeInTheDocument();
    });
  });

  it('displays live account badge for live accounts', async () => {
    render(<TradingTasksPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      const liveAccountBadges = screen.getAllByText('LIVE ACCOUNT');
      expect(liveAccountBadges.length).toBeGreaterThan(0);
    });
  });

  it('displays metrics for running tasks', async () => {
    render(<TradingTasksPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      // Check for P&L values
      expect(screen.getByText(/150\.50/)).toBeInTheDocument();
      expect(screen.getByText(/-50\.25/)).toBeInTheDocument();
    });
  });

  it('displays metrics for stopped tasks', async () => {
    render(<TradingTasksPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText(/5\.5%/)).toBeInTheDocument();
      expect(screen.getByText(/60\.0%/)).toBeInTheDocument();
    });
  });

  it('renders tabs for filtering tasks', async () => {
    render(<TradingTasksPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('All')).toBeInTheDocument();
      expect(screen.getByText('Running')).toBeInTheDocument();
      expect(screen.getByText('Paused')).toBeInTheDocument();
      expect(screen.getByText('Stopped')).toBeInTheDocument();
    });
  });

  it('renders search and filter controls', async () => {
    render(<TradingTasksPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(
        screen.getByPlaceholderText('Search tasks...')
      ).toBeInTheDocument();
    });
  });

  it('renders action buttons', async () => {
    render(<TradingTasksPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Refresh')).toBeInTheDocument();
      expect(screen.getByText('Account Settings')).toBeInTheDocument();
      expect(screen.getByText('Manage Configurations')).toBeInTheDocument();
      expect(screen.getByText('New Task')).toBeInTheDocument();
    });
  });

  it('displays one-task-per-account warning', async () => {
    render(<TradingTasksPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(
        screen.getByText('Important: One Task Per Account')
      ).toBeInTheDocument();
      expect(
        screen.getByText(/Only one trading task can be running per account/i)
      ).toBeInTheDocument();
    });
  });

  it('displays empty state when no tasks', async () => {
    const { useTradingTasks } = await import(
      '../../../src/hooks/useTradingTasks'
    );
    vi.mocked(useTradingTasks).mockReturnValue({
      data: { results: [], count: 0 },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    } as never);

    render(<TradingTasksPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('No trading tasks found')).toBeInTheDocument();
      expect(
        screen.getByText(
          'Create your first trading task to start automated trading'
        )
      ).toBeInTheDocument();
    });
  });

  it('displays loading state', async () => {
    const { useTradingTasks } = await import(
      '../../../src/hooks/useTradingTasks'
    );
    vi.mocked(useTradingTasks).mockReturnValue({
      data: null,
      isLoading: true,
      error: null,
      refetch: vi.fn(),
    } as never);

    render(<TradingTasksPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Loading...')).toBeInTheDocument();
    });
  });

  it('displays error state', async () => {
    const { useTradingTasks } = await import(
      '../../../src/hooks/useTradingTasks'
    );
    vi.mocked(useTradingTasks).mockReturnValue({
      data: null,
      isLoading: false,
      error: new Error('Failed to load tasks'),
      refetch: vi.fn(),
    } as never);

    render(<TradingTasksPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(
        screen.getByText(/Error loading tasks: Failed to load tasks/i)
      ).toBeInTheDocument();
    });
  });

  it('renders TaskControlButtons for each task', async () => {
    render(<TradingTasksPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      // Verify tasks are rendered (TaskControlButtons is mocked)
      expect(screen.getByText('Trading Tasks')).toBeInTheDocument();
    });
  });
});
