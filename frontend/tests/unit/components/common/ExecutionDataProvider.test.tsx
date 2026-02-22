/**
 * ExecutionDataProvider Unit Tests
 *
 * Tests for the ExecutionDataProvider HOC component.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { ExecutionDataProvider } from '../../../../src/components/common/ExecutionDataProvider';

// Mock the useTaskPolling hook
vi.mock('../../../../src/hooks/useTaskPolling', () => ({
  useTaskPolling: vi.fn(),
}));

import { useTaskPolling } from '../../../../src/hooks/useTaskPolling';

describe('ExecutionDataProvider', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render loading state when isLoading is true and no status', () => {
    vi.mocked(useTaskPolling).mockReturnValue({
      status: null,
      details: null,
      logs: null,
      isLoading: true,
      error: null,
      isPolling: true,
      startPolling: vi.fn(),
      stopPolling: vi.fn(),
      refetch: vi.fn(),
    });

    render(
      <ExecutionDataProvider taskId={1} taskType="backtest">
        {(executionId, isLoading) => (
          <div>{isLoading ? 'Loading...' : `Execution ID: ${executionId}`}</div>
        )}
      </ExecutionDataProvider>
    );

    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('should render error state when error is present', () => {
    const error = new Error('Failed to fetch execution data');
    vi.mocked(useTaskPolling).mockReturnValue({
      status: null,
      details: null,
      logs: null,
      isLoading: false,
      error,
      isPolling: false,
      startPolling: vi.fn(),
      stopPolling: vi.fn(),
      refetch: vi.fn(),
    });

    render(
      <ExecutionDataProvider taskId={1} taskType="backtest">
        {(executionId, isLoading) => (
          <div>{isLoading ? 'Loading...' : `Execution ID: ${executionId}`}</div>
        )}
      </ExecutionDataProvider>
    );

    expect(
      screen.getByText(/Error Loading Execution Data/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Failed to fetch execution data/i)
    ).toBeInTheDocument();
  });

  it('should render children with execution_id when status is available', async () => {
    vi.mocked(useTaskPolling).mockReturnValue({
      status: { execution_id: 123, status: 'running' },
      details: null,
      logs: null,
      isLoading: false,
      error: null,
      isPolling: true,
      startPolling: vi.fn(),
      stopPolling: vi.fn(),
      refetch: vi.fn(),
    });

    render(
      <ExecutionDataProvider taskId={1} taskType="backtest">
        {(executionId, isLoading) => (
          <div>{isLoading ? 'Loading...' : `Execution ID: ${executionId}`}</div>
        )}
      </ExecutionDataProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Execution ID: 123')).toBeInTheDocument();
    });
  });

  it('should render children with null execution_id when status has no execution_id', async () => {
    vi.mocked(useTaskPolling).mockReturnValue({
      status: { status: 'idle' },
      details: null,
      logs: null,
      isLoading: false,
      error: null,
      isPolling: true,
      startPolling: vi.fn(),
      stopPolling: vi.fn(),
      refetch: vi.fn(),
    });

    render(
      <ExecutionDataProvider taskId={1} taskType="backtest">
        {(executionId, isLoading) => (
          <div>{isLoading ? 'Loading...' : `Execution ID: ${executionId}`}</div>
        )}
      </ExecutionDataProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Execution ID: null')).toBeInTheDocument();
    });
  });

  it('should render custom fallback when provided', () => {
    vi.mocked(useTaskPolling).mockReturnValue({
      status: null,
      details: null,
      logs: null,
      isLoading: true,
      error: null,
      isPolling: true,
      startPolling: vi.fn(),
      stopPolling: vi.fn(),
      refetch: vi.fn(),
    });

    render(
      <ExecutionDataProvider
        taskId={1}
        taskType="backtest"
        fallback={<div>Custom Loading...</div>}
      >
        {(executionId, isLoading) => (
          <div>{isLoading ? 'Loading...' : `Execution ID: ${executionId}`}</div>
        )}
      </ExecutionDataProvider>
    );

    expect(screen.getByText('Custom Loading...')).toBeInTheDocument();
  });

  it('should render custom error fallback when provided', () => {
    const error = new Error('Custom error');
    vi.mocked(useTaskPolling).mockReturnValue({
      status: null,
      details: null,
      logs: null,
      isLoading: false,
      error,
      isPolling: false,
      startPolling: vi.fn(),
      stopPolling: vi.fn(),
      refetch: vi.fn(),
    });

    render(
      <ExecutionDataProvider
        taskId={1}
        taskType="backtest"
        errorFallback={(err) => <div>Custom Error: {err.message}</div>}
      >
        {(executionId, isLoading) => (
          <div>{isLoading ? 'Loading...' : `Execution ID: ${executionId}`}</div>
        )}
      </ExecutionDataProvider>
    );

    expect(screen.getByText('Custom Error: Custom error')).toBeInTheDocument();
  });

  it('should pass isLoading state to children', async () => {
    vi.mocked(useTaskPolling).mockReturnValue({
      status: { execution_id: 123, status: 'running' },
      details: null,
      logs: null,
      isLoading: true,
      error: null,
      isPolling: true,
      startPolling: vi.fn(),
      stopPolling: vi.fn(),
      refetch: vi.fn(),
    });

    render(
      <ExecutionDataProvider taskId={1} taskType="backtest">
        {(executionId, isLoading) => (
          <div>
            <div>Execution ID: {executionId}</div>
            <div>Loading: {isLoading ? 'Yes' : 'No'}</div>
          </div>
        )}
      </ExecutionDataProvider>
    );

    await waitFor(() => {
      expect(screen.getByText('Execution ID: 123')).toBeInTheDocument();
      expect(screen.getByText('Loading: Yes')).toBeInTheDocument();
    });
  });
});
