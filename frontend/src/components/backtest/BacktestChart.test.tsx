/**
 * BacktestChart Component Tests
 *
 * Tests for the BacktestChart component
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BacktestChart } from './BacktestChart';

// Mock dependencies
vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({ token: 'mock-token' }),
}));

vi.mock('../../hooks/useMarketConfig', () => ({
  useSupportedInstruments: () => ({
    instruments: ['EUR_USD', 'GBP_USD', 'USD_JPY'],
    isLoading: false,
    error: null,
  }),
  useSupportedGranularities: () => ({
    granularities: [
      { value: 'M1', label: '1 Minute' },
      { value: 'H1', label: '1 Hour' },
      { value: 'D', label: 'Daily' },
    ],
    isLoading: false,
    error: null,
  }),
}));

vi.mock('../chart/FinancialChart', () => ({
  FinancialChart: vi.fn(({ data, markers }) => (
    <div data-testid="financial-chart">
      <div data-testid="chart-data-count">{data?.length || 0}</div>
      <div data-testid="chart-markers-count">{markers?.length || 0}</div>
    </div>
  )),
}));

// Mock fetch
globalThis.fetch = vi.fn();

describe('BacktestChart', () => {
  const defaultProps = {
    instrument: 'EUR_USD',
    startDate: '2024-01-15T10:00:00Z',
    endDate: '2024-01-15T14:00:00Z',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      json: async () => ({
        candles: [
          {
            time: '2024-01-15T10:00:00Z',
            mid: { o: '1.1000', h: '1.1050', l: '1.0950', c: '1.1020' },
            volume: 100,
          },
        ],
      }),
    } as Response);
  });

  describe('Rendering', () => {
    it('should render with controls', async () => {
      render(<BacktestChart {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('financial-chart')).toBeInTheDocument();
      });

      // Should have timeframe selector
      expect(screen.getByLabelText('Timeframe')).toBeInTheDocument();

      // Should have Reset button
      expect(screen.getByText('Reset')).toBeInTheDocument();
    });

    it('should render trade markers', async () => {
      render(<BacktestChart {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('financial-chart')).toBeInTheDocument();
      });

      // Should have 2 trade markers
      expect(screen.getByTestId('chart-markers-count')).toHaveTextContent('2');
    });

    it('should fetch candles on mount', async () => {
      render(<BacktestChart {...defaultProps} />);

      await waitFor(() => {
        expect(globalThis.fetch).toHaveBeenCalledWith(
          expect.stringContaining('/api/candles'),
          expect.objectContaining({
            headers: { Authorization: 'Bearer mock-token' },
          })
        );
      });
    });
  });
});
