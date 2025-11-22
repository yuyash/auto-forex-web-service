# Chart Components Documentation

This document describes the chart components used in the Auto Forex Trading System, including configuration options, features, and usage examples.

## Overview

The application uses **react-financial-charts** (v2.0.1) for displaying OHLC (Open, High, Low, Close) candlestick charts with interactive overlays and markers. This library was chosen for its:

- React-first design with hooks support
- Robust overlay positioning that maintains accuracy during pan/zoom
- Comprehensive feature set for financial charting
- Built on d3 for powerful data visualization
- Active maintenance and community support

## Migration from lightweight-charts

The application was previously using TradingView's lightweight-charts library. The migration to react-financial-charts was completed to provide:

- Better support for custom markers and overlays
- More reliable overlay positioning during interactions
- Improved React integration
- Enhanced timezone support
- Better accessibility features

## Chart Components

### 1. FinancialChart (Core Component)

The base chart component that wraps react-financial-charts and provides common functionality.

**Location:** `frontend/src/components/chart/FinancialChart.tsx`

**Features:**

- Candlestick rendering with OHLC data
- Pan and zoom interactions
- Vertical and horizontal line overlays
- Custom markers with click handlers
- OHLC tooltip on hover
- Reset view button
- Marker visibility toggles
- Grid lines and crosshair cursor
- Timezone-aware axis formatting

**Props:**

```typescript
interface FinancialChartProps {
  data: OHLCData[]; // Candle data
  width?: number; // Chart width
  height?: number; // Chart height (default: 500)
  verticalLines?: VerticalLine[]; // Vertical line overlays
  horizontalLines?: HorizontalLine[]; // Horizontal line overlays
  markers?: ChartMarker[]; // Trade/event markers
  onVisibleRangeChange?: (range: { from: Date; to: Date }) => void;
  onLoadMore?: (direction: 'older' | 'newer') => void;
  onMarkerClick?: (marker: ChartMarker) => void;
  initialVisibleRange?: { from: Date; to: Date };
  enablePan?: boolean; // Enable pan interaction
  enableZoom?: boolean; // Enable zoom interaction
  showGrid?: boolean; // Show grid lines
  showCrosshair?: boolean; // Show crosshair cursor
  showOHLCTooltip?: boolean; // Show OHLC tooltip on hover
  showResetButton?: boolean; // Show reset view button
  enableMarkerToggle?: boolean; // Allow toggling markers
  timezone?: string; // IANA timezone (e.g., 'America/New_York')
  loading?: boolean; // Show loading state
  error?: string | null; // Show error message
}
```

### 2. BacktestChart

Specialized chart for backtest results with start/end markers and trade visualization.

**Location:** `frontend/src/components/backtest/BacktestChart.tsx`

**Features:**

- Displays OHLC chart for backtest time range
- Start and end markers (gray double circles)
- Trade markers (cyan buy triangles, orange sell triangles)
- Strategy layer horizontal lines
- Initial position marker (if provided)
- Automatic granularity calculation based on duration
- Buffered range (2-3 candles before/after backtest period)
- No auto-refresh (backtest data is historical)
- Trade click handler for chart-to-table interaction

**Props:**

```typescript
interface BacktestChartProps {
  instrument: string; // Trading instrument
  startDate: string; // ISO 8601 start date
  endDate: string; // ISO 8601 end date
  trades: Trade[]; // Trade executions
  initialPosition?: InitialPosition; // Initial capital/position
  strategyLayers?: StrategyLayer[]; // Strategy-specific levels
  granularity?: string; // Candle granularity (M1, H1, etc.)
  height?: number; // Chart height
  timezone?: string; // IANA timezone
  onGranularityChange?: (granularity: string) => void;
  onTradeClick?: (tradeIndex: number) => void;
}
```

**Usage Example:**

```tsx
<BacktestChart
  instrument="EUR_USD"
  startDate="2024-01-01T00:00:00Z"
  endDate="2024-01-31T23:59:59Z"
  trades={backtestTrades}
  strategyLayers={[
    { price: 1.085, label: 'Support', color: '#4caf50' },
    { price: 1.095, label: 'Resistance', color: '#f44336' },
  ]}
  timezone="America/New_York"
  onTradeClick={(index) => scrollToTrade(index)}
/>
```

### 3. TradingTaskChart

Specialized chart for live trading tasks with real-time updates.

**Location:** `frontend/src/components/trading/TradingTaskChart.tsx`

**Features:**

- Displays OHLC chart from task start to current time
- Start marker (gray double circle)
- Stop marker (if task is stopped)
- Trade markers (cyan buy triangles, orange sell triangles)
- Strategy layer horizontal lines
- Auto-refresh enabled by default (60s interval)
- Scrolls to latest data when new candles arrive
- Updates markers when new trades occur
- Trade click handler for chart-to-table interaction

**Props:**

```typescript
interface TradingTaskChartProps {
  instrument: string; // Trading instrument
  startDate: string; // ISO 8601 start date
  stopDate?: string; // ISO 8601 stop date (if stopped)
  trades: Trade[]; // Trade executions
  strategyLayers?: StrategyLayer[]; // Strategy-specific levels
  granularity?: string; // Candle granularity
  height?: number; // Chart height
  timezone?: string; // IANA timezone
  autoRefresh?: boolean; // Enable auto-refresh (default: true)
  refreshInterval?: number; // Refresh interval in ms (default: 60000)
  onGranularityChange?: (granularity: string) => void;
  onTradeClick?: (tradeIndex: number) => void;
}
```

**Usage Example:**

```tsx
<TradingTaskChart
  instrument="EUR_USD"
  startDate={task.started_at}
  stopDate={task.stopped_at}
  trades={taskTrades}
  autoRefresh={task.status === 'running'}
  refreshInterval={60000}
  timezone="UTC"
  onTradeClick={(index) => highlightTrade(index)}
/>
```

### 4. DashboardChart

Simple chart for market monitoring without trade markers.

**Location:** `frontend/src/components/chart/DashboardChart.tsx`

**Features:**

- Displays recent OHLC candles for selected instrument
- Granularity controls
- Auto-refresh enabled by default (60s interval)
- Scroll-based data loading (older/newer candles)
- No markers or overlays (simple market monitoring)

**Props:**

```typescript
interface DashboardChartProps {
  instrument: string; // Trading instrument
  granularity: string; // Candle granularity
  height?: number; // Chart height
  timezone?: string; // IANA timezone
  autoRefresh?: boolean; // Enable auto-refresh (default: true)
  refreshInterval?: number; // Refresh interval in ms (default: 60000)
  onGranularityChange?: (granularity: string) => void;
}
```

**Usage Example:**

```tsx
<DashboardChart
  instrument="EUR_USD"
  granularity="H1"
  autoRefresh={true}
  refreshInterval={60000}
  timezone="America/New_York"
  onGranularityChange={(gran) => savePreference(gran)}
/>
```

## Chart Configuration

### Default Configuration

Configuration constants are defined in `frontend/src/config/chartConfig.ts`:

```typescript
export const CHART_CONFIG = {
  // Granularity
  DEFAULT_GRANULARITY: 'H1',

  // Data fetching
  DEFAULT_FETCH_COUNT: 500, // Initial candles to fetch
  SCROLL_LOAD_COUNT: 500, // Candles to load on scroll
  MAX_FETCH_COUNT: 5000, // Max candles per request

  // Auto-refresh
  DEFAULT_AUTO_REFRESH_ENABLED: true,
  DEFAULT_AUTO_REFRESH_INTERVAL: 60000, // 60 seconds
  AUTO_REFRESH_INTERVALS: [
    { label: '10 seconds', value: 10000 },
    { label: '30 seconds', value: 30000 },
    { label: '1 minute', value: 60000 },
    { label: '2 minutes', value: 120000 },
    { label: '5 minutes', value: 300000 },
  ],

  // Chart dimensions
  DEFAULT_HEIGHT: 500,
  MIN_HEIGHT: 300,
  MAX_HEIGHT: 1000,

  // Buffer for backtest charts
  BACKTEST_BUFFER_CANDLES: 3, // Candles before/after backtest

  // Scroll/zoom thresholds
  SCROLL_LOAD_THRESHOLD: 10, // Load when within 10 candles of edge
  MIN_VISIBLE_CANDLES: 20,
  MAX_VISIBLE_CANDLES: 500,

  // Error handling
  MAX_RETRY_ATTEMPTS: 3,
  RETRY_DELAYS: [1000, 2000, 4000], // Exponential backoff
};
```

### Marker Types and Colors

**Trade Markers:**

- Buy: Cyan (#00bcd4) triangle pointing up, positioned below candle
- Sell: Orange (#ff9800) triangle pointing down, positioned above candle

**Strategy Markers:**

- Start: Gray (#757575) double circle, positioned at candle high
- End: Gray (#757575) double circle, positioned at candle high
- Initial Position: Blue (#2196f3) double circle

**Custom SVG Paths:**

```typescript
const buyPath = () => 'M 0 0 L 10 10 L -10 10 Z'; // Triangle up
const sellPath = () => 'M 0 10 L 10 0 L -10 0 Z'; // Triangle down
const doubleCirclePath = () => {
  const outerCircle = 'M 0,-5 A 5,5 0 1,1 0,5 A 5,5 0 1,1 0,-5';
  const innerCircle = 'M 0,-3 A 3,3 0 1,1 0,3 A 3,3 0 1,1 0,-3';
  return `${outerCircle} ${innerCircle}`;
};
```

## Timezone Support

All charts support timezone-aware display of timestamps:

- Backend API returns all timestamps in UTC
- Charts convert UTC to user's selected timezone
- Timezone setting comes from global user preferences
- Default timezone is UTC if not specified

**Supported Timezones:**
Any IANA timezone identifier (e.g., 'America/New_York', 'Europe/London', 'Asia/Tokyo')

**Implementation:**

```typescript
import { formatInTimeZone } from 'date-fns-tz';

function formatChartTime(date: Date, timezone: string): string {
  if (timezone && timezone !== 'UTC') {
    return formatInTimeZone(date, timezone, 'yyyy-MM-dd HH:mm:ss');
  }
  return format(date, 'yyyy-MM-dd HH:mm:ss') + ' UTC';
}
```

## Chart-to-Table Interaction

Charts support clicking on trade markers to highlight corresponding rows in trade log tables:

1. User clicks a trade marker on the chart
2. Chart component captures the click event
3. `onTradeClick` callback is called with the trade index
4. Parent component scrolls to and highlights the trade in TradeLogTable

**Example Implementation:**

```tsx
const [selectedTradeIndex, setSelectedTradeIndex] = useState<number | null>(null);

<BacktestChart
  {...props}
  onTradeClick={(index) => {
    setSelectedTradeIndex(index);
    // Scroll to trade in table
    const tradeRow = document.getElementById(`trade-${index}`);
    tradeRow?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }}
/>

<TradeLogTable
  trades={trades}
  selectedIndex={selectedTradeIndex}
/>
```

## Utilities

### Data Transformation

**Location:** `frontend/src/utils/chartDataTransform.ts`

```typescript
// Transform API candles to chart format
function transformCandles(apiCandles: APICandle[]): ChartCandle[];

// Convert backend trade format to frontend format
function convertBackendTradeToFrontend(
  backendTrade: BackendTrade
): FrontendTrade;

// Get granularity duration in milliseconds
function getGranularityDuration(granularity: string): number;

// Calculate buffered range for backtest charts
function calculateBufferedRange(
  startDate: Date,
  endDate: Date,
  granularity: string
);
```

### Marker Creation

**Location:** `frontend/src/utils/chartMarkers.ts`

```typescript
// Create trade markers from trade data
function createTradeMarkers(trades: Trade[]): ChartMarker[];

// Create start/end markers for backtest/task boundaries
function createStartEndMarkers(
  startDate: Date,
  endDate: Date | null,
  startPrice: number,
  endPrice?: number
): ChartMarker[];

// Create vertical line overlay
function createVerticalLine(
  date: Date,
  label: string,
  color: string,
  strokeWidth?: number,
  strokeDasharray?: string
): VerticalLine;

// Create horizontal line overlay
function createHorizontalLine(
  price: number,
  label: string,
  color: string,
  strokeWidth?: number,
  strokeDasharray?: string
): HorizontalLine;

// Create markers from strategy events
function createStrategyEventMarkers(events: StrategyEvent[]): ChartMarker[];
```

### Granularity Calculation

**Location:** `frontend/src/utils/granularityCalculator.ts`

```typescript
// Calculate appropriate granularity based on time range
function calculateGranularity(startDate: Date, endDate: Date): OandaGranularity;

// Get list of available granularities
function getAvailableGranularities(): OandaGranularity[];
```

## Error Handling

Charts implement comprehensive error handling:

### API Errors

1. **Network Failures:**
   - Display error message with retry button
   - Exponential backoff retry (1s, 2s, 4s)
   - Max 3 retry attempts

2. **Rate Limiting (429):**
   - Show rate limit message
   - Exponential backoff
   - Wait for rate limit window to expire

3. **Critical Errors (400, 401, 403, 404, 500):**
   - No automatic retry
   - Display clear error message
   - Log error details for debugging

4. **Invalid Data:**
   - Skip invalid candles
   - Continue rendering valid data
   - Show warning if significant data missing

### Chart Rendering Errors

1. **Empty Data:** Display "No data available" message
2. **Invalid Date Range:** Show error and reset to default
3. **Library Errors:** Catch and log, display fallback error UI

## Performance Considerations

- **Data Loading:** Progressive loading for large datasets
- **Rendering:** Canvas rendering for better performance
- **Memoization:** Expensive calculations are memoized
- **Debouncing:** Scroll/zoom events are debounced
- **Virtual Scrolling:** Data loaded in chunks as user scrolls
- **Caching:** Transformed data is cached to avoid re-transformation

## Accessibility

- **Keyboard Navigation:** Arrow keys for pan, +/- for zoom
- **Screen Readers:** ARIA labels for chart elements
- **High Contrast:** Sufficient color contrast for markers and lines
- **Focus Indicators:** Clear focus indicators for interactive elements
- **Alternative Text:** Text descriptions of chart data

## Browser Compatibility

- Chrome/Edge: Latest 2 versions
- Firefox: Latest 2 versions
- Safari: Latest 2 versions
- Mobile browsers: iOS Safari, Chrome Android

## Testing

Charts are tested using:

- **Unit Tests:** Vitest for utility functions and data transformations
- **Component Tests:** React Testing Library for component rendering and interactions
- **Property-Based Tests:** fast-check for testing universal properties across random inputs
- **Integration Tests:** End-to-end tests for complete user workflows

**Test Coverage:** Minimum 80% for chart components

## Migration Notes

### From lightweight-charts to react-financial-charts

**Key Changes:**

1. Component names changed from `OHLCChart` to specific chart types (`BacktestChart`, `TradingTaskChart`, `DashboardChart`)
2. Marker positioning is more reliable during pan/zoom operations
3. Better timezone support with date-fns-tz integration
4. Enhanced overlay system with vertical/horizontal lines
5. Improved React integration with hooks and proper state management

**Breaking Changes:**

- Old `OHLCChart` component removed
- lightweight-charts dependency removed
- Test mocks updated to use new component names

**Migration Checklist:**

- ✅ Remove lightweight-charts from package.json
- ✅ Delete old OHLCChart components
- ✅ Rename new chart components (remove "New" suffix)
- ✅ Update all imports across codebase
- ✅ Update test mocks
- ✅ Update documentation

## Future Enhancements

Potential future improvements:

1. **Technical Indicators:** Moving averages, RSI, MACD
2. **Drawing Tools:** Trend lines, support/resistance levels
3. **Chart Comparison:** Multiple instruments on same chart
4. **Export:** Export chart as image or data as CSV
5. **Annotations:** User-added custom annotations
6. **Alerts:** Price alerts with visual indicators

## Support

For issues or questions about chart components:

1. Check this documentation
2. Review component source code and inline comments
3. Check the design document: `.kiro/specs/react-financial-charts-migration/design.md`
4. Review test files for usage examples
5. Consult react-financial-charts documentation: https://github.com/react-financial/react-financial-charts

## References

- [react-financial-charts GitHub](https://github.com/react-financial/react-financial-charts)
- [d3-scale Documentation](https://github.com/d3/d3-scale)
- [date-fns-tz Documentation](https://github.com/marnusw/date-fns-tz)
- [OANDA API Documentation](https://developer.oanda.com/rest-live-v20/introduction/)
