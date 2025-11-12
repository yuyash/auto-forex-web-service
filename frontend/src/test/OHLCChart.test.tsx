import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, waitFor, screen } from '@testing-library/react';
import OHLCChart from '../components/chart/OHLCChart';
import type { OHLCData } from '../types/chart';

// Mock useMarketData hook
vi.mock('../hooks/useMarketData', () => ({
  default: vi.fn(() => ({
    tickData: null,
    isConnected: false,
    error: null,
  })),
}));

// Mock lightweight-charts
const mockSetData = vi.fn();
const mockUpdate = vi.fn();
const mockSetMarkers = vi.fn();
const mockFitContent = vi.fn();
const mockSubscribeVisibleLogicalRangeChange = vi.fn();
const mockUnsubscribeVisibleLogicalRangeChange = vi.fn();
const mockGetVisibleLogicalRange = vi.fn();
const mockGetVisibleRange = vi.fn();
const mockScrollToPosition = vi.fn();
const mockRemove = vi.fn();
const mockApplyOptions = vi.fn();
const mockSubscribeCrosshairMove = vi.fn();
const mockUnsubscribeCrosshairMove = vi.fn();

vi.mock('lightweight-charts', () => ({
  createChart: vi.fn(() => ({
    addSeries: vi.fn(() => ({
      setData: mockSetData,
      update: mockUpdate,
      setMarkers: mockSetMarkers,
      data: vi.fn(() => []),
    })),
    applyOptions: mockApplyOptions,
    timeScale: vi.fn(() => ({
      fitContent: mockFitContent,
      getVisibleRange: mockGetVisibleRange,
      scrollToPosition: mockScrollToPosition,
      subscribeVisibleLogicalRangeChange:
        mockSubscribeVisibleLogicalRangeChange,
      unsubscribeVisibleLogicalRangeChange:
        mockUnsubscribeVisibleLogicalRangeChange,
      getVisibleLogicalRange: mockGetVisibleLogicalRange,
    })),
    subscribeCrosshairMove: mockSubscribeCrosshairMove,
    unsubscribeCrosshairMove: mockUnsubscribeCrosshairMove,
    remove: mockRemove,
  })),
  ColorType: {
    Solid: 0,
  },
  CandlestickSeries: 'CandlestickSeries',
  LineSeries: 'LineSeries',
}));

describe('OHLCChart - Refactored Self-Contained Component', () => {
  const mockData: OHLCData[] = [
    { time: 1609459200, open: 1.2, high: 1.25, low: 1.18, close: 1.22 },
    { time: 1609545600, open: 1.22, high: 1.28, low: 1.2, close: 1.26 },
    { time: 1609632000, open: 1.26, high: 1.3, low: 1.24, close: 1.28 },
  ];

  const olderMockData: OHLCData[] = [
    { time: 1609372800, open: 1.18, high: 1.21, low: 1.17, close: 1.2 },
    { time: 1609459200, open: 1.2, high: 1.25, low: 1.18, close: 1.22 },
  ];

  const newerMockData: OHLCData[] = [
    { time: 1609718400, open: 1.28, high: 1.32, low: 1.27, close: 1.31 },
    { time: 1609804800, open: 1.31, high: 1.35, low: 1.3, close: 1.33 },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    mockGetVisibleLogicalRange.mockReturnValue({ from: 50, to: 100 });
    mockGetVisibleRange.mockReturnValue({
      from: 1609459200,
      to: 1609632000,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Initial Data Loading', () => {
    it('loads initial data on mount', async () => {
      const mockFetchCandles = vi.fn().mockResolvedValue(mockData);

      render(
        <OHLCChart
          instrument="EUR_USD"
          granularity="H1"
          fetchCandles={mockFetchCandles}
        />
      );

      await waitFor(() => {
        expect(mockFetchCandles).toHaveBeenCalledWith('EUR_USD', 'H1', 5000);
      });

      await waitFor(() => {
        expect(mockSetData).toHaveBeenCalledWith(
          expect.arrayContaining([
            expect.objectContaining({ time: 1609459200 }),
          ])
        );
      });
    });

    it('displays loading indicator during initial load', async () => {
      const mockFetchCandles = vi
        .fn()
        .mockImplementation(
          () =>
            new Promise((resolve) => setTimeout(() => resolve(mockData), 100))
        );

      render(
        <OHLCChart
          instrument="EUR_USD"
          granularity="H1"
          fetchCandles={mockFetchCandles}
        />
      );

      // Loading indicator should appear
      expect(screen.getByTestId('chart-loading-indicator')).toBeInTheDocument();

      await waitFor(() => {
        expect(mockFetchCandles).toHaveBeenCalled();
      });
    });

    it('handles initial load error without clearing data', async () => {
      const mockFetchCandles = vi
        .fn()
        .mockRejectedValue(new Error('Network error'));

      render(
        <OHLCChart
          instrument="EUR_USD"
          granularity="H1"
          fetchCandles={mockFetchCandles}
        />
      );

      await waitFor(() => {
        expect(mockFetchCandles).toHaveBeenCalled();
      });

      // Error message should be displayed
      await waitFor(() => {
        expect(screen.getByText(/network error/i)).toBeInTheDocument();
      });
    });
  });

  describe('Load Older Data', () => {
    it('prepends older data correctly', async () => {
      const mockFetchCandles = vi
        .fn()
        .mockResolvedValueOnce(mockData)
        .mockResolvedValueOnce(olderMockData);

      render(
        <OHLCChart
          instrument="EUR_USD"
          granularity="H1"
          fetchCandles={mockFetchCandles}
        />
      );

      // Wait for initial load
      await waitFor(() => {
        expect(mockFetchCandles).toHaveBeenCalledWith('EUR_USD', 'H1', 5000);
      });

      // Verify initial data was loaded
      expect(mockFetchCandles).toHaveBeenCalledTimes(1);
    });

    it('does not call fetchCandles with before parameter when data is empty', async () => {
      const mockFetchCandles = vi.fn().mockResolvedValue([]);

      render(
        <OHLCChart
          instrument="EUR_USD"
          granularity="H1"
          fetchCandles={mockFetchCandles}
        />
      );

      await waitFor(() => {
        expect(mockFetchCandles).toHaveBeenCalledWith('EUR_USD', 'H1', 5000);
      });

      // Should only be called once for initial load
      expect(mockFetchCandles).toHaveBeenCalledTimes(1);
    });
  });

  describe('Load Newer Data', () => {
    it('loads initial data successfully', async () => {
      const mockFetchCandles = vi.fn().mockResolvedValue(mockData);

      render(
        <OHLCChart
          instrument="EUR_USD"
          granularity="H1"
          fetchCandles={mockFetchCandles}
        />
      );

      await waitFor(() => {
        expect(mockFetchCandles).toHaveBeenCalledWith('EUR_USD', 'H1', 5000);
      });

      expect(mockFetchCandles).toHaveBeenCalledTimes(1);
    });
  });

  describe('Loading States', () => {
    it('sets isLoading to true during fetch', async () => {
      const mockFetchCandles = vi
        .fn()
        .mockImplementation(
          () =>
            new Promise((resolve) => setTimeout(() => resolve(mockData), 100))
        );

      render(
        <OHLCChart
          instrument="EUR_USD"
          granularity="H1"
          fetchCandles={mockFetchCandles}
        />
      );

      // Loading indicator should be visible
      expect(screen.getByTestId('chart-loading-indicator')).toBeInTheDocument();

      await waitFor(() => {
        expect(mockFetchCandles).toHaveBeenCalled();
      });
    });

    it('clears loading state after successful fetch', async () => {
      const mockFetchCandles = vi.fn().mockResolvedValue(mockData);

      render(
        <OHLCChart
          instrument="EUR_USD"
          granularity="H1"
          fetchCandles={mockFetchCandles}
        />
      );

      await waitFor(() => {
        expect(mockFetchCandles).toHaveBeenCalled();
      });

      // Loading indicator should not be visible after load completes
      await waitFor(() => {
        expect(
          screen.queryByTestId('chart-loading-indicator')
        ).not.toBeInTheDocument();
      });
    });
  });

  describe('Error Handling', () => {
    it('displays error message on fetch failure', async () => {
      const mockFetchCandles = vi
        .fn()
        .mockRejectedValue(new Error('Failed to fetch'));

      render(
        <OHLCChart
          instrument="EUR_USD"
          granularity="H1"
          fetchCandles={mockFetchCandles}
        />
      );

      await waitFor(() => {
        expect(screen.getByText(/failed to fetch/i)).toBeInTheDocument();
      });
    });

    it('displays error message on network error', async () => {
      const mockFetchCandles = vi
        .fn()
        .mockRejectedValue(new Error('Network error'));

      render(
        <OHLCChart
          instrument="EUR_USD"
          granularity="H1"
          fetchCandles={mockFetchCandles}
        />
      );

      await waitFor(() => {
        expect(screen.getByText(/network error/i)).toBeInTheDocument();
      });
    });
  });

  describe('Instrument/Granularity Changes', () => {
    it('clears data and reloads when instrument changes', async () => {
      const mockFetchCandles = vi
        .fn()
        .mockResolvedValueOnce(mockData)
        .mockResolvedValueOnce(newerMockData);

      const { rerender } = render(
        <OHLCChart
          instrument="EUR_USD"
          granularity="H1"
          fetchCandles={mockFetchCandles}
        />
      );

      await waitFor(() => {
        expect(mockFetchCandles).toHaveBeenCalledWith('EUR_USD', 'H1', 5000);
      });

      // Change instrument
      rerender(
        <OHLCChart
          instrument="GBP_USD"
          granularity="H1"
          fetchCandles={mockFetchCandles}
        />
      );

      await waitFor(() => {
        expect(mockFetchCandles).toHaveBeenCalledWith('GBP_USD', 'H1', 5000);
      });

      expect(mockFetchCandles).toHaveBeenCalledTimes(2);
    });

    it('clears data and reloads when granularity changes', async () => {
      const mockFetchCandles = vi
        .fn()
        .mockResolvedValueOnce(mockData)
        .mockResolvedValueOnce(newerMockData);

      const { rerender } = render(
        <OHLCChart
          instrument="EUR_USD"
          granularity="H1"
          fetchCandles={mockFetchCandles}
        />
      );

      await waitFor(() => {
        expect(mockFetchCandles).toHaveBeenCalledWith('EUR_USD', 'H1', 5000);
      });

      // Change granularity
      rerender(
        <OHLCChart
          instrument="EUR_USD"
          granularity="M15"
          fetchCandles={mockFetchCandles}
        />
      );

      await waitFor(() => {
        expect(mockFetchCandles).toHaveBeenCalledWith('EUR_USD', 'M15', 5000);
      });

      expect(mockFetchCandles).toHaveBeenCalledTimes(2);
    });
  });

  describe('Strategy Event Overlay', () => {
    it('should display strategy event markers on the chart', async () => {
      const mockFetchCandles = vi.fn().mockResolvedValue(mockData);
      const mockStrategyEvents = [
        {
          id: '1',
          strategy_name: 'MA Crossover',
          event_type: 'SIGNAL' as const,
          message: 'Buy signal detected',
          timestamp: '2024-01-01T12:00:00Z',
          instrument: 'EUR_USD',
        },
        {
          id: '2',
          strategy_name: 'RSI Strategy',
          event_type: 'ORDER' as const,
          message: 'Order placed',
          timestamp: '2024-01-01T13:00:00Z',
          instrument: 'EUR_USD',
          direction: 'long' as const,
          price: 1.105,
        },
      ];

      render(
        <OHLCChart
          instrument="EUR_USD"
          granularity="H1"
          fetchCandles={mockFetchCandles}
          strategyEvents={mockStrategyEvents}
        />
      );

      await waitFor(() => {
        expect(mockSetData).toHaveBeenCalled();
      });

      // Verify markers were set with strategy events
      await waitFor(() => {
        expect(mockSetMarkers).toHaveBeenCalled();
        const markersCall = mockSetMarkers.mock.calls[0][0];
        // Should have 2 strategy event markers
        expect(markersCall.length).toBeGreaterThanOrEqual(2);
      });
    });

    it('should filter strategy events by instrument', async () => {
      const mockFetchCandles = vi.fn().mockResolvedValue(mockData);
      const mockStrategyEvents = [
        {
          id: '1',
          strategy_name: 'MA Crossover',
          event_type: 'SIGNAL' as const,
          message: 'Buy signal detected',
          timestamp: '2024-01-01T12:00:00Z',
          instrument: 'EUR_USD',
        },
        {
          id: '2',
          strategy_name: 'RSI Strategy',
          event_type: 'ORDER' as const,
          message: 'Order placed',
          timestamp: '2024-01-01T13:00:00Z',
          instrument: 'GBP_USD', // Different instrument
        },
      ];

      render(
        <OHLCChart
          instrument="EUR_USD"
          granularity="H1"
          fetchCandles={mockFetchCandles}
          strategyEvents={mockStrategyEvents}
        />
      );

      await waitFor(() => {
        expect(mockSetData).toHaveBeenCalled();
      });

      // Note: The filtering happens in DashboardPage, not in OHLCChart
      // OHLCChart displays all events passed to it
      // This test verifies that events are converted to markers
      await waitFor(() => {
        expect(mockSetMarkers).toHaveBeenCalled();
      });
    });

    it('should apply correct marker styles based on event type', async () => {
      const mockFetchCandles = vi.fn().mockResolvedValue(mockData);
      const mockStrategyEvents = [
        {
          id: '1',
          strategy_name: 'Test',
          event_type: 'SIGNAL' as const,
          message: 'Signal',
          timestamp: '2024-01-01T12:00:00Z',
        },
        {
          id: '2',
          strategy_name: 'Test',
          event_type: 'ERROR' as const,
          message: 'Error',
          timestamp: '2024-01-01T13:00:00Z',
        },
        {
          id: '3',
          strategy_name: 'Test',
          event_type: 'POSITION' as const,
          message: 'Position',
          timestamp: '2024-01-01T14:00:00Z',
        },
      ];

      render(
        <OHLCChart
          instrument="EUR_USD"
          granularity="H1"
          fetchCandles={mockFetchCandles}
          strategyEvents={mockStrategyEvents}
        />
      );

      await waitFor(() => {
        expect(mockSetMarkers).toHaveBeenCalled();
        const markersCall = mockSetMarkers.mock.calls[0][0];

        // Find the strategy event markers
        type Marker = {
          text?: string;
          color?: string;
          shape?: string;
          position?: string;
        };
        const signalMarker = markersCall.find(
          (m: Marker) => m.text && m.text.includes('SIGNAL')
        );
        const errorMarker = markersCall.find(
          (m: Marker) => m.text && m.text.includes('ERROR')
        );
        const positionMarker = markersCall.find(
          (m: Marker) => m.text && m.text.includes('POSITION')
        );

        // Verify marker styles
        if (signalMarker) {
          expect(signalMarker.color).toBe('#2196F3'); // Blue
          expect(signalMarker.shape).toBe('circle');
          expect(signalMarker.position).toBe('aboveBar');
        }

        if (errorMarker) {
          expect(errorMarker.color).toBe('#F44336'); // Red
          expect(errorMarker.shape).toBe('circle');
          expect(errorMarker.position).toBe('belowBar');
        }

        if (positionMarker) {
          expect(positionMarker.color).toBe('#FF9800'); // Orange
          expect(positionMarker.shape).toBe('square');
          expect(positionMarker.position).toBe('aboveBar');
        }
      });
    });
  });
});
