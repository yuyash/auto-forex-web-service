import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import AppFooter from '../components/layout/AppFooter';
import { AuthProvider } from '../contexts/AuthContext';
import '../i18n/config';

// Mock fetch globally
const mockFetch = vi.fn();
global.fetch = mockFetch;

// Wrapper component with necessary providers
const Wrapper = ({ children }: { children: React.ReactNode }) => (
  <BrowserRouter>
    <AuthProvider>{children}</AuthProvider>
  </BrowserRouter>
);

describe('AppFooter', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.setItem('token', 'mock-token');
    localStorage.setItem(
      'user',
      JSON.stringify({
        id: 1,
        email: 'test@example.com',
        timezone: 'UTC',
        is_staff: false,
      })
    );
    // Reset fetch mock before each test
    mockFetch.mockReset();
    // Default: simulate "no OANDA account configured" response from backend
    mockFetch.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString();

      if (url.includes('/api/accounts/settings/public')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({}),
        } as Response;
      }

      if (url.includes('/api/market/health/oanda/')) {
        return {
          ok: false,
          status: 400,
          json: async () => ({
            error: 'No OANDA account found. Please configure an account first.',
            error_code: 'NO_OANDA_ACCOUNT',
          }),
        } as Response;
      }

      return {
        ok: true,
        status: 200,
        json: async () => ({}),
      } as Response;
    });
  });

  it('renders connection status indicator', async () => {
    render(<AppFooter />, { wrapper: Wrapper });

    // Connection status should be visible (starts in checking state)
    expect(screen.getByText(/checking/i)).toBeInTheDocument();

    // Then it should switch to an explicit empty-account state
    expect(await screen.findByText(/no account/i)).toBeInTheDocument();
    expect(screen.queryByText(/disconnected/i)).not.toBeInTheDocument();
  });

  it('renders with all three status chips', async () => {
    render(<AppFooter />, { wrapper: Wrapper });

    // Should have connection status
    expect(screen.getByText(/checking/i)).toBeInTheDocument();
    expect(await screen.findByText(/no account/i)).toBeInTheDocument();

    // Should have strategy status
    expect(screen.getByText(/inactive/i)).toBeInTheDocument();

    // Should have time display
    const timeRegex = /\d{2}:\d{2}:\d{2}/;
    expect(screen.getByText(timeRegex)).toBeInTheDocument();
  });

  it('displays strategy status as inactive by default', async () => {
    render(<AppFooter />, { wrapper: Wrapper });

    // Wait for async AuthProvider/footer effects to settle
    await screen.findByText(/no account/i);

    // Strategy status should be visible (currently always inactive)
    expect(screen.getByText(/inactive/i)).toBeInTheDocument();
  });

  it('displays system time in HH:MM:SS format', async () => {
    render(<AppFooter />, { wrapper: Wrapper });

    // Wait for async AuthProvider/footer effects to settle
    await screen.findByText(/no account/i);

    // Time should be displayed (format: HH:MM:SS)
    const timeRegex = /\d{2}:\d{2}:\d{2}/;
    expect(screen.getByText(timeRegex)).toBeInTheDocument();
  });

  it('persists across re-renders', async () => {
    const { rerender } = render(<AppFooter />, { wrapper: Wrapper });

    // Initial render should show checking state
    expect(screen.getByText(/checking/i)).toBeInTheDocument();

    // Empty-account state should appear after the async health call
    expect(await screen.findByText(/no account/i)).toBeInTheDocument();

    // Re-render the component
    rerender(<AppFooter />);

    // Should still be visible
    expect(screen.getByText(/no account/i)).toBeInTheDocument();
    expect(screen.getByText(/inactive/i)).toBeInTheDocument();
  });

  it('renders footer with correct styling', async () => {
    const { container } = render(<AppFooter />, { wrapper: Wrapper });

    // Wait for async AuthProvider/footer effects to settle
    await screen.findByText(/no account/i);

    // Footer element should exist
    const footer = container.querySelector('footer');
    expect(footer).toBeInTheDocument();
  });

  it('displays all status indicators in a horizontal layout', async () => {
    render(<AppFooter />, { wrapper: Wrapper });

    // All three status indicators should be present
    expect(screen.getByText(/checking/i)).toBeInTheDocument();
    expect(await screen.findByText(/no account/i)).toBeInTheDocument();
    expect(screen.getByText(/inactive/i)).toBeInTheDocument();
    const timeRegex = /\d{2}:\d{2}:\d{2}/;
    expect(screen.getByText(timeRegex)).toBeInTheDocument();
  });
});
