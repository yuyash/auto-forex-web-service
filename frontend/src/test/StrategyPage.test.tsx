import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import StrategyPage from '../pages/StrategyPage';
import { AuthProvider } from '../contexts/AuthContext';

// Mock fetch
const mockFetch = vi.fn();
globalThis.fetch = mockFetch as unknown as typeof fetch;

describe('StrategyPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    localStorage.setItem('token', 'test-token');
    localStorage.setItem(
      'user',
      JSON.stringify({
        id: 1,
        email: 'test@example.com',
        username: 'testuser',
        is_staff: false,
        timezone: 'UTC',
        language: 'en',
      })
    );
  });

  it('renders strategy page title', async () => {
    // Mock all API calls
    mockFetch.mockImplementation((url) => {
      if (url === '/api/system/settings/public') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            registration_enabled: true,
            login_enabled: true,
          }),
        });
      }
      if (url === '/api/accounts/') {
        return Promise.resolve({
          ok: true,
          json: async () => [],
        });
      }
      if (url === '/api/strategies/') {
        return Promise.resolve({
          ok: true,
          json: async () => [],
        });
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({}),
      });
    });

    render(
      <MemoryRouter>
        <AuthProvider>
          <StrategyPage />
        </AuthProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/trading strategy/i)).toBeInTheDocument();
    });
  });

  it('displays account selection section', async () => {
    mockFetch.mockImplementation((url) => {
      if (url === '/api/system/settings/public') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            registration_enabled: true,
            login_enabled: true,
          }),
        });
      }
      if (url === '/api/accounts/') {
        return Promise.resolve({
          ok: true,
          json: async () => [
            {
              id: 1,
              account_id: '001-001-1234567-001',
              api_type: 'practice',
              currency: 'USD',
              balance: 10000,
              margin_used: 0,
              margin_available: 10000,
              is_active: true,
            },
          ],
        });
      }
      if (url === '/api/strategies/') {
        return Promise.resolve({
          ok: true,
          json: async () => [],
        });
      }
      if (url.includes('/strategy/status/')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            is_active: false,
            strategy_type: null,
            config: null,
            instruments: [],
            state: null,
            created_at: null,
            updated_at: null,
          }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({}),
      });
    });

    render(
      <MemoryRouter>
        <AuthProvider>
          <StrategyPage />
        </AuthProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/account selection/i)).toBeInTheDocument();
    });
  });

  it('displays strategy configuration section when account is selected', async () => {
    mockFetch.mockImplementation((url) => {
      if (url === '/api/system/settings/public') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            registration_enabled: true,
            login_enabled: true,
          }),
        });
      }
      if (url === '/api/accounts/') {
        return Promise.resolve({
          ok: true,
          json: async () => [
            {
              id: 1,
              account_id: '001-001-1234567-001',
              api_type: 'practice',
              currency: 'USD',
              balance: 10000,
              margin_used: 0,
              margin_available: 10000,
              is_active: true,
            },
          ],
        });
      }
      if (url === '/api/strategies/') {
        return Promise.resolve({
          ok: true,
          json: async () => [
            {
              id: 'floor',
              name: 'Floor Strategy',
              class_name: 'FloorStrategy',
              description: 'Multi-layer scaling strategy',
              config_schema: {
                type: 'object',
                properties: {
                  lot_size: {
                    type: 'number',
                    default: 1.0,
                  },
                },
              },
            },
          ],
        });
      }
      if (url.includes('/strategy/status/')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            is_active: false,
            strategy_type: null,
            config: null,
            instruments: [],
            state: null,
            created_at: null,
            updated_at: null,
          }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({}),
      });
    });

    render(
      <MemoryRouter>
        <AuthProvider>
          <StrategyPage />
        </AuthProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/configuration/i)).toBeInTheDocument();
    });
  });
});
