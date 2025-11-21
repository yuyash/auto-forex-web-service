/**
 * Unit tests for chart marker creation utilities
 */

import { describe, it, expect } from 'vitest';
import {
  createTradeMarkers,
  createStartEndMarkers,
  createVerticalLine,
  createHorizontalLine,
  createStrategyEventMarkers,
  buyPath,
  sellPath,
  doubleCirclePath,
  type Trade,
  type StrategyEvent,
} from './chartMarkers';

describe('SVG Path Functions', () => {
  it('should return valid SVG path for buy marker', () => {
    const path = buyPath();
    expect(path).toBe('M 0 0 L 10 10 L -10 10 Z');
  });

  it('should return valid SVG path for sell marker', () => {
    const path = sellPath();
    expect(path).toBe('M 0 10 L 10 0 L -10 0 Z');
  });

  it('should return valid SVG path for double circle', () => {
    const path = doubleCirclePath();
    expect(path).toContain('M 0,-5 A 5,5');
    expect(path).toContain('M 0,-3 A 3,3');
  });
});

describe('createTradeMarkers', () => {
  it('should create buy markers with correct properties', () => {
    const trades: Trade[] = [
      {
        timestamp: '2024-01-01T10:00:00Z',
        action: 'buy',
        price: 1.1,
        units: 1000,
        pnl: 50.0,
      },
    ];

    const markers = createTradeMarkers(trades);

    expect(markers).toHaveLength(1);
    expect(markers[0].id).toBe('trade-0');
    expect(markers[0].date).toEqual(new Date('2024-01-01T10:00:00Z'));
    expect(markers[0].price).toBe(1.1 - 0.3); // Buy positioned below
    expect(markers[0].type).toBe('buy');
    expect(markers[0].color).toBe('#00bcd4'); // Cyan
    expect(markers[0].shape).toBe('triangleUp');
    expect(markers[0].label).toBe('BUY');
    expect(markers[0].tooltip).toContain('BUY 1000 @ 1.10000');
    expect(markers[0].tooltip).toContain('P&L: +50.00');
  });

  it('should create sell markers with correct properties', () => {
    const trades: Trade[] = [
      {
        timestamp: '2024-01-01T11:00:00Z',
        action: 'sell',
        price: 1.15,
        units: 500,
        pnl: -25.0,
      },
    ];

    const markers = createTradeMarkers(trades);

    expect(markers).toHaveLength(1);
    expect(markers[0].id).toBe('trade-0');
    expect(markers[0].date).toEqual(new Date('2024-01-01T11:00:00Z'));
    expect(markers[0].price).toBe(1.15 + 0.3); // Sell positioned above
    expect(markers[0].type).toBe('sell');
    expect(markers[0].color).toBe('#ff9800'); // Orange
    expect(markers[0].shape).toBe('triangleDown');
    expect(markers[0].label).toBe('SELL');
    expect(markers[0].tooltip).toContain('SELL 500 @ 1.15000');
    expect(markers[0].tooltip).toContain('P&L: -25.00');
  });

  it('should handle trades without pnl', () => {
    const trades: Trade[] = [
      {
        timestamp: '2024-01-01T10:00:00Z',
        action: 'buy',
        price: 1.1,
        units: 1000,
      },
    ];

    const markers = createTradeMarkers(trades);

    expect(markers[0].tooltip).not.toContain('P&L');
  });

  it('should create multiple markers', () => {
    const trades: Trade[] = [
      {
        timestamp: '2024-01-01T10:00:00Z',
        action: 'buy',
        price: 1.1,
        units: 1000,
      },
      {
        timestamp: '2024-01-01T11:00:00Z',
        action: 'sell',
        price: 1.15,
        units: 1000,
      },
    ];

    const markers = createTradeMarkers(trades);

    expect(markers).toHaveLength(2);
    expect(markers[0].id).toBe('trade-0');
    expect(markers[1].id).toBe('trade-1');
  });

  it('should handle empty trades array', () => {
    const markers = createTradeMarkers([]);
    expect(markers).toEqual([]);
  });
});

describe('createStartEndMarkers', () => {
  it('should create start marker', () => {
    const startDate = new Date('2024-01-01T10:00:00Z');
    const markers = createStartEndMarkers(startDate, null, 1.1);

    expect(markers).toHaveLength(1);
    expect(markers[0].id).toBe('start');
    expect(markers[0].date).toEqual(startDate);
    expect(markers[0].price).toBe(1.1);
    expect(markers[0].type).toBe('start_strategy');
    expect(markers[0].color).toBe('#757575'); // Gray
    expect(markers[0].shape).toBe('doubleCircle');
    expect(markers[0].label).toBe('START');
    expect(markers[0].tooltip).toBe('Strategy Start');
  });

  it('should create start and end markers', () => {
    const startDate = new Date('2024-01-01T10:00:00Z');
    const endDate = new Date('2024-01-01T12:00:00Z');
    const markers = createStartEndMarkers(startDate, endDate, 1.1, 1.15);

    expect(markers).toHaveLength(2);
    expect(markers[0].id).toBe('start');
    expect(markers[1].id).toBe('end');
    expect(markers[1].date).toEqual(endDate);
    expect(markers[1].price).toBe(1.15);
    expect(markers[1].type).toBe('end_strategy');
    expect(markers[1].label).toBe('END');
  });

  it('should not create end marker if endDate is null', () => {
    const startDate = new Date('2024-01-01T10:00:00Z');
    const markers = createStartEndMarkers(startDate, null, 1.1);

    expect(markers).toHaveLength(1);
    expect(markers[0].id).toBe('start');
  });

  it('should not create end marker if endPrice is undefined', () => {
    const startDate = new Date('2024-01-01T10:00:00Z');
    const endDate = new Date('2024-01-01T12:00:00Z');
    const markers = createStartEndMarkers(startDate, endDate, 1.1, undefined);

    expect(markers).toHaveLength(1);
    expect(markers[0].id).toBe('start');
  });
});

describe('createVerticalLine', () => {
  it('should create vertical line with default values', () => {
    const date = new Date('2024-01-01T10:00:00Z');
    const line = createVerticalLine(date, 'Start', '#ff0000');

    expect(line.date).toEqual(date);
    expect(line.label).toBe('Start');
    expect(line.color).toBe('#ff0000');
    expect(line.strokeWidth).toBe(2);
    expect(line.labelPosition).toBe('top');
    expect(line.strokeDasharray).toBeUndefined();
  });

  it('should create vertical line with custom values', () => {
    const date = new Date('2024-01-01T10:00:00Z');
    const line = createVerticalLine(date, 'End', '#00ff00', 3, '5,5');

    expect(line.strokeWidth).toBe(3);
    expect(line.strokeDasharray).toBe('5,5');
  });
});

describe('createHorizontalLine', () => {
  it('should create horizontal line with default values', () => {
    const line = createHorizontalLine(1.1, 'Support', '#0000ff');

    expect(line.price).toBe(1.1);
    expect(line.label).toBe('Support');
    expect(line.color).toBe('#0000ff');
    expect(line.strokeWidth).toBe(1);
    expect(line.strokeDasharray).toBe('5,5');
  });

  it('should create horizontal line with custom values', () => {
    const line = createHorizontalLine(1.2, 'Resistance', '#ff00ff', 2, '10,5');

    expect(line.strokeWidth).toBe(2);
    expect(line.strokeDasharray).toBe('10,5');
  });
});

describe('createStrategyEventMarkers', () => {
  it('should create markers from strategy events', () => {
    const events: StrategyEvent[] = [
      {
        id: 1,
        strategy_name: 'MA Crossover',
        event_type: 'SIGNAL',
        timestamp: '2024-01-01T10:00:00Z',
        instrument: 'EUR_USD',
        price: 1.1,
        message: 'Buy signal detected',
      },
      {
        id: 2,
        strategy_name: 'MA Crossover',
        event_type: 'ORDER',
        timestamp: '2024-01-01T10:05:00Z',
        instrument: 'EUR_USD',
        price: 1.105,
        message: 'Order placed',
      },
    ];

    const markers = createStrategyEventMarkers(events);

    expect(markers).toHaveLength(2);
    expect(markers[0].id).toBe('event-1');
    expect(markers[0].date).toEqual(new Date('2024-01-01T10:00:00Z'));
    expect(markers[0].price).toBe(1.1);
    expect(markers[0].type).toBe('info');
    expect(markers[0].color).toBe('#2196f3'); // Blue for SIGNAL
    expect(markers[0].label).toBe('SIGNAL');
    expect(markers[0].tooltip).toBe('MA Crossover: Buy signal detected');
    expect(markers[0].strategyEvent).toEqual(events[0]);
  });

  it('should filter out events without price', () => {
    const events: StrategyEvent[] = [
      {
        id: 1,
        strategy_name: 'Test',
        event_type: 'ERROR',
        timestamp: '2024-01-01T10:00:00Z',
        message: 'Error occurred',
      },
      {
        id: 2,
        strategy_name: 'Test',
        event_type: 'SIGNAL',
        timestamp: '2024-01-01T10:05:00Z',
        price: 1.1,
        message: 'Signal detected',
      },
    ];

    const markers = createStrategyEventMarkers(events);

    expect(markers).toHaveLength(1);
    expect(markers[0].id).toBe('event-2');
  });

  it('should handle empty events array', () => {
    const markers = createStrategyEventMarkers([]);
    expect(markers).toEqual([]);
  });

  it('should use correct colors for different event types', () => {
    const events: StrategyEvent[] = [
      {
        id: 1,
        strategy_name: 'Test',
        event_type: 'SIGNAL',
        timestamp: '2024-01-01T10:00:00Z',
        price: 1.1,
        message: 'Signal',
      },
      {
        id: 2,
        strategy_name: 'Test',
        event_type: 'ORDER',
        timestamp: '2024-01-01T10:00:00Z',
        price: 1.1,
        message: 'Order',
      },
      {
        id: 3,
        strategy_name: 'Test',
        event_type: 'POSITION',
        timestamp: '2024-01-01T10:00:00Z',
        price: 1.1,
        message: 'Position',
      },
      {
        id: 4,
        strategy_name: 'Test',
        event_type: 'ERROR',
        timestamp: '2024-01-01T10:00:00Z',
        price: 1.1,
        message: 'Error',
      },
      {
        id: 5,
        strategy_name: 'Test',
        event_type: 'FLOOR_LEVEL',
        timestamp: '2024-01-01T10:00:00Z',
        price: 1.1,
        message: 'Floor',
      },
      {
        id: 6,
        strategy_name: 'Test',
        event_type: 'CUSTOM',
        timestamp: '2024-01-01T10:00:00Z',
        price: 1.1,
        message: 'Custom',
      },
    ];

    const markers = createStrategyEventMarkers(events);

    expect(markers[0].color).toBe('#2196f3'); // Blue for SIGNAL
    expect(markers[1].color).toBe('#4caf50'); // Green for ORDER
    expect(markers[2].color).toBe('#ff9800'); // Orange for POSITION
    expect(markers[3].color).toBe('#f44336'); // Red for ERROR
    expect(markers[4].color).toBe('#9c27b0'); // Purple for FLOOR_LEVEL
    expect(markers[5].color).toBe('#607d8b'); // Blue Gray for CUSTOM
  });
});
