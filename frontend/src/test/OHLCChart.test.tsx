import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import OHLCChart from '../components/chart/OHLCChart';
import type { OHLCData } from '../types/chart';

// Mock lightweight-charts
vi.mock('lightweight-charts', () => ({
  createChart: vi.fn(() => ({
    addSeries: vi.fn(() => ({
      setData: vi.fn(),
      update: vi.fn(),
      setMarkers: vi.fn(),
      data: vi.fn(() => []),
    })),
    addCandlestickSeries: vi.fn(() => ({
      setData: vi.fn(),
      update: vi.fn(),
      setMarkers: vi.fn(),
      data: vi.fn(() => []),
    })),
    addLineSeries: vi.fn(() => ({
      setData: vi.fn(),
      update: vi.fn(),
    })),
    applyOptions: vi.fn(),
    timeScale: vi.fn(() => ({
      fitContent: vi.fn(),
      getVisibleRange: vi.fn(() => ({
        from: 1609459200,
        to: 1609632000,
      })),
      subscribeVisibleLogicalRangeChange: vi.fn(),
      getVisibleLogicalRange: vi.fn(() => ({
        from: 50,
        to: 100,
      })),
    })),
    remove: vi.fn(),
  })),
  ColorType: {
    Solid: 0,
  },
  CandlestickSeries: 'CandlestickSeries',
  LineSeries: 'LineSeries',
}));

describe('OHLCChart', () => {
  const mockData: OHLCData[] = [
    { time: 1609459200, open: 1.2, high: 1.25, low: 1.18, close: 1.22 },
    { time: 1609545600, open: 1.22, high: 1.28, low: 1.2, close: 1.26 },
    { time: 1609632000, open: 1.26, high: 1.3, low: 1.24, close: 1.28 },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders chart container', () => {
    const { container } = render(
      <OHLCChart instrument="EUR_USD" granularity="H1" data={mockData} />
    );

    // Chart container should be rendered
    expect(container.firstChild).toBeInTheDocument();
  });

  it('displays loading state when loading data', async () => {
    const mockLoadData = vi.fn(
      () =>
        new Promise<OHLCData[]>((resolve) => {
          setTimeout(() => resolve(mockData), 100);
        })
    );

    render(
      <OHLCChart
        instrument="EUR_USD"
        granularity="H1"
        onLoadHistoricalData={mockLoadData}
      />
    );

    // Should show loading spinner
    await waitFor(() => {
      expect(screen.getByRole('progressbar')).toBeInTheDocument();
    });

    // Wait for loading to complete
    await waitFor(
      () => {
        expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
      },
      { timeout: 200 }
    );
  });

  it('displays error message when data loading fails', async () => {
    const mockLoadData = vi.fn(() =>
      Promise.reject(new Error('Failed to fetch data'))
    );

    render(
      <OHLCChart
        instrument="EUR_USD"
        granularity="H1"
        onLoadHistoricalData={mockLoadData}
      />
    );

    // Wait for error message
    await waitFor(() => {
      expect(screen.getByText(/Failed to fetch data/i)).toBeInTheDocument();
    });
  });

  it('renders with provided data', () => {
    const { container } = render(
      <OHLCChart instrument="EUR_USD" granularity="H1" data={mockData} />
    );

    // Chart should be rendered without errors
    expect(container.firstChild).toBeInTheDocument();
  });

  it('calls onLoadHistoricalData when provided and data is empty', async () => {
    const mockLoadData = vi.fn(() => Promise.resolve(mockData));

    render(
      <OHLCChart
        instrument="EUR_USD"
        granularity="H1"
        onLoadHistoricalData={mockLoadData}
      />
    );

    await waitFor(() => {
      expect(mockLoadData).toHaveBeenCalledWith('EUR_USD', 'H1');
    });
  });

  it('applies custom chart configuration', () => {
    const customConfig = {
      height: 800,
      upColor: '#00ff00',
      downColor: '#ff0000',
    };

    const { container } = render(
      <OHLCChart
        instrument="EUR_USD"
        granularity="H1"
        data={mockData}
        config={customConfig}
      />
    );

    // Chart should be rendered with custom config
    expect(container.firstChild).toBeInTheDocument();
  });
});
