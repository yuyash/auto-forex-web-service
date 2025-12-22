/**
 * Floor Strategy Markers Utility
 *
 * Creates chart markers for floor strategy events (retracements, layer creation, etc.)
 *
 * Marker Types:
 * - Long (Dark green triangle) - retracement entry with direction=long
 * - Long (Blue triangle) - initial_entry with direction=long
 * - Short (Pink inverted triangle) - entries with direction=short
 * - Close (Gray circle) - strategy_close, take_profit
 * - New Layer (Purple circle + Layer number label: L#)
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

// Note: canonical events are flat objects like:
// { "event_type": "initial_entry"|"retracement"|"take_profit"|"add_layer"|..., "timestamp": "...", "price"?: ..., ... }
// We still accept legacy keys like `type` when present to avoid hard crashes on old DB rows.

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

  // Extract price from canonical fields (fallbacks only to keep old rows from breaking).
  const price =
    (raw.price as unknown) ??
    (raw.entry_price as unknown) ??
    (raw.exit_price as unknown) ??
    (raw.bid as unknown);

  if (price === null || price === undefined || price === '') {
    // If we have bid+ask, use mid.
    const bidNum = Number(raw.bid);
    const askNum = Number(raw.ask);
    const mid =
      Number.isFinite(bidNum) && Number.isFinite(askNum)
        ? (bidNum + askNum) / 2
        : null;
    if (mid !== null) {
      const markerConfig = getMarkerConfig(event);
      return {
        id: `event-${index}`,
        date: eventDate,
        price: mid,
        type: markerConfig.type,
        color: markerConfig.color,
        shape: markerConfig.shape,
        label: markerConfig.label,
        tooltip: formatTooltip(event),
      };
    }
    if (isDev) {
      // eslint-disable-next-line no-console
      console.warn('[floorStrategyMarkers] Dropping event: missing price', {
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
  label?: string;
} {
  const raw = event as unknown as Record<string, unknown>;

  const eventType = String(
    (raw.event_type as string | undefined) ||
      (raw.type as string | undefined) ||
      ''
  );

  const normalizeDirection = (value: unknown): 'long' | 'short' | undefined => {
    if (typeof value !== 'string') return undefined;
    const normalized = value.toLowerCase();
    if (normalized === 'long' || normalized === 'short') return normalized;
    return undefined;
  };

  const directionFromRaw = normalizeDirection(raw.direction);
  const directionFromDescription = undefined;

  const unitsRaw = raw.units;
  const unitsNum =
    typeof unitsRaw === 'number'
      ? unitsRaw
      : typeof unitsRaw === 'string'
        ? Number(unitsRaw)
        : undefined;
  const directionFromUnits =
    typeof unitsNum === 'number' && Number.isFinite(unitsNum)
      ? unitsNum < 0
        ? 'short'
        : unitsNum > 0
          ? 'long'
          : undefined
      : undefined;

  const inferredDirection =
    directionFromRaw ?? directionFromDescription ?? directionFromUnits;
  const isShort = inferredDirection === 'short';
  const units = formatUnits(raw.units);
  const layerNumber = raw.layer_number;

  switch (eventType) {
    // Backend: trade open marker
    case 'open':
    // Frontend event names
    case 'initial_entry':
    case 'retracement': {
      const isRetracement = eventType === 'retracement';

      // Preserve the semantic event type for initial entry, but render direction
      // via shape/color/label.
      if (eventType === 'initial_entry') {
        return {
          type: 'initial_entry',
          color: isShort ? COLORS.SHORT : COLORS.LONG_INITIAL,
          shape: isShort ? 'triangleDown' : 'triangleUp',
        };
      }

      // Short entries always render as "Short" markers (pink inverted triangle)
      if (isShort) {
        return {
          type: 'sell',
          color: COLORS.SHORT,
          shape: 'triangleDown',
        };
      }

      return {
        type: isRetracement ? 'buy' : 'initial_entry',
        color: isRetracement ? COLORS.LONG_RETRACEMENT : COLORS.LONG_INITIAL,
        shape: 'triangleUp',
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
      };
    }

    // Backend: layer created marker
    case 'add_layer':
    case 'remove_layer':
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
      };
    }

    case 'margin_protection': {
      return {
        type: 'info',
        color: COLORS.MARGIN_PROTECTION,
        shape: 'circle',
      };
    }

    // Start/End strategy
    case 'strategy_started':
    case 'start_strategy': {
      return {
        type: 'start_strategy',
        color: COLORS.START_END,
        shape: 'doubleCircle',
      };
    }

    case 'strategy_stopped':
    case 'end_strategy': {
      return {
        type: 'end_strategy',
        color: COLORS.START_END,
        shape: 'doubleCircle',
      };
    }

    // Default fallback
    default:
      return {
        type: 'info',
        color: '#666',
        shape: 'circle',
      };
  }
}

/**
 * Format tooltip text for event
 */
function formatTooltip(event: BacktestStrategyEvent): string {
  const raw = event as unknown as Record<string, unknown>;
  const eventType = String(
    (raw.event_type as string | undefined) ||
      (raw.type as string | undefined) ||
      ''
  );

  const lines: string[] = [eventType || 'Strategy event'];

  const price =
    (raw.price as unknown) ??
    (raw.entry_price as unknown) ??
    (raw.exit_price as unknown);
  if (price !== null && price !== undefined && price !== '') {
    const p = Number(price);
    if (Number.isFinite(p)) {
      lines.push(`Price: ${p.toFixed(5)}`);
    }
  }

  if (raw.layer_number !== undefined) {
    lines.push(`Layer: ${String(raw.layer_number)}`);
  }
  if (raw.retracement_count !== undefined) {
    lines.push(`Retracement: ${String(raw.retracement_count)}`);
  }
  if (raw.units !== undefined) {
    lines.push(`Units: ${String(raw.units)}`);
  }
  if (raw.pips !== undefined) {
    lines.push(`Pips: ${String(raw.pips)}`);
  }
  if (raw.pnl !== undefined) {
    lines.push(`P&L: ${String(raw.pnl)}`);
  }

  return lines.join('\n');
}
