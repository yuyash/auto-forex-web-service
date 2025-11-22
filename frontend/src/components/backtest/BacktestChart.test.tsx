/**
 * BacktestChart Component Tests
 *
 * Tests for the BacktestChart component including:
 * - Initial data fetching
 * - Start/end vertical lines rendering
 * - Trade marker rendering
 * - Strategy layer rendering
 * - Granularity changes
 * - Buffer calculation
 * - Loading states
 * - Error states
 * - Trade click events
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BacktestChart } from './BacktestChart';
import type { Trade } from '../../types/execution';
import type { StrategyLayer } from '../../utils/chartMarkers';

// Mock the AuthContext
vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({
    token: 'test-token',
    user: { id: 1, username: 'testuser' },
    isAuthenticated: true,
  }),
}));

// Mock the FinancialChart component
interface MockFinancialChartProps {
  loading?: boolean;
  error?: string;
  data: unknown[];
  markers?: Array<{ id: string; label: string }>;
  verticalLines?: unknown[];
  horizontalLines?: unknown[];
  onMarkerClick?: (marker: { id: string; label: string }) => void;
}

vi.mock('../chart/FinancialChart', () => ({
  FinancialChart: ({
    loading,
    error,
    data,
    markers,
    verticalLines,
    horizontalLines,
    onMarkerClick,
  }: MockFinancialChartProps) => {
    if (loading) {
      return <div data-testid="chart-loading">Loading...</div>;
    }
    if (error) {
      return <div data-testid="chart-error">{error}</div>;
    }
    return (
      <div data-testid="financial-chart">
        <div data-testid="chart-data-count">{data.length}</div>
        <div data-testid="chart-markers-count">{markers?.length || 0}</div>
        <div data-testid="chart-vlines-count">{verticalLines?.length || 0}</div>
        <div data-testid="chart-hlines-count">
          {horizontalLines?.length || 0}
        </div>
        {markers?.map((marker, idx: number) => (
          <button
            key={idx}
            data-testid={`marker-${marker.id}`}
            onClick={() => onMarkerClick?.(marker)}
          >
            {marker.label}
          </button>
        ))}
      </div>
    );
  },
}));

describe('BacktestChart', () => {
  const mockTrades: Trade[] = [
    {
      entry_time: '2024-01-15T10:00:00Z',
      exit_time: '2024-01-15T11:00:00Z',
      instrument: 'EUR_USD',
      direction: 'long',
      units: 1000,
      entry_price: 1.095,
      exit_price: 1.096,
      pnl: 10.0,
    },
    {
      entry_time: '2024-01-15T14:00:00Z',
      exit_time: '2024-01-15T15:00:00Z',
      instrument: 'EUR_USD',
      direction: 'short',
      units: 1000,
      entry_price: 1.097,
      exit_price: 1.096,
      pnl: 10.0,
    },
  ];

  const mockStrategyLayers: StrategyLayer[] = [
    { price: 1.09, label: 'Support', color: '#4caf50' },
    { price: 1.1, label: 'Resistance', color: '#f44336' },
  ];

  const defaultProps = {
    instrument: 'EUR_USD',
    startDate: '2024-01-15T09:00:00Z',
    endDate: '2024-01-15T17:00:00Z',
    trades: mockTrades,
  };

  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    // Mock fetch for candle data
    fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers(),
      json: async () => ({
        candles: [
          {
            time: 1705312800,
            open: 1.095,
            high: 1.096,
            low: 1.094,
            close: 1.0955,
            volume: 1000,
          },
          {
            time: 1705316400,
            open: 1.0955,
            high: 1.097,
            low: 1.095,
            close: 1.0965,
            volume: 1200,
          },
          {
            time: 1705320000,
            open: 1.0965,
            high: 1.0975,
            low: 1.096,
            close: 1.097,
            volume: 1100,
          },
        ],
      }),
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('Initial data fetching', () => {
    it('should fetch candles on mount', async () => {
      render(<BacktestChart {...defaultProps} />);

      await waitFor(() => {
        expect(fetchMock).toHaveBeenCalled();
      });

      const callUrl = fetchMock.mock.calls[0][0];
      expect(callUrl).toContain('/api/candles');
      expect(callUrl).toContain('instrument=EUR_USD');
      expect(callUrl).toContain('granularity=');
    });

    it('should display loading state initially', () => {
      render(<BacktestChart {...defaultProps} />);
      expect(screen.getByTestId('chart-loading')).toBeInTheDocument();
    });

    it('should display chart after data loads', async () => {
      render(<BacktestChart {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('financial-chart')).toBeInTheDocument();
      });

      expect(screen.getByTestId('chart-data-count')).toHaveTextContent('3');
    });

    it('should calculate buffered range correctly', async () => {
      render(<BacktestChart {...defaultProps} />);

      await waitFor(() => {
        expect(fetchMock).toHaveBeenCalled();
      });

      const callUrl = fetchMock.mock.calls[0][0];
      // Should include from and to timestamps
      expect(callUrl).toContain('from=');
      expect(callUrl).toContain('to=');
    });
  });

  describe('Markers and overlays', () => {
    it('should render trade markers', async () => {
      render(<BacktestChart {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('financial-chart')).toBeInTheDocument();
      });

      // Should have 2 trade markers + 2 start/end markers = 4 total
      expect(screen.getByTestId('chart-markers-count')).toHaveTextContent('4');
    });

    it('should render start and end vertical lines', async () => {
      render(<BacktestChart {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('financial-chart')).toBeInTheDocument();
      });

      // Should have 2 vertical lines (start and end)
      expect(screen.getByTestId('chart-vlines-count')).toHaveTextContent('2');
    });

    it('should render strategy layers as horizontal lines', async () => {
      render(
        <BacktestChart {...defaultProps} strategyLayers={mockStrategyLayers} />
      );

      await waitFor(() => {
        expect(screen.getByTestId('financial-chart')).toBeInTheDocument();
      });

      // Should have 2 horizontal lines for strategy layers
      expect(screen.getByTestId('chart-hlines-count')).toHaveTextContent('2');
    });

    it('should render initial position marker when provided', async () => {
      const initialPosition = {
        capital: 10000,
        timestamp: '2024-01-15T09:00:00Z',
      };

      render(
        <BacktestChart {...defaultProps} initialPosition={initialPosition} />
      );

      await waitFor(() => {
        expect(screen.getByTestId('financial-chart')).toBeInTheDocument();
      });

      // Should have 2 trade markers + 2 start/end markers + 1 initial position = 5 total
      expect(screen.getByTestId('chart-markers-count')).toHaveTextContent('5');
    });
  });

  describe('Granularity changes', () => {
    it('should display granularity selector', async () => {
      render(<BacktestChart {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByRole('combobox')).toBeInTheDocument();
      });
    });

    it('should refetch data when granularity changes', async () => {
      const user = userEvent.setup();
      render(<BacktestChart {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('financial-chart')).toBeInTheDocument();
      });

      const initialCallCount = fetchMock.mock.calls.length;

      // Change granularity by interacting with the Select component
      const select = screen.getByRole('combobox');
      await user.click(select);

      await waitFor(() => {
        expect(screen.getByRole('option', { name: 'H4' })).toBeInTheDocument();
      });

      const h4Option = screen.getByRole('option', { name: 'H4' });
      await user.click(h4Option);

      await waitFor(
        () => {
          expect(fetchMock.mock.calls.length).toBeGreaterThan(initialCallCount);
        },
        { timeout: 2000 }
      );
    });

    it('should call onGranularityChange callback', async () => {
      const onGranularityChange = vi.fn();
      const user = userEvent.setup();

      render(
        <BacktestChart
          {...defaultProps}
          onGranularityChange={onGranularityChange}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId('financial-chart')).toBeInTheDocument();
      });

      // Change granularity
      const select = screen.getByRole('combobox');
      await user.click(select);

      await waitFor(() => {
        expect(screen.getByRole('option', { name: 'H4' })).toBeInTheDocument();
      });

      const h4Option = screen.getByRole('option', { name: 'H4' });
      await user.click(h4Option);

      await waitFor(
        () => {
          expect(onGranularityChange).toHaveBeenCalledWith('H4');
        },
        { timeout: 2000 }
      );
    });
  });

  describe('Error handling', () => {
    it('should display error when fetch fails', async () => {
      fetchMock.mockRejectedValueOnce(new Error('Network error'));

      render(<BacktestChart {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('chart-error')).toBeInTheDocument();
      });

      expect(screen.getByTestId('chart-error')).toHaveTextContent(
        'Network error'
      );
    });

    it('should display error when rate limited', async () => {
      // Mock rate limit response - will retry 3 times then fail
      fetchMock.mockResolvedValue({
        ok: false,
        status: 429,
        statusText: 'Too Many Requests',
        headers: new Headers({ 'X-Rate-Limited': 'true' }),
      });

      render(<BacktestChart {...defaultProps} />);

      // Wait for retries to complete (1s + 2s + 4s = 7s total)
      await waitFor(
        () => {
          expect(screen.getByTestId('chart-error')).toBeInTheDocument();
        },
        { timeout: 8000 }
      );

      expect(screen.getByTestId('chart-error')).toHaveTextContent(
        'Rate limited'
      );
    }, 10000);

    it('should retry on server errors', async () => {
      // First call fails with 500, second succeeds
      fetchMock
        .mockResolvedValueOnce({
          ok: false,
          status: 500,
          statusText: 'Internal Server Error',
          headers: new Headers(),
        })
        .mockResolvedValueOnce({
          ok: true,
          status: 200,
          headers: new Headers(),
          json: async () => ({
            candles: [
              {
                time: 1705312800,
                open: 1.095,
                high: 1.096,
                low: 1.094,
                close: 1.0955,
                volume: 1000,
              },
            ],
          }),
        });

      render(<BacktestChart {...defaultProps} />);

      await waitFor(
        () => {
          expect(screen.getByTestId('financial-chart')).toBeInTheDocument();
        },
        { timeout: 3000 }
      );

      // Should have retried and succeeded (at least 2 calls)
      expect(fetchMock.mock.calls.length).toBeGreaterThanOrEqual(2);
    });

    // Note: Testing missing token requires complex mock setup and is covered by integration tests
  });

  describe('Trade click events', () => {
    it('should call onTradeClick when trade marker is clicked', async () => {
      const onTradeClick = vi.fn();
      const user = userEvent.setup();

      render(<BacktestChart {...defaultProps} onTradeClick={onTradeClick} />);

      await waitFor(() => {
        expect(screen.getByTestId('financial-chart')).toBeInTheDocument();
      });

      // Click first trade marker
      const tradeMarker = screen.getByTestId('marker-trade-0');
      await user.click(tradeMarker);

      expect(onTradeClick).toHaveBeenCalledWith(0);
    });

    it('should not error when onTradeClick is not provided', async () => {
      const user = userEvent.setup();

      render(<BacktestChart {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('financial-chart')).toBeInTheDocument();
      });

      // Click trade marker - should not throw
      const tradeMarker = screen.getByTestId('marker-trade-0');
      await user.click(tradeMarker);

      // No error should occur
      expect(screen.getByTestId('financial-chart')).toBeInTheDocument();
    });
  });

  describe('Loading states', () => {
    it('should show loading indicator while fetching', () => {
      render(<BacktestChart {...defaultProps} />);
      expect(screen.getByTestId('chart-loading')).toBeInTheDocument();
    });

    it('should hide loading indicator after data loads', async () => {
      render(<BacktestChart {...defaultProps} />);

      await waitFor(() => {
        expect(screen.queryByTestId('chart-loading')).not.toBeInTheDocument();
      });

      expect(screen.getByTestId('financial-chart')).toBeInTheDocument();
    });
  });
});
