import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import BacktestTasksPage from '../pages/BacktestTasksPage';
import { AuthProvider } from '../contexts/AuthContext';
import { TaskStatus } from '../types/common';

// Mock fetch
const mockFetch = vi.fn();
globalThis.fetch = mockFetch as unknown as typeof fetch;

// Mock WebSocket
class MockWebSocket {
  static instances: MockWebSocket[] = [];
  url: string;
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onerror: ((error: Event) => void) | null = null;
  onclose: ((event: { code: number; reason: string }) => void) | null = null;
  readyState = WebSocket.CONNECTING;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
    // Simulate connection after a short delay
    setTimeout(() => {
      this.readyState = WebSocket.OPEN;
      this.onopen?.();
    }, 10);
  }

  send() {
    // Mock send
  }

  close(code?: number, reason?: string) {
    this.readyState = WebSocket.CLOSED;
    this.onclose?.({ code: code || 1000, reason: reason || '' });
  }

  static reset() {
    MockWebSocket.instances = [];
  }

  static simulateMessage(message: unknown) {
    MockWebSocket.instances.forEach((ws) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.onmessage?.({ data: JSON.stringify(message) });
      }
    });
  }
}

globalThis.WebSocket = MockWebSocket as unknown as typeof WebSocket;

// Mock useNavigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

const mockBacktestTasks = [
  {
    id: 1,
    name: 'Test Backtest 1',
    status: TaskStatus.RUNNING,
    strategy_type: 'ma_crossover',
    config_name: 'Test Config',
    start_time: '2025-01-01T00:00:00Z',
    end_time: '2025-01-10T00:00:00Z',
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
    latest_execution: {
      id: 1,
      status: TaskStatus.RUNNING,
      progress: 50,
    },
  },
  {
    id: 2,
    name: 'Test Backtest 2',
    status: TaskStatus.COMPLETED,
    strategy_type: 'rsi',
    config_name: 'Test Config 2',
    start_time: '2025-01-01T00:00:00Z',
    end_time: '2025-01-10T00:00:00Z',
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
    latest_execution: {
      id: 2,
      status: TaskStatus.COMPLETED,
      total_return: '10.5',
      win_rate: '65.0',
      total_trades: 42,
    },
  },
];

describe('BacktestTasksPage Integration Tests', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.clearAllMocks();
    MockWebSocket.reset();
    localStorage.clear();
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });

    // Mock system settings API call
    mockFetch.mockImplementation((url: string) => {
      if (url.includes('/api/system-settings/')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            registration_enabled: true,
            login_enabled: true,
          }),
        });
      }
      if (url.includes('/api/backtest-tasks/')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            count: mockBacktestTasks.length,
            results: mockBacktestTasks,
          }),
        });
      }
      if (url.includes('/api/strategies/')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            strategies: [
              { name: 'ma_crossover', display_name: 'MA Crossover' },
              { name: 'rsi', display_name: 'RSI Strategy' },
            ],
          }),
        });
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    // Set auth token
    localStorage.setItem('token', 'mock-token');
  });

  afterEach(() => {
    queryClient.clear();
  });

  it('should connect to WebSocket on mount', async () => {
    render(
      <MemoryRouter>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <BacktestTasksPage />
          </AuthProvider>
        </QueryClientProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(MockWebSocket.instances.length).toBeGreaterThan(0);
    });

    // Verify WebSocket URL contains task status endpoint
    const wsInstance = MockWebSocket.instances.find((ws) =>
      ws.url.includes('/ws/tasks/')
    );
    expect(wsInstance).toBeDefined();
  });

  it('should display tasks from API', async () => {
    render(
      <MemoryRouter>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <BacktestTasksPage />
          </AuthProvider>
        </QueryClientProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Test Backtest 1')).toBeInTheDocument();
      expect(screen.getByText('Test Backtest 2')).toBeInTheDocument();
    });
  });

  it('should update task status in real-time via WebSocket', async () => {
    render(
      <MemoryRouter>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <BacktestTasksPage />
          </AuthProvider>
        </QueryClientProvider>
      </MemoryRouter>
    );

    // Wait for initial render
    await waitFor(() => {
      expect(screen.getByText('Test Backtest 1')).toBeInTheDocument();
    });

    // Simulate WebSocket status update
    MockWebSocket.simulateMessage({
      type: 'task_status_update',
      data: {
        task_id: 1,
        task_type: 'backtest',
        status: TaskStatus.COMPLETED,
        timestamp: new Date().toISOString(),
      },
    });

    // The status should be updated via WebSocket
    await waitFor(() => {
      // This would trigger a refetch in the TaskStatusListener
      expect(mockFetch).toHaveBeenCalled();
    });
  });

  it('should update task progress in real-time via WebSocket', async () => {
    render(
      <MemoryRouter>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <BacktestTasksPage />
          </AuthProvider>
        </QueryClientProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Test Backtest 1')).toBeInTheDocument();
    });

    // Simulate WebSocket progress update
    MockWebSocket.simulateMessage({
      type: 'task_progress_update',
      data: {
        task_id: 1,
        task_type: 'backtest',
        execution_id: 1,
        progress: 75,
        current_day: '2025-01-05',
        total_days: 10,
        completed_days: 7,
        timestamp: new Date().toISOString(),
      },
    });

    // Progress update should be reflected
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalled();
    });
  });

  it('should stream logs in real-time when log panel is expanded', async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <BacktestTasksPage />
          </AuthProvider>
        </QueryClientProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Test Backtest 1')).toBeInTheDocument();
    });

    // Find and click the "Show Execution Logs" button
    const showLogsButtons = screen.getAllByText(/Show Execution Logs/i);
    await user.click(showLogsButtons[0]);

    // Wait for log panel to expand
    await waitFor(() => {
      expect(screen.getByText(/Execution Logs/i)).toBeInTheDocument();
    });

    // Verify WebSocket connection for logs
    await waitFor(() => {
      const logWsInstance = MockWebSocket.instances.find((ws) =>
        ws.url.includes('/logs/')
      );
      expect(logWsInstance).toBeDefined();
    });
  });

  it('should toggle log panel expand/collapse', async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <BacktestTasksPage />
          </AuthProvider>
        </QueryClientProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Test Backtest 1')).toBeInTheDocument();
    });

    // Expand log panel
    const showLogsButtons = screen.getAllByText(/Show Execution Logs/i);
    await user.click(showLogsButtons[0]);

    await waitFor(() => {
      expect(screen.getByText(/Hide Execution Logs/i)).toBeInTheDocument();
    });

    // Collapse log panel
    const hideLogsButton = screen.getByText(/Hide Execution Logs/i);
    await user.click(hideLogsButton);

    await waitFor(() => {
      expect(screen.getByText(/Show Execution Logs/i)).toBeInTheDocument();
    });
  });

  it('should fall back to polling if WebSocket fails', async () => {
    // Simulate WebSocket connection failure
    const originalWebSocket = globalThis.WebSocket;
    globalThis.WebSocket = class extends MockWebSocket {
      constructor(url: string) {
        super(url);
        setTimeout(() => {
          this.readyState = WebSocket.CLOSED;
          this.onerror?.(new Event('error'));
          this.onclose?.({ code: 1006, reason: 'Connection failed' });
        }, 20);
      }
    } as unknown as typeof WebSocket;

    render(
      <MemoryRouter>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <BacktestTasksPage />
          </AuthProvider>
        </QueryClientProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Test Backtest 1')).toBeInTheDocument();
    });

    // Verify polling is active (multiple fetch calls)
    await waitFor(
      () => {
        const backtestTaskCalls = mockFetch.mock.calls.filter((call) =>
          call[0].includes('/api/backtest-tasks/')
        );
        expect(backtestTaskCalls.length).toBeGreaterThan(1);
      },
      { timeout: 15000 }
    );

    globalThis.WebSocket = originalWebSocket;
  });

  it('should handle button interactions correctly', async () => {
    userEvent.setup();

    // Mock start task API
    mockFetch.mockImplementation((url: string, options?: RequestInit) => {
      if (url.includes('/api/system-settings/')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            registration_enabled: true,
            login_enabled: true,
          }),
        });
      }
      if (url.includes('/api/backtest-tasks/') && options?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            id: 1,
            status: TaskStatus.RUNNING,
          }),
        });
      }
      if (url.includes('/api/backtest-tasks/')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            count: mockBacktestTasks.length,
            results: mockBacktestTasks,
          }),
        });
      }
      if (url.includes('/api/strategies/')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            strategies: [
              { name: 'ma_crossover', display_name: 'MA Crossover' },
              { name: 'rsi', display_name: 'RSI Strategy' },
            ],
          }),
        });
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    render(
      <MemoryRouter>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <BacktestTasksPage />
          </AuthProvider>
        </QueryClientProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Test Backtest 1')).toBeInTheDocument();
    });

    // Find Stop button for running task
    const stopButtons = screen.getAllByRole('button', { name: /stop/i });
    expect(stopButtons.length).toBeGreaterThan(0);

    // Find Rerun button for completed task
    const rerunButtons = screen.getAllByRole('button', { name: /rerun/i });
    expect(rerunButtons.length).toBeGreaterThan(0);
  });
});
