/**
 * Integration tests for ErrorBoundary component.
 * Verifies error catching, fallback rendering, reset, and onError callback.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ErrorBoundary from '../../../src/components/common/ErrorBoundary';

function ThrowingChild({ shouldThrow }: { shouldThrow: boolean }) {
  if (shouldThrow) throw new Error('Test explosion');
  return <div>Child content</div>;
}

describe('ErrorBoundary', () => {
  beforeEach(() => {
    // Suppress React error boundary console.error noise
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  it('renders children when no error', () => {
    render(
      <ErrorBoundary>
        <ThrowingChild shouldThrow={false} />
      </ErrorBoundary>
    );
    expect(screen.getByText('Child content')).toBeInTheDocument();
  });

  it('renders default error UI when child throws', () => {
    render(
      <ErrorBoundary>
        <ThrowingChild shouldThrow={true} />
      </ErrorBoundary>
    );
    expect(screen.getByText('Application Error')).toBeInTheDocument();
    expect(screen.getByText('Test explosion')).toBeInTheDocument();
    expect(screen.getByText('Try Again')).toBeInTheDocument();
  });

  it('renders custom fallback when provided', () => {
    render(
      <ErrorBoundary fallback={<div>Custom fallback</div>}>
        <ThrowingChild shouldThrow={true} />
      </ErrorBoundary>
    );
    expect(screen.getByText('Custom fallback')).toBeInTheDocument();
  });

  it('shows correct title for page-level errors', () => {
    render(
      <ErrorBoundary level="page">
        <ThrowingChild shouldThrow={true} />
      </ErrorBoundary>
    );
    expect(screen.getByText('Page Error')).toBeInTheDocument();
  });

  it('shows correct title for component-level errors', () => {
    render(
      <ErrorBoundary level="component">
        <ThrowingChild shouldThrow={true} />
      </ErrorBoundary>
    );
    expect(screen.getByText('Component Error')).toBeInTheDocument();
  });

  it('calls onError callback when error occurs', () => {
    const onError = vi.fn();
    render(
      <ErrorBoundary onError={onError}>
        <ThrowingChild shouldThrow={true} />
      </ErrorBoundary>
    );
    expect(onError).toHaveBeenCalledTimes(1);
    expect(onError.mock.calls[0][0].message).toBe('Test explosion');
  });

  it('resets error state when Try Again is clicked', async () => {
    const user = userEvent.setup();
    const onReset = vi.fn();

    // We need a component that can toggle throwing
    let shouldThrow = true;
    function ToggleChild() {
      if (shouldThrow) throw new Error('Boom');
      return <div>Recovered</div>;
    }

    const { rerender } = render(
      <ErrorBoundary onReset={onReset}>
        <ToggleChild />
      </ErrorBoundary>
    );

    expect(screen.getByText('Boom')).toBeInTheDocument();

    // Fix the child before clicking reset
    shouldThrow = false;
    await user.click(screen.getByText('Try Again'));

    expect(onReset).toHaveBeenCalledTimes(1);

    // Re-render to pick up the fixed child
    rerender(
      <ErrorBoundary onReset={onReset}>
        <ToggleChild />
      </ErrorBoundary>
    );

    expect(screen.getByText('Recovered')).toBeInTheDocument();
  });

  it('shows Go to Dashboard button for app and page level', () => {
    render(
      <ErrorBoundary level="app">
        <ThrowingChild shouldThrow={true} />
      </ErrorBoundary>
    );
    expect(screen.getByText('Go to Dashboard')).toBeInTheDocument();
  });

  it('does not show Go to Dashboard for component level', () => {
    render(
      <ErrorBoundary level="component">
        <ThrowingChild shouldThrow={true} />
      </ErrorBoundary>
    );
    expect(screen.queryByText('Go to Dashboard')).not.toBeInTheDocument();
  });
});
