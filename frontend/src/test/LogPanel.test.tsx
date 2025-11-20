import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { LogPanel } from '../components/tasks/display/LogPanel';

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

  // Note: Log streaming tests removed as WebSocket functionality has been removed.
  // Logs are now fetched via HTTP API.

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
});
