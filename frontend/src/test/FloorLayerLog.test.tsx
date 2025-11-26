/**
 * Unit Tests for FloorLayerLog Component
 *
 * Tests component rendering, event type display, conditional fields,
 * calculations, and user interactions.
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { FloorLayerLog } from '../components/backtest/FloorLayerLog';
import type { Trade, StrategyEvent } from '../types/execution';

describe('FloorLayerLog Component', () => {
  const mockTrades: Trade[] = [
    {
      entry_time: '2024-01-15T10:00:00Z',
      exit_time: '2024-01-15T11:00:00Z',
      instrument: 'USD_JPY',
      direction: 'long',
      units: 1000,
      entry_price: 149.5,
      exit_price: 149.75,
      pnl: 250.0,
      layer_number: 1,
      is_first_lot: true,
      retracement_count: 0,
    },
    {
      entry_time: '2024-01-15T10:30:00Z',
      exit_time: '2024-01-15T11:30:00Z',
      instrument: 'USD_JPY',
      direction: 'long',
      units: 1500,
      entry_price: 149.3,
      exit_price: 149.75,
      pnl: 675.0,
      layer_number: 1,
      is_first_lot: false,
      retracement_count: 1,
    },
  ];

  const mockStrategyEvents: StrategyEvent[] = [
    {
      event_type: 'initial',
      timestamp: '2024-01-15T10:00:00Z',
      layer_number: 1,
      retracement_count: 0,
      direction: 'long',
      units: 1000,
      entry_price: 149.5,
    },
    {
      event_type: 'retracement',
      timestamp: '2024-01-15T10:30:00Z',
      layer_number: 1,
      retracement_count: 1,
      direction: 'long',
      units: 1500,
      entry_price: 149.3,
    },
    {
      event_type: 'take_profit',
      timestamp: '2024-01-15T11:00:00Z',
      layer_number: 1,
      retracement_count: 0,
      direction: 'long',
      units: 1000,
      entry_price: 149.5,
      exit_price: 149.75,
      pnl: 250.0,
    },
  ];

  it('renders with strategy events', () => {
    render(<FloorLayerLog trades={[]} strategyEvents={mockStrategyEvents} />);

    expect(
      screen.getByText('Floor Strategy - Layer & Retracement Log')
    ).toBeInTheDocument();
    expect(screen.getByText('Layer 1')).toBeInTheDocument();
  });

  it('displays event type column correctly', () => {
    render(<FloorLayerLog trades={[]} strategyEvents={mockStrategyEvents} />);

    // Check for event type chips
    expect(screen.getByText('Initial')).toBeInTheDocument();
    expect(screen.getByText('Retracement')).toBeInTheDocument();
    expect(screen.getByText('Take Profit')).toBeInTheDocument();
  });

  it('shows Exit Price only for close events', () => {
    const { container } = render(
      <FloorLayerLog trades={[]} strategyEvents={mockStrategyEvents} />
    );

    const rows = Array.from(container.querySelectorAll('tbody tr')).filter(
      (row) => !row.textContent?.includes('Total')
    );

    // Initial event (row 0) - Exit Price should be dash
    const initialRow = rows[0];
    const initialCells = initialRow.querySelectorAll('td');
    expect(initialCells[5].textContent).toBe('-');

    // Retracement event (row 1) - Exit Price should be dash
    const retracementRow = rows[1];
    const retracementCells = retracementRow.querySelectorAll('td');
    expect(retracementCells[5].textContent).toBe('-');

    // Take Profit event (row 2) - Exit Price should be shown
    const takeProfitRow = rows[2];
    const takeProfitCells = takeProfitRow.querySelectorAll('td');
    expect(takeProfitCells[5].textContent).not.toBe('-');
    expect(takeProfitCells[5].textContent).toContain('149.75');
  });

  it('shows P&L only for close events', () => {
    const { container } = render(
      <FloorLayerLog trades={[]} strategyEvents={mockStrategyEvents} />
    );

    const rows = Array.from(container.querySelectorAll('tbody tr')).filter(
      (row) => !row.textContent?.includes('Total')
    );

    // Initial event - P&L should be dash
    const initialRow = rows[0];
    const initialCells = initialRow.querySelectorAll('td');
    expect(initialCells[6].textContent).toBe('-');

    // Retracement event - P&L should be dash
    const retracementRow = rows[1];
    const retracementCells = retracementRow.querySelectorAll('td');
    expect(retracementCells[6].textContent).toBe('-');

    // Take Profit event - P&L should be shown
    const takeProfitRow = rows[2];
    const takeProfitCells = takeProfitRow.querySelectorAll('td');
    expect(takeProfitCells[6].textContent).not.toBe('-');
    expect(takeProfitCells[6].textContent).toContain('$250.00');
  });

  it('calculates total P&L correctly', () => {
    const { container } = render(
      <FloorLayerLog trades={[]} strategyEvents={mockStrategyEvents} />
    );

    const totalRow = Array.from(container.querySelectorAll('tbody tr')).find(
      (row) => row.textContent?.includes('Layer 1 Total')
    );

    expect(totalRow).toBeTruthy();
    const totalCell = totalRow!.querySelectorAll('td')[1];
    expect(totalCell.textContent).toContain('$250.00');
  });

  it('displays Time column with correct timestamps', () => {
    const { container } = render(
      <FloorLayerLog trades={[]} strategyEvents={mockStrategyEvents} />
    );

    // Check that Time column header exists
    expect(screen.getByText('Time')).toBeInTheDocument();

    const rows = Array.from(container.querySelectorAll('tbody tr')).filter(
      (row) => !row.textContent?.includes('Total')
    );

    // Each row should have a timestamp in the Time column
    rows.forEach((row) => {
      const cells = row.querySelectorAll('td');
      const timeCell = cells[1];
      expect(timeCell.textContent).not.toBe('');
      expect(timeCell.textContent).not.toBe('-');
    });
  });

  it('displays blank retracement when value is 0', () => {
    const { container } = render(
      <FloorLayerLog trades={[]} strategyEvents={mockStrategyEvents} />
    );

    const rows = Array.from(container.querySelectorAll('tbody tr')).filter(
      (row) => !row.textContent?.includes('Total')
    );

    // Initial event has retracement_count = 0, should be blank
    const initialRow = rows[0];
    const initialCells = initialRow.querySelectorAll('td');
    expect(initialCells[7].textContent).toBe('');

    // Retracement event has retracement_count = 1, should show number
    const retracementRow = rows[1];
    const retracementCells = retracementRow.querySelectorAll('td');
    expect(retracementCells[7].textContent).toBe('1');
  });

  it('handles empty state correctly', () => {
    render(<FloorLayerLog trades={[]} strategyEvents={[]} />);

    expect(
      screen.getByText(/No floor\/layer data available/)
    ).toBeInTheDocument();
  });

  it('groups events by layer', () => {
    const multiLayerEvents: StrategyEvent[] = [
      {
        event_type: 'initial',
        timestamp: '2024-01-15T10:00:00Z',
        layer_number: 1,
        retracement_count: 0,
        direction: 'long',
        units: 1000,
        entry_price: 149.5,
      },
      {
        event_type: 'initial',
        timestamp: '2024-01-15T10:05:00Z',
        layer_number: 2,
        retracement_count: 0,
        direction: 'long',
        units: 1000,
        entry_price: 149.0,
      },
    ];

    render(<FloorLayerLog trades={[]} strategyEvents={multiLayerEvents} />);

    expect(screen.getByText('Layer 1')).toBeInTheDocument();
    expect(screen.getByText('Layer 2')).toBeInTheDocument();
  });

  it('displays event count per layer', () => {
    render(<FloorLayerLog trades={[]} strategyEvents={mockStrategyEvents} />);

    // All 3 events are in layer 1
    expect(screen.getByText('3 events')).toBeInTheDocument();
  });

  it('renders with both trades and strategy events', () => {
    render(
      <FloorLayerLog trades={mockTrades} strategyEvents={mockStrategyEvents} />
    );

    // Should render successfully with both data sources
    expect(
      screen.getByText('Floor Strategy - Layer & Retracement Log')
    ).toBeInTheDocument();
  });
});
