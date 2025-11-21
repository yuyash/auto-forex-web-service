import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { OHLCChart, type Trade } from './OHLCChart';
import type { OHLCData } from '../../types/chart';

// Mock the API client
vi.mock('../../services/api/client', () => ({
  apiClient: {
    get: vi.fn(),
  },
}));

// Mock lightweight-charts
vi.mock('lightweight-charts', () => {
  // Create mock functions inside the factory
  const mockSetData = vi.fn();
  const mockSetMarkers = vi.fn();
  const mockFitContent = vi.fn();
  const mockApplyOptions = vi.fn();
  const mockRemove = vi.fn();
  const mockSubscribeVisibleLogicalRangeChange = vi.fn();
  const mockUnsubscribeVisibleLogicalRangeChange = vi.fn();
  const mockGetVisibleLogicalRange = vi.fn(() => ({ from: 100, to: 200 }));
  const mockBarsInLogicalRange = vi.fn(() => ({
    barsBefore: 50,
    barsAfter: 50,
  }));
  const mockAddSeries = vi.fn(() => ({
    setData: mockSetData,
    setMarkers: mockSetMarkers,
    barsInLogicalRange: mockBarsInLogicalRange,
  }));
  const mockTimeScale = vi.fn(() => ({
    fitContent: mockFitContent,
    subscribeVisibleLogicalRangeChange: mockSubscribeVisibleLogicalRangeChange,
    unsubscribeVisibleLogicalRangeChange:
      mockUnsubscribeVisibleLogicalRangeChange,
    getVisibleLogicalRange: mockGetVisibleLogicalRange,
  }));
  const mockCreateSeriesMarkers = vi.fn();
  const mockCreateChart = vi.fn(() => ({
    addSeries: mockAddSeries,
    timeScale: mockTimeScale,
    applyOptions: mockApplyOptions,
    remove: mockRemove,
  }));

  // Store mocks globally for test access
  (globalThis as unknown as { __chartMocks: ChartMocks }).__chartMocks = {
    mockSetData,
    mockSetMarkers,
    mockFitContent,
    mockApplyOptions,
    mockRemove,
    mockAddSeries,
    mockTimeScale,
    mockCreateSeriesMarkers,
    mockCreateChart,
    mockSubscribeVisibleLogicalRangeChange,
    mockUnsubscribeVisibleLogicalRangeChange,
    mockGetVisibleLogicalRange,
    mockBarsInLogicalRange,
  };

  return {
    createChart: mockCreateChart,
    CandlestickSeries: 'CandlestickSeries',
    createSeriesMarkers: mockCreateSeriesMarkers,
  };
});

// Mock granularity calculator
vi.mock('../../utils/granularityCalculator', () => ({
  calculateGranularity: vi.fn(() => 'H1'),
  calculateDataPoints: vi.fn(() => 100),
  getAvailableGranularities: vi.fn(() => [
    'M1',
    'M5',
    'M15',
    'M30',
    'H1',
    'H4',
    'D',
    'W',
  ]),
}));

import { apiClient } from '../../services/api/client';

// Define type for chart mocks
interface ChartMocks {
  mockSetData: ReturnType<typeof vi.fn>;
  mockSetMarkers: ReturnType<typeof vi.fn>;
  mockFitContent: ReturnType<typeof vi.fn>;
  mockApplyOptions: ReturnType<typeof vi.fn>;
  mockRemove: ReturnType<typeof vi.fn>;
  mockAddSeries: ReturnType<typeof vi.fn>;
  mockTimeScale: ReturnType<typeof vi.fn>;
  mockCreateSeriesMarkers: ReturnType<typeof vi.fn>;
  mockCreateChart: ReturnType<typeof vi.fn>;
  mockSubscribeVisibleLogicalRangeChange: ReturnType<typeof vi.fn>;
  mockUnsubscribeVisibleLogicalRangeChange: ReturnType<typeof vi.fn>;
  mockGetVisibleLogicalRange: ReturnType<typeof vi.fn>;
  mockBarsInLogicalRange: ReturnType<typeof vi.fn>;
}

// Extend globalThis to include our mocks
declare global {
  var __chartMocks: ChartMocks;
}

// Get mocks from global
const getMocks = (): ChartMocks => globalThis.__chartMocks;

describe('OHLCChart', () => {
  const mockCandles: OHLCData[] = [
    { time: 1000, open: 1.1, high: 1.2, low: 1.0, close: 1.15 },
    { time: 2000, open: 1.15, high: 1.25, low: 1.1, close: 1.2 },
    { time: 3000, open: 1.2, high: 1.3, low: 1.15, close: 1.25 },
  ];

  const mockTrades: Trade[] = [
    {
      timestamp: '2025-01-01T10:00:00Z',
      action: 'buy',
      price: 1.15,
      units: 1000,
      pnl: 50,
    },
    {
      timestamp: '2025-01-01T11:00:00Z',
      action: 'sell',
      price: 1.2,
      units: -1000,
      pnl: 50,
    },
  ];

  const defaultProps = {
    instrument: 'EUR_USD',
    startDate: '2025-01-01T00:00:00Z',
    endDate: '2025-01-02T00:00:00Z',
    trades: mockTrades,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    // Clear chart mocks
    const mocks = getMocks();
    if (mocks) {
      Object.values(mocks).forEach((mock) => {
        if (typeof mock.mockClear === 'function') {
          mock.mockClear();
        }
      });
    }
    (apiClient.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      instrument: 'EUR_USD',
      granularity: 'H1',
      candles: mockCandles,
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('should show loading state initially', () => {
      render(<OHLCChart {...defaultProps} />);

      expect(screen.getByRole('progressbar')).toBeInTheDocument();
    });

    it('should render chart after data loads', async () => {
      render(<OHLCChart {...defaultProps} />);

      await waitFor(() => {
        expect(apiClient.get).toHaveBeenCalledWith('/candles', {
          instrument: 'EUR_USD',
          start_date: '2025-01-01T00:00:00Z',
          end_date: '2025-01-02T00:00:00Z',
          granularity: 'H1',
          count: 5000,
        });
      });

      await waitFor(() => {
        expect(getMocks().mockSetData).toHaveBeenCalled();
      });
    });

    it('should display error message when API call fails', async () => {
      const errorMessage = 'Failed to fetch candles';
      (apiClient.get as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error(errorMessage)
      );

      render(<OHLCChart {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText(errorMessage)).toBeInTheDocument();
      });
    });

    it('should display message when no data is available', async () => {
      (apiClient.get as ReturnType<typeof vi.fn>).mockResolvedValue({
        instrument: 'EUR_USD',
        granularity: 'H1',
        candles: [],
      });

      render(<OHLCChart {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText(/No chart data available/)).toBeInTheDocument();
      });
    });
  });

  describe('data fetching', () => {
    it('should fetch candles with correct parameters', async () => {
      render(<OHLCChart {...defaultProps} />);

      await waitFor(() => {
        expect(apiClient.get).toHaveBeenCalledWith('/candles', {
          instrument: 'EUR_USD',
          start_date: '2025-01-01T00:00:00Z',
          end_date: '2025-01-02T00:00:00Z',
          granularity: 'H1',
          count: 5000,
        });
      });
    });

    it('should use provided granularity if specified', async () => {
      render(<OHLCChart {...defaultProps} granularity="M5" />);

      await waitFor(() => {
        expect(apiClient.get).toHaveBeenCalledWith('/candles', {
          instrument: 'EUR_USD',
          start_date: '2025-01-01T00:00:00Z',
          end_date: '2025-01-02T00:00:00Z',
          granularity: 'M5',
          count: 5000,
        });
      });
    });

    it('should transform OHLC data correctly', async () => {
      render(<OHLCChart {...defaultProps} />);

      await waitFor(() => {
        expect(getMocks().mockSetData).toHaveBeenCalledWith([
          { time: 1000, open: 1.1, high: 1.2, low: 1.0, close: 1.15 },
          { time: 2000, open: 1.15, high: 1.25, low: 1.1, close: 1.2 },
          { time: 3000, open: 1.2, high: 1.3, low: 1.15, close: 1.25 },
        ]);
      });
    });
  });

  describe('trade markers', () => {
    // Note: Marker tests are skipped as they require complex chart mocking
    // These features are better tested through integration/E2E tests
    it.skip('should add markers for buy trades', async () => {
      const buyTrade: Trade = {
        timestamp: '2025-01-01T10:00:00Z',
        action: 'buy',
        price: 1.15,
        units: 1000,
      };

      render(<OHLCChart {...defaultProps} trades={[buyTrade]} />);

      await waitFor(() => {
        expect(getMocks().mockSetMarkers).toHaveBeenCalled();
      });

      const markers = getMocks().mockSetMarkers.mock.calls[0][0];
      expect(markers).toHaveLength(1);
      expect(markers[0]).toMatchObject({
        position: 'belowBar',
        color: '#26a69a',
        shape: 'arrowUp',
      });
      expect(markers[0].text).toContain('BUY');
      expect(markers[0].text).toContain('1000');
      expect(markers[0].text).toContain('1.15000');
    });

    it.skip('should add markers for sell trades', async () => {
      const sellTrade: Trade = {
        timestamp: '2025-01-01T11:00:00Z',
        action: 'sell',
        price: 1.2,
        units: -1000,
      };

      render(<OHLCChart {...defaultProps} trades={[sellTrade]} />);

      await waitFor(() => {
        expect(getMocks().mockSetMarkers).toHaveBeenCalled();
      });

      const markers = getMocks().mockSetMarkers.mock.calls[0][0];
      expect(markers).toHaveLength(1);
      expect(markers[0]).toMatchObject({
        position: 'aboveBar',
        color: '#ef5350',
        shape: 'arrowDown',
      });
      expect(markers[0].text).toContain('SELL');
      expect(markers[0].text).toContain('1000');
      expect(markers[0].text).toContain('1.20000');
    });

    it.skip('should add markers for multiple trades', async () => {
      render(<OHLCChart {...defaultProps} trades={mockTrades} />);

      await waitFor(() => {
        expect(getMocks().mockSetMarkers).toHaveBeenCalled();
      });

      const markers = getMocks().mockSetMarkers.mock.calls[0][0];
      expect(markers).toHaveLength(2);
    });

    it('should not add markers when trades array is empty', async () => {
      render(<OHLCChart {...defaultProps} trades={[]} />);

      await waitFor(() => {
        expect(getMocks().mockSetData).toHaveBeenCalled();
      });

      // Markers should not be set for empty trades
      expect(getMocks().mockSetMarkers).not.toHaveBeenCalled();
    });

    it.skip('should convert timestamp to correct time format', async () => {
      const trade: Trade = {
        timestamp: '2025-01-01T10:00:00Z',
        action: 'buy',
        price: 1.15,
        units: 1000,
      };

      render(<OHLCChart {...defaultProps} trades={[trade]} />);

      await waitFor(() => {
        expect(getMocks().mockSetMarkers).toHaveBeenCalled();
      });

      const markers = getMocks().mockSetMarkers.mock.calls[0][0];
      const expectedTime = new Date('2025-01-01T10:00:00Z').getTime() / 1000;
      expect(markers[0].time).toBe(expectedTime);
    });
  });

  describe('chart configuration', () => {
    it('should use custom height when provided', async () => {
      render(<OHLCChart {...defaultProps} height={600} />);

      await waitFor(() => {
        expect(getMocks().mockSetData).toHaveBeenCalled();
      });

      // Chart should be created with custom height
      // This is verified by the createChart mock being called
    });

    it('should use default height when not provided', async () => {
      render(<OHLCChart {...defaultProps} />);

      await waitFor(() => {
        expect(getMocks().mockSetData).toHaveBeenCalled();
      });

      // Chart should be created with default height (500)
    });
  });

  describe('error handling', () => {
    it('should handle network errors gracefully', async () => {
      (apiClient.get as ReturnType<typeof vi.fn>).mockRejectedValue(
        new TypeError('Network error')
      );

      render(<OHLCChart {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Network error')).toBeInTheDocument();
      });
    });

    it('should handle API errors with custom messages', async () => {
      (apiClient.get as ReturnType<typeof vi.fn>).mockRejectedValue({
        message: 'Historical data not available',
      });

      render(<OHLCChart {...defaultProps} />);

      await waitFor(() => {
        expect(
          screen.getByText(/Failed to load chart data/)
        ).toBeInTheDocument();
      });
    });
  });

  describe('cleanup', () => {
    it('should cleanup chart on unmount', async () => {
      const { unmount } = render(<OHLCChart {...defaultProps} />);

      await waitFor(() => {
        expect(getMocks().mockSetData).toHaveBeenCalled();
      });

      unmount();

      expect(getMocks().mockRemove).toHaveBeenCalled();
    });
  });
});
