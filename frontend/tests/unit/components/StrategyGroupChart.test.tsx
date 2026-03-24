import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import type { DisplayCycleStep } from '../../../src/types/strategyVisualization';

/* ------------------------------------------------------------------ */
/*  Hoisted mocks                                                      */
/* ------------------------------------------------------------------ */

const { mockUseWindowedCandles } = vi.hoisted(() => ({
  mockUseWindowedCandles: vi.fn(),
}));

vi.mock('../../../src/hooks/useWindowedCandles', () => ({
  useWindowedCandles: mockUseWindowedCandles,
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('@mui/material/styles', async () => {
  const actual = await vi.importActual('@mui/material/styles');
  return {
    ...actual,
    useTheme: () => ({ palette: { mode: 'light' } }),
  };
});

vi.mock('lightweight-charts', () => {
  const mockSeries = {
    setData: vi.fn(),
  };
  const mockTimeScale = {
    fitContent: vi.fn(),
  };
  const mockChart = {
    addSeries: vi.fn(() => mockSeries),
    applyOptions: vi.fn(),
    timeScale: vi.fn(() => mockTimeScale),
    remove: vi.fn(),
  };
  return {
    createChart: vi.fn(() => mockChart),
    createSeriesMarkers: vi.fn(() => ({ setMarkers: vi.fn() })),
    CandlestickSeries: 'CandlestickSeries',
  };
});

vi.mock('../../../src/utils/candleColors', () => ({
  getCandleColors: () => ({ upColor: '#16a34a', downColor: '#ef4444' }),
}));

// jsdom does not provide ResizeObserver
class MockResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver =
  MockResizeObserver as unknown as typeof ResizeObserver;

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function makeStep(overrides: Partial<DisplayCycleStep> = {}): DisplayCycleStep {
  return {
    kind: 'open_position',
    event_type: 'open_position',
    entry_id: 1,
    parent_entry_id: null,
    timestamp: '2026-03-20T10:00:00Z',
    basket: 'trend',
    direction: 'long',
    step: 1,
    entry_price: '150.000',
    exit_price: null,
    units: '3000',
    layer_number: null,
    retracement_count: null,
    description: 'Open position',
    expected_interval_pips: null,
    actual_interval_pips: null,
    expected_tp_pips: null,
    actual_tp_pips: null,
    expected_exit_price: null,
    actual_exit_price: null,
    validation_status: 'not_applicable',
    ...overrides,
  };
}

const defaultSteps: DisplayCycleStep[] = [
  makeStep({ entry_id: 1, timestamp: '2026-03-20T10:00:00Z' }),
  makeStep({
    entry_id: 1,
    event_type: 'close_position',
    kind: 'trend_tp',
    timestamp: '2026-03-20T14:30:00Z',
  }),
];

const defaultCandles = [
  { time: 1742464500, open: 150.0, high: 150.5, low: 149.8, close: 150.3 },
  { time: 1742464800, open: 150.3, high: 150.6, low: 150.1, close: 150.4 },
];

/* ------------------------------------------------------------------ */
/*  Tests                                                              */
/* ------------------------------------------------------------------ */

describe('StrategyGroupChart', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  /* ---- Req 8.1: renders chart with valid props ---- */
  it('renders chart container when candles are loaded', async () => {
    mockUseWindowedCandles.mockReturnValue({
      candles: defaultCandles,
      isInitialLoading: false,
      error: null,
    });

    const { StrategyGroupChart } = await import(
      '../../../src/components/tasks/detail/strategy/StrategyGroupChart'
    );

    const { container } = render(
      <StrategyGroupChart
        instrument="USD_JPY"
        startTime="2026-03-20T10:00:00Z"
        endTime="2026-03-20T14:30:00Z"
        steps={defaultSteps}
        height={300}
      />
    );

    // The chart container Box should be rendered (no error, no loading)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
    // Container div should exist
    expect(container.firstChild).toBeTruthy();
  });

  /* ---- Req 8.1: loading state shows spinner ---- */
  it('shows loading spinner during initial candle fetch', async () => {
    mockUseWindowedCandles.mockReturnValue({
      candles: [],
      isInitialLoading: true,
      error: null,
    });

    const { StrategyGroupChart } = await import(
      '../../../src/components/tasks/detail/strategy/StrategyGroupChart'
    );

    render(
      <StrategyGroupChart
        instrument="USD_JPY"
        startTime="2026-03-20T10:00:00Z"
        endTime="2026-03-20T14:30:00Z"
        steps={defaultSteps}
      />
    );

    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  /* ---- Req 10.1: error state shows fallback UI ---- */
  it('displays error alert when candle data fetch fails', async () => {
    mockUseWindowedCandles.mockReturnValue({
      candles: [],
      isInitialLoading: false,
      error: 'Network error',
    });

    const { StrategyGroupChart } = await import(
      '../../../src/components/tasks/detail/strategy/StrategyGroupChart'
    );

    render(
      <StrategyGroupChart
        instrument="USD_JPY"
        startTime="2026-03-20T10:00:00Z"
        endTime="2026-03-20T14:30:00Z"
        steps={defaultSteps}
      />
    );

    const alert = screen.getByRole('alert');
    expect(alert).toBeInTheDocument();
    expect(alert).toHaveTextContent(
      'common:strategyVisualization.chartLoadError'
    );
  });

  /* ---- Req 10.1: error state does not render chart or spinner ---- */
  it('does not render chart or spinner in error state', async () => {
    mockUseWindowedCandles.mockReturnValue({
      candles: [],
      isInitialLoading: false,
      error: 'Server error',
    });

    const { StrategyGroupChart } = await import(
      '../../../src/components/tasks/detail/strategy/StrategyGroupChart'
    );

    const { container } = render(
      <StrategyGroupChart
        instrument="USD_JPY"
        startTime="2026-03-20T10:00:00Z"
        endTime="2026-03-20T14:30:00Z"
        steps={defaultSteps}
      />
    );

    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
    // Only the Alert should be rendered, no chart container
    expect(container.querySelector('[role="alert"]')).toBeTruthy();
  });

  /* ---- Req 8.1: props change triggers re-render with new params ---- */
  it('calls useWindowedCandles with updated params on props change', async () => {
    mockUseWindowedCandles.mockReturnValue({
      candles: defaultCandles,
      isInitialLoading: false,
      error: null,
    });

    const { StrategyGroupChart } = await import(
      '../../../src/components/tasks/detail/strategy/StrategyGroupChart'
    );

    const { rerender } = render(
      <StrategyGroupChart
        instrument="USD_JPY"
        startTime="2026-03-20T10:00:00Z"
        endTime="2026-03-20T14:30:00Z"
        steps={defaultSteps}
      />
    );

    // First render call
    expect(mockUseWindowedCandles).toHaveBeenCalledWith(
      expect.objectContaining({
        instrument: 'USD_JPY',
        startTime: '2026-03-20T10:00:00Z',
        endTime: '2026-03-20T14:30:00Z',
      })
    );

    // Re-render with different cycle (different time range)
    const newSteps = [
      makeStep({ entry_id: 5, timestamp: '2026-03-21T08:00:00Z' }),
    ];

    rerender(
      <StrategyGroupChart
        instrument="EUR_USD"
        startTime="2026-03-21T08:00:00Z"
        endTime="2026-03-21T16:00:00Z"
        steps={newSteps}
      />
    );

    expect(mockUseWindowedCandles).toHaveBeenCalledWith(
      expect.objectContaining({
        instrument: 'EUR_USD',
        startTime: '2026-03-21T08:00:00Z',
        endTime: '2026-03-21T16:00:00Z',
      })
    );
  });

  /* ---- Req 8.2: active cycle (endTime=null) uses current time ---- */
  it('passes current time as endTime when endTime is null', async () => {
    mockUseWindowedCandles.mockReturnValue({
      candles: [],
      isInitialLoading: true,
      error: null,
    });

    const { StrategyGroupChart } = await import(
      '../../../src/components/tasks/detail/strategy/StrategyGroupChart'
    );

    const beforeRender = new Date().toISOString();

    render(
      <StrategyGroupChart
        instrument="USD_JPY"
        startTime="2026-03-20T10:00:00Z"
        endTime={null}
        steps={defaultSteps}
      />
    );

    const afterRender = new Date().toISOString();

    // The hook should have been called with an endTime between before and after render
    const call = mockUseWindowedCandles.mock.calls[0][0];
    expect(call.endTime).toBeDefined();
    expect(call.endTime >= beforeRender).toBe(true);
    expect(call.endTime <= afterRender).toBe(true);
  });

  /* ---- Req 8.1: granularity is M5 ---- */
  it('uses M5 granularity for candle fetching', async () => {
    mockUseWindowedCandles.mockReturnValue({
      candles: [],
      isInitialLoading: true,
      error: null,
    });

    const { StrategyGroupChart } = await import(
      '../../../src/components/tasks/detail/strategy/StrategyGroupChart'
    );

    render(
      <StrategyGroupChart
        instrument="USD_JPY"
        startTime="2026-03-20T10:00:00Z"
        endTime="2026-03-20T14:30:00Z"
        steps={defaultSteps}
      />
    );

    expect(mockUseWindowedCandles).toHaveBeenCalledWith(
      expect.objectContaining({
        granularity: 'M5',
      })
    );
  });
});
