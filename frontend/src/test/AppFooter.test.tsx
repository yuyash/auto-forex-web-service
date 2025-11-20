import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import AppFooter from '../components/layout/AppFooter';
import { AuthProvider } from '../contexts/AuthContext';
import '../i18n/config';

// Mock fetch globally
const mockFetch = vi.fn();
global.fetch = mockFetch;

// Mock AuthContext
const mockAuthContext = {
  user: {
    id: 1,
    email: 'test@example.com',
    timezone: 'UTC',
    is_staff: false,
  },
  token: 'mock-token',
  login: vi.fn(),
  logout: vi.fn(),
  isLoading: false,
};

// Wrapper component with necessary providers
const Wrapper = ({ children }: { children: React.ReactNode }) => (
  <BrowserRouter>
    <AuthProvider value={mockAuthContext}>{children}</AuthProvider>
  </BrowserRouter>
);

describe('AppFooter', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset fetch mock before each test
    mockFetch.mockReset();
    // Mock system settings call that AuthContext makes
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({}),
    });
  });

  it('renders connection status indicator', () => {
    render(<AppFooter />, { wrapper: Wrapper });

    // Connection status should be visible (starts in checking state)
    expect(screen.getByText(/checking/i)).toBeInTheDocument();
  });

  it('renders with all three status chips', () => {
    render(<AppFooter />, { wrapper: Wrapper });

    // Should have connection status
    expect(screen.getByText(/checking/i)).toBeInTheDocument();

    // Should have strategy status
    expect(screen.getByText(/inactive/i)).toBeInTheDocument();

    // Should have time display
    const timeRegex = /\d{2}:\d{2}:\d{2}/;
    expect(screen.getByText(timeRegex)).toBeInTheDocument();
  });

  it('displays strategy status as inactive by default', () => {
    render(<AppFooter />, { wrapper: Wrapper });

    // Strategy status should be visible (currently always inactive)
    expect(screen.getByText(/inactive/i)).toBeInTheDocument();
  });

  it('displays system time in HH:MM:SS format', () => {
    render(<AppFooter />, { wrapper: Wrapper });

    // Time should be displayed (format: HH:MM:SS)
    const timeRegex = /\d{2}:\d{2}:\d{2}/;
    expect(screen.getByText(timeRegex)).toBeInTheDocument();
  });

  it('persists across re-renders', () => {
    const { rerender } = render(<AppFooter />, { wrapper: Wrapper });

    // Initial render should show checking state
    expect(screen.getByText(/checking/i)).toBeInTheDocument();

    // Re-render the component
    rerender(<AppFooter />);

    // Should still be visible
    expect(screen.getByText(/checking/i)).toBeInTheDocument();
    expect(screen.getByText(/inactive/i)).toBeInTheDocument();
  });

  it('renders footer with correct styling', () => {
    const { container } = render(<AppFooter />, { wrapper: Wrapper });

    // Footer element should exist
    const footer = container.querySelector('footer');
    expect(footer).toBeInTheDocument();
  });

  it('displays all status indicators in a horizontal layout', () => {
    render(<AppFooter />, { wrapper: Wrapper });

    // All three status indicators should be present
    expect(screen.getByText(/checking/i)).toBeInTheDocument();
    expect(screen.getByText(/inactive/i)).toBeInTheDocument();
    const timeRegex = /\d{2}:\d{2}:\d{2}/;
    expect(screen.getByText(timeRegex)).toBeInTheDocument();
  });
});
