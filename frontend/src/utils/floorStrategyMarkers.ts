/**
 * Floor Strategy Markers Utility
 *
 * Creates chart markers for floor strategy events (retracements, layer creation, etc.)
 *
 * Marker Types:
 * - Long (Dark green triangle + Unit size) - retracement entry with direction=long
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
  LONG_RETRACEMENT: '#1b5e20', // Dark green - retracement long
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

// Note: backend currently stores raw strategy events with keys like:
// { "type": "open"|"close"|"layer_opened"|..., "details": {...}, "timestamp": "..." }
// Frontend types call this field "event_type" but we accept both.

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

  events.forEach((event, index) => {
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
  const raw = event as unknown as Record<string, unknown>;

  const isDev =
    typeof import.meta !== 'undefined' &&
    typeof import.meta.env !== 'undefined' &&
    Boolean(import.meta.env.DEV);

  const timestamp =
    (typeof event.timestamp === 'string' && event.timestamp) ||
    (typeof raw.timestamp === 'string' && raw.timestamp) ||
    (typeof raw.ts === 'string' && raw.ts) ||
    '';

  if (!timestamp) {
    if (isDev) {
      // eslint-disable-next-line no-console
      console.warn('[floorStrategyMarkers] Dropping event: missing timestamp', {
        index,
        event_type:
          (raw.event_type as string | undefined) ||
          (raw.type as string | undefined),
        raw,
      });
    }
    return null;
  }

  const eventDate = new Date(timestamp);
  if (isNaN(eventDate.getTime())) {
    if (isDev) {
      // eslint-disable-next-line no-console
      console.warn('[floorStrategyMarkers] Dropping event: invalid timestamp', {
        index,
        timestamp,
        event_type:
          (raw.event_type as string | undefined) ||
          (raw.type as string | undefined),
        raw,
      });
    }
    return null;
  }

  const details = (event.details ||
    (raw.details as Record<string, unknown>) ||
    {}) as Record<string, unknown>;

  // Extract price from various possible fields
  const price =
    details.price ??
    details.current_price ??
    details.exit_price ??
    details.entry_price;

  if (price === null || price === undefined || price === '') {
    if (isDev) {
      // eslint-disable-next-line no-console
      console.warn('[floorStrategyMarkers] Dropping event: missing price', {
        index,
        timestamp,
        event_type:
          (raw.event_type as string | undefined) ||
          (raw.type as string | undefined),
        details,
        raw,
      });
    }
    return null;
  }

  // Get marker configuration based on event type and direction
  const markerConfig = getMarkerConfig(event);

  return {
    id: `event-${index}`,
    date: eventDate,
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
  const raw = event as unknown as Record<string, unknown>;
  const details = (event.details ||
    (raw.details as Record<string, unknown>) ||
    {}) as Record<string, unknown>;

  const eventType = String(
    (raw.event_type as string | undefined) ||
      (raw.type as string | undefined) ||
      ''
  );

  const direction = details.direction as string | undefined;
  const retracementOpen = Boolean(details.retracement_open);
  const units = formatUnits(details.units ?? details.lot_size);
  const layerNumber = details.layer_number ?? details.layer;

  switch (eventType) {
    // Backend: trade open marker
    case 'open':
    // Frontend event names
    case 'initial_entry':
    case 'retracement': {
      const isLong = direction === 'long';
      const isRetracement = eventType === 'retracement' || retracementOpen;

      // Short entries always render as "Short" markers (pink inverted triangle)
      if (!isLong) {
        return {
          type: 'sell',
          color: COLORS.SHORT,
          shape: 'triangleDown',
          label: units ? `S ${units}` : 'Short',
        };
      }

      return {
        type: isRetracement ? 'buy' : 'initial_entry',
        color: isRetracement ? COLORS.LONG_RETRACEMENT : COLORS.LONG_INITIAL,
        shape: 'triangleUp',
        label: units
          ? `L ${units}`
          : isRetracement
            ? 'Long (Retracement)'
            : 'Long (Initial)',
      };
    }

    // Backend: trade close marker
    case 'close':
    case 'strategy_close':
    case 'take_profit':
    case 'take_profit_hit': {
      return {
        type: 'info',
        color: COLORS.CLOSE,
        shape: 'circle',
        label: units ? `C ${units}` : 'Close',
      };
    }

    // Backend: layer created marker
    case 'layer_opened':
    case 'new_layer_created': {
      return {
        type: 'info',
        color: COLORS.NEW_LAYER,
        shape: 'circle',
        label: layerNumber !== undefined ? `L${layerNumber}` : 'Layer',
      };
    }

    // Volatility lock / Margin protection
    case 'volatility_lock': {
      return {
        type: 'info',
        color: COLORS.VOLATILITY_LOCK,
        shape: 'circle',
        label: 'VLock',
      };
    }

    case 'margin_protection': {
      return {
        type: 'info',
        color: COLORS.MARGIN_PROTECTION,
        shape: 'circle',
        label: 'Margin',
      };
    }

    // Start/End strategy
    case 'strategy_started':
    case 'start_strategy': {
      return {
        type: 'start_strategy',
        color: COLORS.START_END,
        shape: 'doubleCircle',
        label: 'START',
      };
    }

    case 'strategy_stopped':
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
  const raw = event as unknown as Record<string, unknown>;
  const details = (event.details ||
    (raw.details as Record<string, unknown>) ||
    {}) as Record<string, unknown>;
  const eventType = String(
    (raw.event_type as string | undefined) ||
      (raw.type as string | undefined) ||
      ''
  );
  const description =
    (typeof event.description === 'string' && event.description) ||
    eventType ||
    'Strategy event';

  const lines: string[] = [description];
  const entryEventTypes = ['open', 'initial_entry', 'retracement'];
  const isEntryEvent = entryEventTypes.includes(eventType);

  // Add relevant details
  if (
    details.price ??
    details.current_price ??
    details.entry_price ??
    details.exit_price
  ) {
    const p = (details.price ??
      details.current_price ??
      details.entry_price ??
      details.exit_price) as unknown;
    lines.push(`Price: ${parseFloat(String(p)).toFixed(5)}`);
  }
  if (details.layer_number !== undefined || details.layer !== undefined) {
    lines.push(`Layer: ${details.layer_number ?? details.layer}`);
  }
  if (details.entry_retracement_count !== undefined) {
    lines.push(`Entry Retracement: ${details.entry_retracement_count}`);
  }
  if (details.retracement_count !== undefined) {
    const label = isEntryEvent ? 'Retracement' : 'Remaining Retracements';
    lines.push(`${label}: ${details.retracement_count}`);
  }
  if (details.units ?? details.lot_size) {
    lines.push(`Units: ${details.units ?? details.lot_size}`);
  }

  return lines.join('\n');
}
