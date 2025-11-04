# OpenPositionsPanel Component

## Overview

The `OpenPositionsPanel` is a React component that displays active trading positions in an expandable panel. It shows position details including instrument, direction, units, entry price, current price, and unrealized P&L. The component updates in real-time as position data changes.

## Features

- **Expandable Panel**: Click the header to expand/collapse the panel
- **Position Count Badge**: Shows the number of open positions
- **Total P&L Badge**: Displays the total unrealized P&L across all positions (color-coded: green for profit, red for loss)
- **Real-time Updates**: Automatically updates when position data changes
- **Sortable Columns**: Click column headers to sort positions
- **Filterable Columns**: Filter positions by position ID, instrument, or direction
- **Close Position Action**: Each position has a "Close Position" button
- **Internationalization**: Supports English and Japanese translations
- **Responsive Design**: Works on desktop and mobile devices

## Usage

```tsx
import { OpenPositionsPanel } from '../components/dashboard';
import type { Position } from '../types/chart';

const MyComponent = () => {
  const [positions, setPositions] = useState<Position[]>([
    {
      position_id: 'POS-001',
      instrument: 'EUR_USD',
      direction: 'long',
      units: 10000,
      entry_price: 1.085,
      current_price: 1.0875,
      unrealized_pnl: 25.0,
      opened_at: '2024-01-15T10:30:00Z',
    },
    // ... more positions
  ]);

  const handleClosePosition = (positionId: string) => {
    // Call API to close position
    console.log('Closing position:', positionId);
  };

  return (
    <OpenPositionsPanel
      positions={positions}
      onClosePosition={handleClosePosition}
      loading={false}
    />
  );
};
```

## Props

| Prop              | Type                           | Required | Default | Description                                    |
| ----------------- | ------------------------------ | -------- | ------- | ---------------------------------------------- |
| `positions`       | `Position[]`                   | Yes      | -       | Array of position objects to display           |
| `onClosePosition` | `(positionId: string) => void` | Yes      | -       | Callback function when close button is clicked |
| `loading`         | `boolean`                      | No       | `false` | Disables close buttons when true               |

## Position Type

```typescript
interface Position {
  position_id: string;
  instrument: string;
  direction: 'long' | 'short';
  units: number;
  entry_price: number;
  current_price: number;
  unrealized_pnl: number;
  opened_at: string;
  take_profit?: number;
  stop_loss?: number;
}
```

## Real-time Updates

The component uses `useEffect` to automatically update when the `positions` prop changes. This allows for real-time P&L updates as market prices change:

```tsx
// In your parent component, update positions from WebSocket
useEffect(() => {
  const ws = new WebSocket('wss://api.example.com/positions');

  ws.onmessage = (event) => {
    const updatedPositions = JSON.parse(event.data);
    setPositions(updatedPositions);
  };

  return () => ws.close();
}, []);
```

## Styling

The component uses Material-UI's theming system. You can customize colors through your theme:

```tsx
import { createTheme } from '@mui/material/styles';

const theme = createTheme({
  palette: {
    success: {
      main: '#4caf50', // Color for long positions and positive P&L
    },
    error: {
      main: '#f44336', // Color for short positions and negative P&L
    },
  },
});
```

## Internationalization

The component uses `react-i18next` for translations. Translation keys are in the `dashboard` namespace:

- `positions.title` - Panel title
- `positions.noPositions` - Empty state message
- `positions.positionId` - Position ID column header
- `positions.instrument` - Instrument column header
- `positions.direction` - Direction column header
- `positions.units` - Units column header
- `positions.entryPrice` - Entry Price column header
- `positions.currentPrice` - Current Price column header
- `positions.unrealizedPnL` - Unrealized P&L column header
- `positions.long` - Long direction label
- `positions.short` - Short direction label
- `positions.closePosition` - Close button label

## Testing

The component has comprehensive test coverage. Run tests with:

```bash
npm run test -- OpenPositionsPanel
```

## Requirements

This component implements the following requirements:

- **9.1**: Calculate unrealized profit/loss for each Position on every Market Data Stream update
- **9.2**: Display Position details including entry price, current price, lot size, direction, and unrealized P&L
- **9.4**: Update Position displays within 500 milliseconds of price changes
