# Chart Components

## OHLCChart

A React component for displaying OHLC (Open, High, Low, Close) candlestick charts using the Lightweight Charts library.

### Features

- Real-time candlestick chart rendering
- Configurable chart styling (colors, dimensions)
- Automatic data loading via callback
- Responsive design with window resize handling
- Loading and error states
- TypeScript support

### Usage

#### Basic Usage with Static Data

```tsx
import { OHLCChart } from './components/chart';
import { OHLCData } from './types/chart';

const data: OHLCData[] = [
  { time: 1609459200, open: 1.2, high: 1.25, low: 1.18, close: 1.22 },
  { time: 1609545600, open: 1.22, high: 1.28, low: 1.2, close: 1.26 },
  { time: 1609632000, open: 1.26, high: 1.3, low: 1.24, close: 1.28 },
];

function App() {
  return <OHLCChart instrument="EUR_USD" granularity="H1" data={data} />;
}
```

#### Usage with Async Data Loading

```tsx
import { OHLCChart } from './components/chart';
import { OHLCData } from './types/chart';

async function loadHistoricalData(
  instrument: string,
  granularity: string
): Promise<OHLCData[]> {
  const response = await fetch(
    `/api/candles?instrument=${instrument}&granularity=${granularity}`
  );
  return response.json();
}

function App() {
  return (
    <OHLCChart
      instrument="EUR_USD"
      granularity="H1"
      onLoadHistoricalData={loadHistoricalData}
    />
  );
}
```

#### Custom Styling

```tsx
import { OHLCChart } from './components/chart';

function App() {
  return (
    <OHLCChart
      instrument="EUR_USD"
      granularity="H1"
      data={data}
      config={{
        height: 800,
        upColor: '#26a69a',
        downColor: '#ef5350',
        wickUpColor: '#26a69a',
        wickDownColor: '#ef5350',
      }}
    />
  );
}
```

### Props

| Prop                   | Type                                                               | Required | Description                                          |
| ---------------------- | ------------------------------------------------------------------ | -------- | ---------------------------------------------------- |
| `instrument`           | `string`                                                           | Yes      | Currency pair or instrument symbol (e.g., "EUR_USD") |
| `granularity`          | `string`                                                           | Yes      | Timeframe granularity (e.g., "H1", "M5", "D")        |
| `data`                 | `OHLCData[]`                                                       | No       | Array of OHLC data points                            |
| `config`               | `ChartConfig`                                                      | No       | Chart styling configuration                          |
| `onLoadHistoricalData` | `(instrument: string, granularity: string) => Promise<OHLCData[]>` | No       | Callback to load historical data                     |

### Types

#### OHLCData

```typescript
interface OHLCData {
  time: number; // Unix timestamp
  open: number; // Opening price
  high: number; // Highest price
  low: number; // Lowest price
  close: number; // Closing price
}
```

#### ChartConfig

```typescript
interface ChartConfig {
  width?: number; // Chart width in pixels
  height?: number; // Chart height in pixels (default: 600)
  upColor?: string; // Color for bullish candles (default: '#26a69a')
  downColor?: string; // Color for bearish candles (default: '#ef5350')
  borderVisible?: boolean; // Show candle borders (default: false)
  wickUpColor?: string; // Color for bullish wicks (default: '#26a69a')
  wickDownColor?: string; // Color for bearish wicks (default: '#ef5350')
}
```

### Granularity Options

Supported OANDA granularities:

- **Seconds**: S5, S10, S15, S30
- **Minutes**: M1, M2, M4, M5, M10, M15, M30
- **Hours**: H1, H2, H3, H4, H6, H8, H12
- **Other**: D (Daily), W (Weekly), M (Monthly)

### Notes

- The chart automatically handles window resize events
- Loading state is displayed while fetching data
- Error messages are shown if data loading fails
- The chart uses the Lightweight Charts library for optimal performance
- All timestamps should be in Unix format (seconds since epoch)
