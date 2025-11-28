/**
 * Floor Strategy Markers Utility
 *
 * Creates chart markers for floor strategy events (retracements, layer creation, etc.)
 */

import type { ChartMarker } from './chartMarkers';
import type { BacktestStrategyEvent } from '../types/execution';

// Event types that should be plotted as markers
const PLOTTABLE_EVENT_TYPES = new Set([
  'initial_entry',
  'scale_in',
  'strategy_close',
  'start_strategy',
  'end_strategy',
  'take_profit',
  'new_layer_created',
  'margin_protection',
  'volatility_lock',
]);

/**
 * Create floor strategy event markers
 *
 * @param events - Array of strategy events
 * @returns Array of chart markers
 */
export function createFloorStrategyMarkers(
  events: BacktestStrategyEvent[]
): ChartMarker[] {
  const markers: ChartMarker[] = [];

  // Filter to only plottable event types
  const plottableEvents = events.filter((event) =>
    PLOTTABLE_EVENT_TYPES.has(event.event_type)
  );

  plottableEvents.forEach((event, index) => {
    const marker = createMarkerFromEvent(event, index);
    if (marker) {
      markers.push(marker);
    }
  });

  return markers;
}

/**
 * Create a single marker from a strategy event
 */
function createMarkerFromEvent(
  event: BacktestStrategyEvent,
  index: number
): ChartMarker | null {
  if (!event.timestamp) return null;

  // Round timestamp to nearest hour to align with H1 candles
  // This ensures markers appear on the chart even if event times don't exactly match candle times
  const eventDate = new Date(event.timestamp);
  const roundedDate = new Date(eventDate);
  roundedDate.setMinutes(0, 0, 0); // Round down to the hour

  // Extract price from various possible fields
  const price =
    event.details.price ||
    event.details.current_price ||
    event.details.exit_price || // For strategy_close events
    event.details.entry_price; // Fallback for entry events

  if (!price) return null;

  // Map event types to marker styles
  const markerConfig = getMarkerConfig(event.event_type);

  return {
    id: `event-${index}`,
    date: roundedDate,
    price: parseFloat(String(price)),
    type: markerConfig.type,
    color: markerConfig.color,
    shape: markerConfig.shape,
    label: markerConfig.label,
    tooltip: formatTooltip(event),
  };
}

/**
 * Get marker configuration for event type
 */
function getMarkerConfig(eventType: string): {
  type: ChartMarker['type'];
  color: string;
  shape?: ChartMarker['shape'];
  label: string;
} {
  const configs: Record<
    string,
    {
      type: ChartMarker['type'];
      color: string;
      shape?: ChartMarker['shape'];
      label: string;
    }
  > = {
    start_strategy: {
      type: 'start_strategy',
      color: '#757575',
      shape: 'doubleCircle',
      label: 'START',
    },
    end_strategy: {
      type: 'end_strategy',
      color: '#757575',
      shape: 'doubleCircle',
      label: 'END',
    },
    initial_entry: {
      type: 'initial_entry',
      color: '#2196f3',
      shape: 'circle',
      label: 'Entry',
    },
    order_created: {
      type: 'info',
      color: '#4caf50',
      shape: undefined,
      label: 'Order',
    },
    scale_in: {
      type: 'info',
      color: '#00bcd4',
      shape: 'triangleUp',
      label: 'Retr',
    },
    retracement_detected: {
      type: 'info',
      color: '#ff9800',
      shape: undefined,
      label: 'Retr',
    },
    new_layer_created: {
      type: 'info',
      color: '#9c27b0',
      shape: undefined,
      label: 'Layer+',
    },
    take_profit: {
      type: 'info',
      color: '#4caf50',
      shape: 'triangleDown',
      label: 'TP',
    },
    stop_loss: {
      type: 'info',
      color: '#f44336',
      shape: 'triangleDown',
      label: 'SL',
    },
    strategy_close: {
      type: 'info',
      color: '#757575',
      shape: 'triangleDown',
      label: 'Close',
    },
    volatility_lock: {
      type: 'info',
      color: '#ff5722',
      shape: undefined,
      label: 'VLock',
    },
    margin_protection: {
      type: 'info',
      color: '#e91e63',
      shape: undefined,
      label: 'Margin',
    },
  };

  return (
    configs[eventType] || {
      type: 'info',
      color: '#666',
      shape: undefined,
      label: '?',
    }
  );
}

/**
 * Format tooltip text for event
 */
function formatTooltip(event: BacktestStrategyEvent): string {
  const lines: string[] = [event.description];
  const entryEventTypes = ['initial_entry', 'scale_in'];
  const isEntryEvent = entryEventTypes.includes(event.event_type);

  // Add relevant details
  if (event.details.price) {
    lines.push(`Price: ${parseFloat(String(event.details.price)).toFixed(5)}`);
  }
  if (event.details.layer_number !== undefined) {
    lines.push(`Layer: ${event.details.layer_number}`);
  }
  if (event.details.entry_retracement_count !== undefined) {
    lines.push(`Entry Retracement: ${event.details.entry_retracement_count}`);
  }
  if (event.details.retracement_count !== undefined) {
    const label = isEntryEvent ? 'Retracement' : 'Remaining Retracements';
    lines.push(`${label}: ${event.details.retracement_count}`);
  }
  if (event.details.units) {
    lines.push(`Units: ${event.details.units}`);
  }

  return lines.join('\n');
}
