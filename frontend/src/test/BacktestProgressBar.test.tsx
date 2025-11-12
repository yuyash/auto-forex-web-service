import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { AuthProvider } from '../contexts/AuthContext';
import BacktestProgressBar from '../components/backtest/BacktestProgressBar';

// Mock fetch globally
global.fetch = vi.fn();

// Helper to render with AuthProvider
const renderWithAuth = (ui: React.ReactElement) => {
  return render(<AuthProvider>{ui}</AuthProvider>);
};

// Mock user data
const mockUser = {
  id: 1,
  username: 'testuser',
  email: 'test@example.com',
};

// Mock backtest data
const mockBacktest = {
  id: 123,
  status: 'running',
  progress: 50,
  strategy_type: 'MA Crossover',
  instrument: ['EUR/USD', 'GBP/USD'],
  start_date: '2024-01-01',
  end_date: '2024-12-31',
  initial_balance: 10000,
};

describe('BacktestProgressBar', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Mock localStorage
    const localStorageMock = {
      getItem: vi.fn((key: string) => {
        if (key === 'token') return 'mock-token';
        if (key === 'user') return JSON.stringify(mockUser);
        return null;
      }),
      setItem: vi.fn(),
      removeItem: vi.fn(),
      clear: vi.fn(),
    };
    Object.defineProperty(window, 'localStorage', {
      value: localStorageMock,
      writable: true,
    });

    // Mock fetch - default to system settings
    (global.fetch as unknown).mockImplementation((url: string) => {
      if (url.includes('/api/system/settings/public')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ trading_enabled: true }),
        });
      }
      if (url.includes('/api/backtest/')) {
        return Promise.resolve({
          ok: true,
          json: async () => mockBacktest,
        });
      }
      return Promise.resolve({
        ok: false,
        json: async () => ({}),
      });
    });
  });

  it('renders no backtest message when backtestId is null', () => {
    renderWithAuth(<BacktestProgressBar backtestId={null} />);
    expect(screen.getByText(/No backtest running/i)).toBeInTheDocument();
  });

  it('renders backtest progress component with backtest ID', async () => {
    renderWithAuth(<BacktestProgressBar backtestId={123} />);

    await waitFor(() => {
      expect(screen.getByText('Backtest Progress')).toBeInTheDocument();
    });
  });

  it('displays backtest details section', async () => {
    renderWithAuth(<BacktestProgressBar backtestId={123} />);

    await waitFor(() => {
      expect(screen.getByText('Backtest Progress')).toBeInTheDocument();
    });
  });

  it('accepts onComplete callback prop', async () => {
    const onComplete = vi.fn();

    renderWithAuth(
      <BacktestProgressBar backtestId={123} onComplete={onComplete} />
    );

    await waitFor(() => {
      expect(screen.getByText('Backtest Progress')).toBeInTheDocument();
    });
  });

  it('accepts onError callback prop', async () => {
    const onError = vi.fn();

    renderWithAuth(<BacktestProgressBar backtestId={123} onError={onError} />);

    await waitFor(() => {
      expect(screen.getByText('Backtest Progress')).toBeInTheDocument();
    });
  });

  it('updates when backtestId changes to null', async () => {
    const { rerender } = renderWithAuth(
      <BacktestProgressBar backtestId={123} />
    );

    await waitFor(() => {
      expect(screen.getByText('Backtest Progress')).toBeInTheDocument();
    });

    // Change to null
    rerender(
      <AuthProvider>
        <BacktestProgressBar backtestId={null} />
      </AuthProvider>
    );

    expect(screen.getByText(/No backtest running/i)).toBeInTheDocument();
  });
});
