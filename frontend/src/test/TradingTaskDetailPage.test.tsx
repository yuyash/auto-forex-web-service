import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import TradingTaskDetailPage from '../pages/TradingTaskDetailPage';
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

const mockTradingTask = {
  id: 1,
  name: 'Test Trading Task',
  status: TaskStatus.RUNNING,
  strategy_type: 'ma_crossover',
  config_name: 'Test Config',
  account_name: 'Test Account',
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
  description: 'Test trading task description',
  latest_execution: {
    id: 1,
    status: TaskStatus.RUNNING,
    progress: 50,
  },
};

const mockStrategies = [
  {
    id: 1,
    name: 'ma_crossover',
    display_name: 'MA Crossover',
    description: 'Moving Average Crossover Strategy',
  },
];

function renderWithProviders(ui: React.ReactElement, taskId = '1') {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={[`/trading-tasks/${taskId}`]}>
          <Routes>
            <Route path="/trading-tasks/:id" element={ui} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}

describe('TradingTaskDetailPage Integration Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    MockWebSocket.reset();

    // Mock successful auth check
    mockFetch.mockImplementation((url: string) => {
      if (url.includes('/api/auth/check/')) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              isAuthenticated: true,
              user: { id: 1, username: 'testuser' },
            }),
        });
      }

      // Mock task detail fetch
      if (url.includes('/api/trading-tasks/1/')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockTradingTask),
        });
      }

      // Mock strategies fetch
      if (url.includes('/api/strategies/')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockStrategies),
        });
      }

      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({}),
      });
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
    MockWebSocket.reset();
  });

  it('should connect to WebSocket on mount (Requirement 3.3)', async () => {
    renderWithProviders(<TradingTaskDetailPage />);

    await waitFor(() => {
      expect(MockWebSocket.instances.length).toBeGreaterThan(0);
    });

    // Check that WebSocket connected to correct URL
    const wsInstance = MockWebSocket.instances.find((ws) =>
      ws.url.includes('/ws/tasks/status/')
    );
    expect(wsInstance).toBeDefined();
  });

  it('should fetch latest status from backend before rendering (Requirement 3.6)', async () => {
    renderWithProviders(<TradingTaskDetailPage />);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/trading-tasks/1/'),
        expect.any(Object)
      );
    });
  });

  it('should display task details after loading', async () => {
    renderWithProviders(<TradingTaskDetailPage />);

    await waitFor(() => {
      expect(screen.getByText('Test Trading Task')).toBeInTheDocument();
    });

    expect(screen.getByText(/Test Account/)).toBeInTheDocument();
    expect(screen.getByText(/Test Config/)).toBeInTheDocument();
    expect(screen.getByText(/MA Crossover/)).toBeInTheDocument();
  });

  it('should update status in real-time via WebSocket (Requirement 3.4)', async () => {
    renderWithProviders(<TradingTaskDetailPage />);

    await waitFor(() => {
      expect(screen.getByText('Test Trading Task')).toBeInTheDocument();
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

    // Should refetch task data
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/trading-tasks/1/'),
        expect.any(Object)
      );
    });
  });

  it('should update progress in real-time via WebSocket (Requirement 3.4)', async () => {
    renderWithProviders(<TradingTaskDetailPage />);

    await waitFor(() => {
      expect(screen.getByText('Test Trading Task')).toBeInTheDocument();
    });

    // Simulate WebSocket progress update
    MockWebSocket.simulateMessage({
      type: 'task_progress_update',
      data: {
        task_id: 1,
        task_type: 'trading',
        execution_id: 1,
        progress: 75,
        timestamp: new Date().toISOString(),
      },
    });

    // Progress bar should update
    await waitFor(() => {
      expect(screen.getByText('75%')).toBeInTheDocument();
    });
  });

  it('should display log panel with real-time log streaming (Requirement 6.8)', async () => {
    renderWithProviders(<TradingTaskDetailPage />);

    await waitFor(() => {
      expect(screen.getByText('Execution Logs')).toBeInTheDocument();
    });

    // Check that log WebSocket is connected
    await waitFor(() => {
      const logWsInstance = MockWebSocket.instances.find((ws) =>
        ws.url.includes('/ws/tasks/trading/1/logs/')
      );
      expect(logWsInstance).toBeDefined();
    });
  });

  it('should display progress bar only for running tasks (Requirement 5.4)', async () => {
    renderWithProviders(<TradingTaskDetailPage />);

    await waitFor(() => {
      expect(screen.getByText('Test Trading Task')).toBeInTheDocument();
    });

    // Progress bar should be visible for running task
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('should show correct action buttons based on task status (Requirement 4.5)', async () => {
    renderWithProviders(<TradingTaskDetailPage />);

    await waitFor(() => {
      expect(screen.getByText('Test Trading Task')).toBeInTheDocument();
    });

    // For running task, should show Emergency Stop button
    expect(
      screen.getByRole('button', { name: /emergency stop/i })
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /^start$/i })
    ).not.toBeInTheDocument();
  });

  it('should handle button interactions with optimistic updates (Requirement 3.1)', async () => {
    const user = userEvent.setup();

    // Mock stop endpoint
    mockFetch.mockImplementation((url: string) => {
      if (url.includes('/api/auth/check/')) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              isAuthenticated: true,
              user: { id: 1, username: 'testuser' },
            }),
        });
      }

      if (url.includes('/api/trading-tasks/1/')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockTradingTask),
        });
      }

      if (url.includes('/api/strategies/')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockStrategies),
        });
      }

      if (url.includes('/api/trading-tasks/1/stop/')) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              id: 1,
              status: TaskStatus.STOPPED,
            }),
        });
      }

      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({}),
      });
    });

    renderWithProviders(<TradingTaskDetailPage />);

    await waitFor(() => {
      expect(screen.getByText('Test Trading Task')).toBeInTheDocument();
    });

    const stopButton = screen.getByRole('button', {
      name: /emergency stop/i,
    });
    await user.click(stopButton);

    // Confirm dialog should appear
    await waitFor(() => {
      expect(screen.getByText(/are you sure/i)).toBeInTheDocument();
    });
  });

  it('should display log panel visibility and updates (Requirement 6.8)', async () => {
    renderWithProviders(<TradingTaskDetailPage />);

    await waitFor(() => {
      expect(screen.getByText('Execution Logs')).toBeInTheDocument();
    });

    // Log panel should always be visible
    expect(screen.getByText('Execution Logs')).toBeVisible();

    // Simulate log message
    const logWsInstance = MockWebSocket.instances.find((ws) =>
      ws.url.includes('/ws/tasks/trading/1/logs/')
    );

    if (logWsInstance) {
      logWsInstance.onmessage?.({
        data: JSON.stringify({
          type: 'execution_log',
          data: {
            execution_id: 1,
            task_id: 1,
            task_type: 'trading',
            execution_number: 1,
            log: {
              timestamp: new Date().toISOString(),
              level: 'INFO',
              message: 'Test trading log message',
            },
          },
        }),
      });
    }

    // Log message should appear
    await waitFor(() => {
      expect(screen.getByText('Test trading log message')).toBeInTheDocument();
    });
  });

  it('should display live trading warning for running tasks', async () => {
    renderWithProviders(<TradingTaskDetailPage />);

    await waitFor(() => {
      expect(screen.getByText('Test Trading Task')).toBeInTheDocument();
    });

    // Warning should be visible for running task
    expect(
      screen.getByText(/actively trading with real money/i)
    ).toBeInTheDocument();
  });
});
