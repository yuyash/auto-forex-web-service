/**
 * Floor Strategy Markers Utility
 *
 * Creates chart markers for floor strategy events (retracements, layer creation, etc.)
 *
 * Marker Types:
 * - Long (Dark green triangle + Unit size) - scale_in with direction=long
 * - Long (Blue triangle + Unit size) - initial_entry with direction=long
 * - Short (Pink inverted triangle + Unit size) - entries with direction=short
 * - Close (Gray circle + Unit size) - strategy_close, take_profit
 * - New Layer (Purple circle + Layer number)
 * - Volatility Lock (Orange circle)
 * - Margin Protection (Red circle)
 */

import type { ChartMarker } from './chartMarkers';
import type { BacktestStrategyEvent } from '../types/execution';

// Marker colors
const COLORS = {
  // Entry colors
  LONG_INITIAL: '#2196f3', // Blue - initial entry long
  LONG_SCALE_IN: '#1b5e20', // Dark green - scale-in long
  SHORT: '#e91e63', // Pink - short positions
  // Close colors
  CLOSE: '#757575', // Gray - close/take profit
  // Event colors
  NEW_LAYER: '#9c27b0', // Purple - new layer
  VOLATILITY_LOCK: '#ff9800', // Orange - volatility lock
  MARGIN_PROTECTION: '#f44336', // Red - margin protection
  // Start/End colors
  START_END: '#757575', // Gray - start/end markers
};

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
 * Format unit size for display in marker label
 */
function formatUnits(units: unknown): string {
  if (units === null || units === undefined || typeof units === 'boolean')
    return '';
  const numUnits =
    typeof units === 'string' ? parseInt(units, 10) : Number(units);
  if (isNaN(numUnits)) return '';
  // Format with K suffix for thousands
  if (numUnits >= 1000) {
    return `${(numUnits / 1000).toFixed(numUnits % 1000 === 0 ? 0 : 1)}K`;
  }
  return String(numUnits);
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
  const eventDate = new Date(event.timestamp);
  const roundedDate = new Date(eventDate);
  roundedDate.setMinutes(0, 0, 0);

  // Extract price from various possible fields
  const price =
    event.details.price ||
    event.details.current_price ||
    event.details.exit_price ||
    event.details.entry_price;

  if (!price) return null;

  // Get marker configuration based on event type and direction
  const markerConfig = getMarkerConfig(event);

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
 * Get marker configuration based on event type and details
 */
function getMarkerConfig(event: BacktestStrategyEvent): {
  type: ChartMarker['type'];
  color: string;
  shape?: ChartMarker['shape'];
  label: string;
} {
  const { event_type, details } = event;
  const direction = details.direction as string | undefined;
  const units = formatUnits(details.units);
  const layerNumber = details.layer_number;

  switch (event_type) {
    // Initial entry - Blue triangle for long, Pink inverted for short
    case 'initial_entry': {
      const isLong = direction === 'long';
      return {
        type: 'initial_entry',
        color: isLong ? COLORS.LONG_INITIAL : COLORS.SHORT,
        shape: isLong ? 'triangleUp' : 'triangleDown',
        label: units
          ? `${isLong ? 'L' : 'S'} ${units}`
          : isLong
            ? 'Long'
            : 'Short',
      };
    }

    // Scale-in (retracement) - Dark green triangle for long, Pink inverted for short
    case 'scale_in': {
      const isLong = direction === 'long';
      return {
        type: 'buy',
        color: isLong ? COLORS.LONG_SCALE_IN : COLORS.SHORT,
        shape: isLong ? 'triangleUp' : 'triangleDown',
        label: units
          ? `${isLong ? 'L' : 'S'} ${units}`
          : isLong
            ? 'Long'
            : 'Short',
      };
    }

    // Close events - Gray circle with unit size
    case 'strategy_close':
    case 'take_profit': {
      return {
        type: 'info',
        color: COLORS.CLOSE,
        shape: 'circle',
        label: units ? `C ${units}` : 'Close',
      };
    }

    // New layer - Purple circle with layer number
    case 'new_layer_created': {
      return {
        type: 'info',
        color: COLORS.NEW_LAYER,
        shape: 'circle',
        label: layerNumber !== undefined ? `L${layerNumber}` : 'Layer',
      };
    }

    // Volatility lock - Orange circle
    case 'volatility_lock': {
      return {
        type: 'info',
        color: COLORS.VOLATILITY_LOCK,
        shape: 'circle',
        label: 'VLock',
      };
    }

    // Margin protection - Red circle
    case 'margin_protection': {
      return {
        type: 'info',
        color: COLORS.MARGIN_PROTECTION,
        shape: 'circle',
        label: 'Margin',
      };
    }

    // Start/End strategy
    case 'start_strategy': {
      return {
        type: 'start_strategy',
        color: COLORS.START_END,
        shape: 'doubleCircle',
        label: 'START',
      };
    }

    case 'end_strategy': {
      return {
        type: 'end_strategy',
        color: COLORS.START_END,
        shape: 'doubleCircle',
        label: 'END',
      };
    }

    // Default fallback
    default:
      return {
        type: 'info',
        color: '#666',
        shape: 'circle',
        label: '?',
      };
  }
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
