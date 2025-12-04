/**
 * Chart Marker Creation Utilities
 *
 * This file contains utilities for creating chart markers, vertical lines,
 * horizontal lines, and strategy event markers with custom SVG paths.
 */

/**
 * Chart Marker interface
 */
export interface ChartMarker {
  id?: string; // Unique identifier for linking to trade log
  date: Date;
  price: number;
  type:
    | 'buy'
    | 'sell'
    | 'info'
    | 'start_strategy'
    | 'end_strategy'
    | 'initial_entry';
  color: string;
  shape?: 'triangleUp' | 'triangleDown' | 'circle' | 'doubleCircle';
  label?: string;
  tooltip?: string;
  eventData?: Record<string, unknown>; // Store full event data for click handling
  strategyEvent?: StrategyEvent;
}

/**
 * Vertical Line interface
 */
export interface VerticalLine {
  date: Date;
  color: string;
  strokeWidth?: number;
  strokeDasharray?: string;
  label?: string;
  labelPosition?: 'top' | 'bottom';
}

/**
 * Horizontal Line interface
 */
export interface HorizontalLine {
  price: number;
  color: string;
  strokeWidth?: number;
  strokeDasharray?: string;
  label?: string;
}

/**
 * Strategy Event interface
 */
export interface StrategyEvent {
  id: number;
  strategy_name: string;
  event_type:
    | 'SIGNAL'
    | 'ORDER'
    | 'POSITION'
    | 'ERROR'
    | 'FLOOR_LEVEL'
    | 'CUSTOM';
  timestamp: string;
  instrument?: string;
  direction?: 'long' | 'short';
  price?: number;
  message: string;
  metadata?: Record<string, unknown>;
}

/**
 * Trade interface for marker creation
 */
export interface Trade {
  timestamp: string; // ISO 8601
  action: 'buy' | 'sell';
  price: number;
  units: number;
  pnl?: number;
}

/**
 * Strategy Layer interface
 */
export interface StrategyLayer {
  price: number;
  label: string;
  color?: string;
}

/**
 * Custom SVG path for buy marker (triangle pointing up)
 */
export function buyPath(): string {
  return 'M 0 0 L 10 10 L -10 10 Z';
}

/**
 * Custom SVG path for sell marker (triangle pointing down)
 */
export function sellPath(): string {
  return 'M 0 10 L 10 0 L -10 0 Z';
}

/**
 * Custom SVG path for circle marker
 */
export function circlePath(): string {
  return 'M 0,-4 A 4,4 0 1,1 0,4 A 4,4 0 1,1 0,-4';
}

/**
 * Custom SVG path for double circle marker (start/end)
 */
export function doubleCirclePath(): string {
  const outerCircle = 'M 0,-5 A 5,5 0 1,1 0,5 A 5,5 0 1,1 0,-5';
  const innerCircle = 'M 0,-3 A 3,3 0 1,1 0,3 A 3,3 0 1,1 0,-3';
  return `${outerCircle} ${innerCircle}`;
}

/**
 * Create trade markers from trade data
 * Buy markers: cyan triangle pointing up, positioned below candle
 * Sell markers: orange triangle pointing down, positioned above candle
 *
 * @param trades - Array of trades
 * @returns Array of chart markers
 */
export function createTradeMarkers(trades: Trade[]): ChartMarker[] {
  return trades.map((trade, index) => {
    const isBuy = trade.action === 'buy';
    const priceOffset = isBuy ? -0.0001 : 0.0001; // Small offset for positioning

    // Format timestamp for tooltip
    const timestamp = new Date(trade.timestamp).toLocaleString();

    // Build detailed tooltip
    const tooltipLines = [
      `${isBuy ? 'BUY' : 'SELL'} Order`,
      `Time: ${timestamp}`,
      `Price: ${trade.price.toFixed(5)}`,
      `Units: ${Math.abs(trade.units)}`,
    ];

    if (trade.pnl !== undefined) {
      const sign = trade.pnl >= 0 ? '+' : '-';
      const amount = Math.abs(trade.pnl).toFixed(2);
      tooltipLines.push(`P&L: ${sign}$${amount}`);
    }

    // Use the trade timestamp directly - callers should align to candle dates if needed
    const tradeDate = new Date(trade.timestamp);

    return {
      id: `trade-${index}`,
      date: tradeDate,
      price: trade.price + priceOffset,
      type: trade.action,
      color: isBuy ? '#00bcd4' : '#ff9800', // Cyan for buy, Orange for sell
      shape: isBuy ? 'triangleUp' : 'triangleDown',
      label: isBuy ? 'BUY' : 'SELL',
      tooltip: tooltipLines.join('\n'),
    };
  });
}

/**
 * Create start and end markers for backtest/trading task
 * Gray double circles positioned at candle high
 *
 * @param startDate - Start date
 * @param endDate - End date (null if still running)
 * @param startPrice - Price at start
 * @param endPrice - Price at end (optional)
 * @returns Array of chart markers
 */
export function createStartEndMarkers(
  startDate: Date,
  endDate: Date | null,
  startPrice: number,
  endPrice?: number
): ChartMarker[] {
  const markers: ChartMarker[] = [
    {
      id: 'start',
      date: startDate,
      price: startPrice,
      type: 'start_strategy',
      color: '#757575', // Gray
      shape: 'doubleCircle',
      label: 'START',
      tooltip: 'Strategy Start',
    },
  ];

  if (endDate && endPrice !== undefined) {
    markers.push({
      id: 'end',
      date: endDate,
      price: endPrice,
      type: 'end_strategy',
      color: '#757575', // Gray
      shape: 'doubleCircle',
      label: 'END',
      tooltip: 'Strategy End',
    });
  }

  return markers;
}

/**
 * Create a vertical line at a specific timestamp
 *
 * @param date - Date for the vertical line
 * @param label - Label text
 * @param color - Line color
 * @param strokeWidth - Line width (default: 2)
 * @param strokeDasharray - Dash pattern (default: solid)
 * @returns Vertical line object
 */
export function createVerticalLine(
  date: Date,
  label: string,
  color: string,
  strokeWidth: number = 2,
  strokeDasharray?: string
): VerticalLine {
  return {
    date,
    color,
    strokeWidth,
    strokeDasharray,
    label,
    labelPosition: 'top',
  };
}

/**
 * Create a horizontal line at a specific price level
 *
 * @param price - Price level for the horizontal line
 * @param label - Label text
 * @param color - Line color
 * @param strokeWidth - Line width (default: 1)
 * @param strokeDasharray - Dash pattern (default: '5,5' for dashed)
 * @returns Horizontal line object
 */
export function createHorizontalLine(
  price: number,
  label: string,
  color: string,
  strokeWidth: number = 1,
  strokeDasharray: string = '5,5'
): HorizontalLine {
  return {
    price,
    color,
    strokeWidth,
    strokeDasharray,
    label,
  };
}

/**
 * Create markers from strategy events
 *
 * @param events - Array of strategy events
 * @returns Array of chart markers
 */
export function createStrategyEventMarkers(
  events: StrategyEvent[]
): ChartMarker[] {
  return events
    .filter((event) => event.price !== undefined)
    .map((event, index) => ({
      id: `event-${event.id || index}`,
      date: new Date(event.timestamp),
      price: event.price!,
      type: 'info',
      color: getEventColor(event.event_type),
      label: event.event_type,
      tooltip: `${event.strategy_name}: ${event.message}`,
      strategyEvent: event,
    }));
}

/**
 * Get color for strategy event type
 */
function getEventColor(eventType: StrategyEvent['event_type']): string {
  const colors: Record<StrategyEvent['event_type'], string> = {
    SIGNAL: '#2196f3', // Blue
    ORDER: '#4caf50', // Green
    POSITION: '#ff9800', // Orange
    ERROR: '#f44336', // Red
    FLOOR_LEVEL: '#9c27b0', // Purple
    CUSTOM: '#607d8b', // Blue Gray
  };
  return colors[eventType] || '#757575';
}
