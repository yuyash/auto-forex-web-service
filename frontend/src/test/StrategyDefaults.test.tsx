import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import StrategyDefaults from '../components/settings/StrategyDefaults';
import { AuthProvider } from '../contexts/AuthContext';
import ToastProvider from '../components/common/Toast';
import '../i18n/config';

// Mock fetch
globalThis.fetch = vi.fn() as unknown as typeof fetch;

const mockToken = 'mock-jwt-token';
const mockUser = {
  id: 1,
  username: 'testuser',
  email: 'test@example.com',
  timezone: 'UTC',
  language: 'en',
  is_staff: false,
};

const renderComponent = () => {
  return render(
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <StrategyDefaults />
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  );
};

const mockFetchSettings = (settingsData: Record<string, unknown> = {}) => {
  (globalThis.fetch as ReturnType<typeof vi.fn>).mockImplementation((url) => {
    if (url === '/api/system/settings/public') {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          registration_enabled: true,
          login_enabled: true,
        }),
      });
    }
    if (url === '/api/settings') {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          default_lot_size: 1.0,
          default_scaling_mode: 'additive',
          default_retracement_pips: 30,
          default_take_profit_pips: 25,
          ...settingsData,
        }),
      });
    }
    return Promise.resolve({
      ok: true,
      json: async () => ({}),
    });
  });
};

describe('StrategyDefaults', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.setItem('token', mockToken);
    localStorage.setItem('user', JSON.stringify(mockUser));
    mockFetchSettings();
  });

  it('renders the component with title', async () => {
    renderComponent();

    await waitFor(() => {
      expect(screen.getByText('Strategy Defaults')).toBeInTheDocument();
    });
  });

  it('fetches and displays current settings', async () => {
    mockFetchSettings({
      default_lot_size: 2.5,
      default_scaling_mode: 'multiplicative',
      default_retracement_pips: 50,
      default_take_profit_pips: 40,
    });

    renderComponent();

    await waitFor(() => {
      const lotSizeInput = screen.getByLabelText(
        'Default Lot Size'
      ) as HTMLInputElement;
      expect(lotSizeInput.value).toBe('2.5');
    });

    await waitFor(() => {
      const retracementInput = screen.getByLabelText(
        'Default Retracement (Pips)'
      ) as HTMLInputElement;
      expect(retracementInput.value).toBe('50');
    });

    await waitFor(() => {
      const takeProfitInput = screen.getByLabelText(
        'Default Take Profit (Pips)'
      ) as HTMLInputElement;
      expect(takeProfitInput.value).toBe('40');
    });
  });

  it('allows user to change lot size', async () => {
    renderComponent();

    await waitFor(() => {
      expect(screen.getByLabelText('Default Lot Size')).toBeInTheDocument();
    });

    const lotSizeInput = screen.getByLabelText(
      'Default Lot Size'
    ) as HTMLInputElement;

    // Change the value directly
    fireEvent.change(lotSizeInput, { target: { value: '3.5' } });

    expect(lotSizeInput.value).toBe('3.5');
  });

  it('allows user to change scaling mode', async () => {
    const user = userEvent.setup();

    renderComponent();

    await waitFor(() => {
      expect(screen.getByLabelText('Default Scaling Mode')).toBeInTheDocument();
    });

    const scalingModeSelect = screen.getByLabelText('Default Scaling Mode');
    await user.click(scalingModeSelect);

    const multiplicativeOption = await screen.findByText('Multiplicative');
    await user.click(multiplicativeOption);

    // Verify the selection changed
    await waitFor(() => {
      expect(screen.getByText('Multiplicative')).toBeInTheDocument();
    });
  });

  it('submits form with updated settings', async () => {
    const user = userEvent.setup();
    let putCalled = false;

    (globalThis.fetch as ReturnType<typeof vi.fn>).mockImplementation(
      (url, options) => {
        if (url === '/api/system/settings/public') {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              registration_enabled: true,
              login_enabled: true,
            }),
          });
        }
        if (url === '/api/settings') {
          if (options?.method === 'PUT') {
            putCalled = true;
            return Promise.resolve({
              ok: true,
              json: async () => ({}),
            });
          }
          return Promise.resolve({
            ok: true,
            json: async () => ({
              default_lot_size: 1.0,
              default_scaling_mode: 'additive',
              default_retracement_pips: 30,
              default_take_profit_pips: 25,
            }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: async () => ({}),
        });
      }
    );

    renderComponent();

    await waitFor(() => {
      expect(screen.getByLabelText('Default Lot Size')).toBeInTheDocument();
    });

    const lotSizeInput = screen.getByLabelText(
      'Default Lot Size'
    ) as HTMLInputElement;
    await user.clear(lotSizeInput);
    await user.type(lotSizeInput, '2.0');

    const saveButton = screen.getByRole('button', { name: /save/i });
    await user.click(saveButton);

    await waitFor(() => {
      expect(putCalled).toBe(true);
    });
  });

  it('validates positive lot size', async () => {
    renderComponent();

    await waitFor(() => {
      expect(screen.getByLabelText('Default Lot Size')).toBeInTheDocument();
    });

    const lotSizeInput = screen.getByLabelText(
      'Default Lot Size'
    ) as HTMLInputElement;

    // Verify input has min attribute for validation
    expect(lotSizeInput).toHaveAttribute('min', '0.01');
    expect(lotSizeInput).toHaveAttribute('type', 'number');
  });

  it('validates positive retracement pips', async () => {
    renderComponent();

    await waitFor(() => {
      expect(
        screen.getByLabelText('Default Retracement (Pips)')
      ).toBeInTheDocument();
    });

    const retracementInput = screen.getByLabelText(
      'Default Retracement (Pips)'
    ) as HTMLInputElement;

    // Verify input has min attribute for validation
    expect(retracementInput).toHaveAttribute('min', '1');
    expect(retracementInput).toHaveAttribute('type', 'number');
  });

  it('displays info alert about default values', async () => {
    renderComponent();

    await waitFor(() => {
      expect(
        screen.getByText(
          /these default values will be used when creating new trading strategies/i
        )
      ).toBeInTheDocument();
    });
  });

  it('handles API error when fetching settings', async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockImplementation((url) => {
      if (url === '/api/system/settings/public') {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            registration_enabled: true,
            login_enabled: true,
          }),
        });
      }
      if (url === '/api/settings') {
        return Promise.resolve({
          ok: false,
          json: async () => ({ message: 'Failed to fetch' }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({}),
      });
    });

    renderComponent();

    // Component should still render with default values
    await waitFor(() => {
      expect(screen.getByText('Strategy Defaults')).toBeInTheDocument();
    });
  });

  it('handles API error when saving settings', async () => {
    const user = userEvent.setup();
    let callCount = 0;

    (globalThis.fetch as ReturnType<typeof vi.fn>).mockImplementation(
      (url, options) => {
        if (url === '/api/system/settings/public') {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              registration_enabled: true,
              login_enabled: true,
            }),
          });
        }
        if (url === '/api/settings') {
          if (options?.method === 'PUT') {
            callCount++;
            return Promise.resolve({
              ok: false,
              json: async () => ({ message: 'Failed to save' }),
            });
          }
          return Promise.resolve({
            ok: true,
            json: async () => ({
              default_lot_size: 1.0,
              default_scaling_mode: 'additive',
              default_retracement_pips: 30,
              default_take_profit_pips: 25,
            }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: async () => ({}),
        });
      }
    );

    renderComponent();

    await waitFor(() => {
      expect(screen.getByLabelText('Default Lot Size')).toBeInTheDocument();
    });

    const saveButton = screen.getByRole('button', { name: /save/i });
    await user.click(saveButton);

    // Error should be handled gracefully
    await waitFor(() => {
      expect(callCount).toBe(1);
    });
  });
});
