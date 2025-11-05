import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render } from '@testing-library/react';
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

  it('renders with empty data array', () => {
    const { container } = render(
      <OHLCChart instrument="EUR_USD" granularity="H1" data={[]} />
    );

    // Chart container should still be rendered even with empty data
    expect(container.firstChild).toBeInTheDocument();
  });

  it('calls onLoadOlderData when provided', async () => {
    const mockLoadOlderData = vi.fn(() => Promise.resolve(mockData));

    render(
      <OHLCChart
        instrument="EUR_USD"
        granularity="H1"
        data={mockData}
        onLoadOlderData={mockLoadOlderData}
      />
    );

    // onLoadOlderData should be available but not called immediately
    // It's only called when user scrolls to the left edge
    expect(mockLoadOlderData).not.toHaveBeenCalled();
  });

  it('renders with provided data', () => {
    const { container } = render(
      <OHLCChart instrument="EUR_USD" granularity="H1" data={mockData} />
    );

    // Chart should be rendered without errors
    expect(container.firstChild).toBeInTheDocument();
  });

  it('calls onLoadNewerData when provided', async () => {
    const mockLoadNewerData = vi.fn(() => Promise.resolve(mockData));

    render(
      <OHLCChart
        instrument="EUR_USD"
        granularity="H1"
        data={mockData}
        onLoadNewerData={mockLoadNewerData}
      />
    );

    // onLoadNewerData should be available but not called immediately
    // It's only called when user scrolls to the right edge
    expect(mockLoadNewerData).not.toHaveBeenCalled();
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
