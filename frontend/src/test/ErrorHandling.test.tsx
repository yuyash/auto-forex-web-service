/**
 * Error Handling Tests
 *
 * Tests error toast display, retry functionality, and error recovery
 * for task operations.
 *
 * Requirements: 8.1, 8.2, 8.3
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ToastProvider, useToast } from '../components/common';
import { Button } from '@mui/material';

// Test component that uses toast
function TestComponent({
  errorMessage,
  withRetry = false,
  durationMs,
}: {
  errorMessage: string;
  withRetry?: boolean;
  durationMs?: number;
}) {
  const { showError } = useToast();

  const handleClick = () => {
    if (withRetry) {
      showError(errorMessage, durationMs, {
        label: 'Retry',
        onClick: () => console.log('Retry clicked'),
      });
    } else {
      showError(errorMessage, durationMs);
    }
  };

  return <Button onClick={handleClick}>Trigger Error</Button>;
}

const renderWithProviders = (component: React.ReactElement) => {
  return render(<ToastProvider>{component}</ToastProvider>);
};

describe('Error Toast Display', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should show error toast when triggered', async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <TestComponent errorMessage="Network error occurred" />
    );

    const button = screen.getByRole('button', { name: /trigger error/i });
    await user.click(button);

    await waitFor(() => {
      expect(screen.getByText(/network error occurred/i)).toBeInTheDocument();
    });
  });

  it('should show retry button for errors with retry action', async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <TestComponent errorMessage="Failed to start task" withRetry={true} />
    );

    const button = screen.getByRole('button', { name: /trigger error/i });
    await user.click(button);

    await waitFor(() => {
      expect(screen.getByText(/failed to start task/i)).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: /retry/i })
      ).toBeInTheDocument();
    });
  });

  it('should close toast when close button is clicked', async () => {
    const user = userEvent.setup();
    renderWithProviders(<TestComponent errorMessage="Test error message" />);

    const button = screen.getByRole('button', { name: /trigger error/i });
    await user.click(button);

    await waitFor(() => {
      expect(screen.getByText(/test error message/i)).toBeInTheDocument();
    });

    // Find and click the close button
    const closeButton = screen.getByLabelText(/close/i);
    await user.click(closeButton);

    await waitFor(() => {
      expect(screen.queryByText(/test error message/i)).not.toBeInTheDocument();
    });
  });

  it('should auto-dismiss toast after duration', async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <TestComponent errorMessage="Auto dismiss error" durationMs={100} />
    );

    const button = screen.getByRole('button', { name: /trigger error/i });
    await user.click(button);

    await waitFor(() => {
      expect(screen.getByText(/auto dismiss error/i)).toBeInTheDocument();
    });

    await waitFor(
      () => {
        expect(
          screen.queryByText(/auto dismiss error/i)
        ).not.toBeInTheDocument();
      },
      { timeout: 1000 }
    );
  });
});

describe('Error Recovery', () => {
  it('should allow retry action to be triggered', async () => {
    const user = userEvent.setup();
    const consoleSpy = vi.spyOn(console, 'log');
    renderWithProviders(
      <TestComponent errorMessage="Retry test" withRetry={true} />
    );

    const button = screen.getByRole('button', { name: /trigger error/i });
    await user.click(button);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /retry/i })
      ).toBeInTheDocument();
    });

    const retryButton = screen.getByRole('button', { name: /retry/i });
    await user.click(retryButton);

    expect(consoleSpy).toHaveBeenCalledWith('Retry clicked');
    consoleSpy.mockRestore();
  });
});
