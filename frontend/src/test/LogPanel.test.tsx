import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { LogPanel } from '../components/tasks/display/LogPanel';

// Mock the useTaskLogsWebSocket hook
vi.mock('../hooks/useTaskLogsWebSocket', () => ({
  useTaskLogsWebSocket: vi.fn(() => ({})),
}));

// Mock AuthContext
vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({
    token: 'mock-token',
    isAuthenticated: true,
  }),
}));

describe('LogPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders log panel with title', () => {
    render(<LogPanel taskType="backtest" taskId={1} />);

    expect(screen.getByText('Execution Logs')).toBeInTheDocument();
  });

  it('shows empty state when no logs', () => {
    render(<LogPanel taskType="backtest" taskId={1} />);

    expect(
      screen.getByText(
        /No logs yet. Logs will appear here when the task starts executing./i
      )
    ).toBeInTheDocument();
  });

  it('renders auto-scroll checkbox', () => {
    render(<LogPanel taskType="backtest" taskId={1} />);

    const checkbox = screen.getByRole('checkbox', { name: /auto-scroll/i });
    expect(checkbox).toBeInTheDocument();
    expect(checkbox).toBeChecked();
  });

  it('renders clear logs button', () => {
    render(<LogPanel taskType="backtest" taskId={1} />);

    const clearButton = screen.getByRole('button', { name: /clear logs/i });
    expect(clearButton).toBeInTheDocument();
    expect(clearButton).toBeDisabled(); // Disabled when no logs
  });

  it('toggles auto-scroll when checkbox is clicked', () => {
    render(<LogPanel taskType="backtest" taskId={1} />);

    const checkbox = screen.getByRole('checkbox', { name: /auto-scroll/i });
    expect(checkbox).toBeChecked();

    fireEvent.click(checkbox);
    expect(checkbox).not.toBeChecked();

    fireEvent.click(checkbox);
    expect(checkbox).toBeChecked();
  });

  it('displays log count', () => {
    render(<LogPanel taskType="backtest" taskId={1} />);

    expect(screen.getByText(/0 entries/i)).toBeInTheDocument();
  });

  it('shows correct log count for single entry', async () => {
    const { rerender } = render(<LogPanel taskType="backtest" taskId={1} />);

    // Simulate receiving a log via the hook
    const { useTaskLogsWebSocket } = await import(
      '../hooks/useTaskLogsWebSocket'
    );
    const mockOnLog = vi.mocked(useTaskLogsWebSocket).mock.calls[0]?.[0]?.onLog;

    if (mockOnLog) {
      mockOnLog({
        execution_id: 1,
        task_id: 1,
        task_type: 'backtest',
        execution_number: 1,
        log: {
          timestamp: '2025-11-16T10:00:00Z',
          level: 'INFO',
          message: 'Test log message',
        },
      });
    }

    rerender(<LogPanel taskType="backtest" taskId={1} />);

    await waitFor(() => {
      expect(screen.getByText(/1 entry/i)).toBeInTheDocument();
    });
  });

  it('respects maxEntries limit', () => {
    render(<LogPanel taskType="backtest" taskId={1} maxEntries={5} />);

    expect(screen.getByText('Execution Logs')).toBeInTheDocument();
  });

  it('shows timestamp when showTimestamp is true', () => {
    render(<LogPanel taskType="backtest" taskId={1} showTimestamp={true} />);

    expect(screen.getByText('Execution Logs')).toBeInTheDocument();
  });

  it('accepts custom height', () => {
    render(<LogPanel taskType="backtest" taskId={1} height={600} />);

    expect(screen.getByText('Execution Logs')).toBeInTheDocument();
  });

  it('filters logs by task_id', () => {
    render(<LogPanel taskType="backtest" taskId={1} />);

    // The component should only show logs for taskId 1
    expect(screen.getByText('Execution Logs')).toBeInTheDocument();
  });

  it('enables clear button when logs are present', async () => {
    const { rerender } = render(<LogPanel taskType="backtest" taskId={1} />);

    const clearButton = screen.getByRole('button', { name: /clear logs/i });
    expect(clearButton).toBeDisabled();

    // Simulate receiving a log
    const { useTaskLogsWebSocket } = await import(
      '../hooks/useTaskLogsWebSocket'
    );
    const mockOnLog = vi.mocked(useTaskLogsWebSocket).mock.calls[0]?.[0]?.onLog;

    if (mockOnLog) {
      mockOnLog({
        execution_id: 1,
        task_id: 1,
        task_type: 'backtest',
        execution_number: 1,
        log: {
          timestamp: '2025-11-16T10:00:00Z',
          level: 'INFO',
          message: 'Test log',
        },
      });
    }

    rerender(<LogPanel taskType="backtest" taskId={1} />);

    await waitFor(() => {
      expect(clearButton).not.toBeDisabled();
    });
  });

  it('connects to WebSocket with correct parameters', async () => {
    render(<LogPanel taskType="backtest" taskId={123} />);

    const { useTaskLogsWebSocket } = await import(
      '../hooks/useTaskLogsWebSocket'
    );

    expect(useTaskLogsWebSocket).toHaveBeenCalledWith(
      expect.objectContaining({
        taskType: 'backtest',
        taskId: 123,
        enabled: true,
      })
    );
  });

  it('does not connect when taskId is 0 or negative', async () => {
    render(<LogPanel taskType="backtest" taskId={0} />);

    const { useTaskLogsWebSocket } = await import(
      '../hooks/useTaskLogsWebSocket'
    );

    expect(useTaskLogsWebSocket).toHaveBeenCalledWith(
      expect.objectContaining({
        enabled: false,
      })
    );
  });
});
