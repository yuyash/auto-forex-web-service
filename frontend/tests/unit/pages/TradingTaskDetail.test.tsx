/**
 * Unit tests for TradingTaskDetail
 *
 * Tests component rendering, tab navigation, and data fetching.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { TradingTaskDetail } from '../../../src/components/trading/TradingTaskDetail';
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
  useTradingTask: vi.fn((id: string) => ({
    data: {
      id: Number(id),
      name: 'Test Trading Task',
      description: 'Test trading description',
      status: TaskStatus.RUNNING,
      config_name: 'Live Config',
      config_id: 1,
      strategy_type: 'floor',
      instrument: 'EUR_USD',
      pip_size: '0.0001',
      trading_mode: 'live',
      account_name: 'Test Account',
      sell_on_stop: false,
      start_time: '2024-01-01T00:00:00Z',
      end_time: null,
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
      latest_execution: null,
      celery_task_id: null,
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  })),
  useTradingTaskPolling: vi.fn(() => ({
    data: null,
  })),
  invalidateTradingTasksCache: vi.fn(),
}));

vi.mock('../../../src/hooks/useOverviewPnl', () => ({
  useOverviewPnl: vi.fn(() => ({
    realizedPnl: 0,
    unrealizedPnl: 0,
    totalTrades: 0,
  })),
}));

// Mock child components
vi.mock('../../../src/components/common/TaskControlButtons', () => ({
  TaskControlButtons: () => <div>Task Control Buttons</div>,
}));

vi.mock('../../../src/components/tasks/display/StatusBadge', () => ({
  StatusBadge: ({ status }: { status: string }) => <span>{status}</span>,
}));

vi.mock('../../../src/components/tasks/detail/TaskEventsTable', () => ({
  TaskEventsTable: () => <div>Events Table</div>,
}));

vi.mock('../../../src/components/tasks/detail/TaskLogsTable', () => ({
  TaskLogsTable: () => <div>Logs Table</div>,
}));

vi.mock('../../../src/components/tasks/detail/TaskPositionsTable', () => ({
  TaskPositionsTable: () => <div>Positions Table</div>,
}));

vi.mock('../../../src/components/tasks/detail/TaskReplayPanel', () => ({
  TaskReplayPanel: () => <div>Replay Panel</div>,
}));

vi.mock('../../../src/components/tasks/actions/DeleteTaskDialog', () => ({
  DeleteTaskDialog: () => null,
}));

vi.mock('../../../src/hooks/useTradingTaskMutations', () => ({
  useDeleteTradingTask: vi.fn(() => ({
    mutate: vi.fn(),
    isLoading: false,
  })),
}));

// Test wrapper
const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/trading-tasks/1']}>
        <Routes>
          <Route path="/trading-tasks/:id" element={children} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
};

describe('TradingTaskDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the task name and status', async () => {
    render(<TradingTaskDetail />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: 'Test Trading Task' })
      ).toBeInTheDocument();
      const statusElements = screen.getAllByText(TaskStatus.RUNNING);
      expect(statusElements.length).toBeGreaterThan(0);
    });
  });

  it('renders task description', async () => {
    render(<TradingTaskDetail />, { wrapper: createWrapper() });

    await waitFor(() => {
      const descElements = screen.getAllByText('Test trading description');
      expect(descElements.length).toBeGreaterThan(0);
    });
  });

  it('renders task control buttons', async () => {
    render(<TradingTaskDetail />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Task Control Buttons')).toBeInTheDocument();
    });
  });

  it('renders all tab labels', async () => {
    render(<TradingTaskDetail />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Overview')).toBeInTheDocument();
      expect(screen.getByText('Events')).toBeInTheDocument();
      expect(screen.getByText('Logs')).toBeInTheDocument();
      expect(screen.getByText('Positions')).toBeInTheDocument();
      expect(screen.getByText('Replay')).toBeInTheDocument();
    });
  });

  it('renders Overview tab content by default', async () => {
    render(<TradingTaskDetail />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Task Information')).toBeInTheDocument();
    });
  });

  it('switches to Events tab when clicked', async () => {
    render(<TradingTaskDetail />, { wrapper: createWrapper() });

    const eventsTab = screen.getByText('Events');
    fireEvent.click(eventsTab);

    await waitFor(() => {
      expect(screen.getByText('Events Table')).toBeInTheDocument();
    });
  });

  it('switches to Logs tab when clicked', async () => {
    render(<TradingTaskDetail />, { wrapper: createWrapper() });

    const logsTab = screen.getByText('Logs');
    fireEvent.click(logsTab);

    await waitFor(() => {
      expect(screen.getByText('Logs Table')).toBeInTheDocument();
    });
  });

  it('switches to Positions tab when clicked', async () => {
    render(<TradingTaskDetail />, { wrapper: createWrapper() });

    const positionsTab = screen.getByText('Positions');
    fireEvent.click(positionsTab);

    await waitFor(() => {
      expect(screen.getByText('Positions Table')).toBeInTheDocument();
    });
  });

  it('switches to Replay tab when clicked', async () => {
    render(<TradingTaskDetail />, { wrapper: createWrapper() });

    const replayTab = screen.getByText('Replay');
    fireEvent.click(replayTab);

    await waitFor(() => {
      expect(screen.getByText('Replay Panel')).toBeInTheDocument();
    });
  });

  it('renders breadcrumbs with navigation', async () => {
    render(<TradingTaskDetail />, { wrapper: createWrapper() });

    await waitFor(() => {
      const breadcrumbs = screen.getByRole('navigation');
      expect(breadcrumbs).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: 'Trading Tasks' })
      ).toBeInTheDocument();
    });
  });

  it('renders configuration and strategy info', async () => {
    render(<TradingTaskDetail />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(
        screen.getByText(/Configuration: Live Config/)
      ).toBeInTheDocument();
      expect(screen.getByText(/Strategy: floor/)).toBeInTheDocument();
    });
  });
});
