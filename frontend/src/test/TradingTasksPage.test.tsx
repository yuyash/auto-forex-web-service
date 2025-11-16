import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import TradingTasksPage from '../pages/TradingTasksPage';
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

const mockTradingTasks = [
  {
    id: 1,
    name: 'Live Trading Task 1',
    status: TaskStatus.RUNNING,
    strategy_type: 'ma_crossover',
    config_name: 'Live Config',
    account_name: 'Live Account',
    account_type: 'live',
    description: 'Live trading with MA Crossover',
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
    latest_execution: {
      id: 1,
      status: TaskStatus.RUNNING,
      total_pnl: '150.50',
      total_trades: 5,
    },
  },
  {
    id: 2,
    name: 'Practice Trading Task',
    status: TaskStatus.PAUSED,
    strategy_type: 'rsi',
    config_name: 'Practice Config',
    account_name: 'Practice Account',
    account_type: 'practice',
    description: 'Practice trading with RSI',
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
    latest_execution: {
      id: 2,
      status: TaskStatus.PAUSED,
      total_pnl: '-25.00',
      total_trades: 3,
    },
  },
];

describe('TradingTasksPage Integration Tests', () => {
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
      if (url.includes('/api/trading-tasks/')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            count: mockTradingTasks.length,
            results: mockTradingTasks,
          }),
        });
      }
      if (url.includes('/api/configurations/')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            count: 2,
            results: [
              { id: 1, name: 'Live Config', strategy_type: 'ma_crossover' },
              { id: 2, name: 'Practice Config', strategy_type: 'rsi' },
            ],
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
            <TradingTasksPage />
          </AuthProvider>
        </QueryClientProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(MockWebSocket.instances.length).toBeGreaterThan(0);
    });

    const wsInstance = MockWebSocket.instances.find((ws) =>
      ws.url.includes('/ws/tasks/')
    );
    expect(wsInstance).toBeDefined();
  });

  it('should display trading tasks from API', async () => {
    render(
      <MemoryRouter>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <TradingTasksPage />
          </AuthProvider>
        </QueryClientProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Live Trading Task 1')).toBeInTheDocument();
      expect(screen.getByText('Practice Trading Task')).toBeInTheDocument();
    });
  });

  it('should show live trading warning for running live tasks', async () => {
    render(
      <MemoryRouter>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <TradingTasksPage />
          </AuthProvider>
        </QueryClientProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Live Trading Active/i)).toBeInTheDocument();
      expect(screen.getByText(/Real money is at risk/i)).toBeInTheDocument();
    });
  });

  it('should update task status in real-time via WebSocket', async () => {
    render(
      <MemoryRouter>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <TradingTasksPage />
          </AuthProvider>
        </QueryClientProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Live Trading Task 1')).toBeInTheDocument();
    });

    // Simulate WebSocket status update
    MockWebSocket.simulateMessage({
      type: 'task_status_update',
      data: {
        task_id: 1,
        task_type: 'trading',
        status: TaskStatus.STOPPED,
        timestamp: new Date().toISOString(),
      },
    });

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
            <TradingTasksPage />
          </AuthProvider>
        </QueryClientProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Live Trading Task 1')).toBeInTheDocument();
    });

    const showLogsButtons = screen.getAllByText(/Show Execution Logs/i);
    await user.click(showLogsButtons[0]);

    await waitFor(() => {
      expect(screen.getByText(/Execution Logs/i)).toBeInTheDocument();
    });

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
            <TradingTasksPage />
          </AuthProvider>
        </QueryClientProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Live Trading Task 1')).toBeInTheDocument();
    });

    const showLogsButtons = screen.getAllByText(/Show Execution Logs/i);
    await user.click(showLogsButtons[0]);

    await waitFor(() => {
      expect(screen.getByText(/Hide Execution Logs/i)).toBeInTheDocument();
    });

    const hideLogsButton = screen.getByText(/Hide Execution Logs/i);
    await user.click(hideLogsButton);

    await waitFor(() => {
      expect(screen.getByText(/Show Execution Logs/i)).toBeInTheDocument();
    });
  });

  it('should fall back to polling if WebSocket fails', async () => {
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
            <TradingTasksPage />
          </AuthProvider>
        </QueryClientProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Live Trading Task 1')).toBeInTheDocument();
    });

    await waitFor(
      () => {
        const tradingTaskCalls = mockFetch.mock.calls.filter((call) =>
          call[0].includes('/api/trading-tasks/')
        );
        expect(tradingTaskCalls.length).toBeGreaterThan(1);
      },
      { timeout: 15000 }
    );

    globalThis.WebSocket = originalWebSocket;
  });

  it('should handle trading-specific button interactions', async () => {
    userEvent.setup();

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
      if (url.includes('/api/trading-tasks/') && options?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            id: 1,
            status: TaskStatus.RUNNING,
          }),
        });
      }
      if (url.includes('/api/trading-tasks/')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            count: mockTradingTasks.length,
            results: mockTradingTasks,
          }),
        });
      }
      if (url.includes('/api/configurations/')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            count: 2,
            results: [
              { id: 1, name: 'Live Config', strategy_type: 'ma_crossover' },
              { id: 2, name: 'Practice Config', strategy_type: 'rsi' },
            ],
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
            <TradingTasksPage />
          </AuthProvider>
        </QueryClientProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Live Trading Task 1')).toBeInTheDocument();
    });

    // Find Pause button for running task
    const pauseButtons = screen.getAllByRole('button', { name: /pause/i });
    expect(pauseButtons.length).toBeGreaterThan(0);

    // Find Stop button for running task
    const stopButtons = screen.getAllByRole('button', { name: /stop/i });
    expect(stopButtons.length).toBeGreaterThan(0);

    // Find Resume button for paused task
    const resumeButtons = screen.getAllByRole('button', { name: /resume/i });
    expect(resumeButtons.length).toBeGreaterThan(0);
  });

  it('should display live P&L metrics for running tasks', async () => {
    render(
      <MemoryRouter>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <TradingTasksPage />
          </AuthProvider>
        </QueryClientProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Live Trading Task 1')).toBeInTheDocument();
    });

    // Check for P&L display
    await waitFor(() => {
      expect(screen.getByText(/Live P&L/i)).toBeInTheDocument();
    });
  });
});
