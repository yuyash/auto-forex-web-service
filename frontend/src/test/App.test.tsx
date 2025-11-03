import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import App from '../App';

// Mock fetch for system settings
const mockFetch = vi.fn();
globalThis.fetch = mockFetch as unknown as typeof fetch;

describe('App', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    // Mock system settings API call
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({
        registration_enabled: true,
        login_enabled: true,
      }),
    });
  });

  it('renders without crashing', async () => {
    render(<App />);
    // Since user is not authenticated, should redirect to login
    // Wait for i18n to load translations and system settings
    await waitFor(
      () => {
        expect(
          screen.getByRole('heading', { name: /sign in/i })
        ).toBeInTheDocument();
      },
      { timeout: 3000 }
    );
  });

  it('renders login page for unauthenticated users', async () => {
    render(<App />);
    // Wait for i18n to load translations and system settings
    await waitFor(
      () => {
        expect(
          screen.getByRole('heading', { name: /sign in/i })
        ).toBeInTheDocument();
      },
      { timeout: 3000 }
    );
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
  });
});
