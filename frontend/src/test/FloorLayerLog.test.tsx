/**
 * Unit Tests for FloorLayerLog Component
 *
 * Tests component rendering, event type display, conditional fields,
 * calculations, and user interactions.
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { FloorLayerLog } from '../components/backtest/FloorLayerLog';
import type { Trade, BacktestStrategyEvent } from '../types/execution';

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
      entry_retracement_count: 0,
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
      entry_retracement_count: 1,
    },
  ];

  const mockStrategyEvents: BacktestStrategyEvent[] = [
    {
      event_type: 'initial_entry',
      timestamp: '2024-01-15T10:00:00Z',
      description: 'Initial LONG entry @ 149.50000',
      details: {
        layer: 1,
        retracement_count: 0,
        direction: 'long',
        units: 1000,
        entry_price: 149.5,
        entry_retracement_count: 0,
      },
    },
    {
      event_type: 'scale_in',
      timestamp: '2024-01-15T10:30:00Z',
      description: 'Retracement LONG entry @ 149.30000',
      details: {
        layer: 1,
        retracement_count: 1,
        direction: 'long',
        units: 1500,
        entry_price: 149.3,
        entry_retracement_count: 1,
      },
    },
    {
      event_type: 'take_profit',
      timestamp: '2024-01-15T11:00:00Z',
      description:
        'Take Profit: LONG 1000 units closed @ 149.75000 | P&L: 250.00',
      details: {
        layer: 1,
        retracement_count: 0,
        direction: 'long',
        units: 1000,
        entry_price: 149.5,
        exit_price: 149.75,
        pnl: 250.0,
        entry_retracement_count: 1,
      },
    },
  ];

  it('renders with strategy events', () => {
    render(<FloorLayerLog trades={[]} strategyEvents={mockStrategyEvents} />);

    expect(
      screen.getByText('Floor Strategy Execution Log')
    ).toBeInTheDocument();
    expect(screen.getByText('Layer 1')).toBeInTheDocument();
  });

  it('displays event type column correctly', () => {
    render(<FloorLayerLog trades={[]} strategyEvents={mockStrategyEvents} />);

    // Check for event type chips with new labels
    expect(screen.getByText('Initial Entry')).toBeInTheDocument();
    expect(screen.getByText('Retracement')).toBeInTheDocument();
    expect(screen.getByText('Take Profit')).toBeInTheDocument();
  });

  it('shows Exit Price only for close events', () => {
    const { container } = render(
      <FloorLayerLog trades={[]} strategyEvents={mockStrategyEvents} />
    );

    // Expand accordion to see table rows
    const rows = Array.from(container.querySelectorAll('tbody tr')).filter(
      (row) => !row.textContent?.includes('Total')
    );

    // The component shows entry_price for entry events and exit_price for close events in the Price column (index 5)
    // Initial Entry event - should show entry price
    const initialRow = rows[0];
    const initialCells = initialRow?.querySelectorAll('td');
    expect(initialCells?.[5]?.textContent).toContain('149.5');

    // Take Profit event (row 2) - should show exit price
    const takeProfitRow = rows[2];
    const takeProfitCells = takeProfitRow?.querySelectorAll('td');
    expect(takeProfitCells?.[5]?.textContent).toContain('149.75');
  });

  it('shows P&L only for close events', () => {
    const { container } = render(
      <FloorLayerLog trades={[]} strategyEvents={mockStrategyEvents} />
    );

    const rows = Array.from(container.querySelectorAll('tbody tr')).filter(
      (row) => !row.textContent?.includes('Total')
    );

    // Initial Entry event - P&L should be dash (column index 6)
    const initialRow = rows[0];
    const initialCells = initialRow?.querySelectorAll('td');
    expect(initialCells?.[6]?.textContent).toBe('-');

    // Add Layer event - P&L should be dash
    const scaleInRow = rows[1];
    const scaleInCells = scaleInRow?.querySelectorAll('td');
    expect(scaleInCells?.[6]?.textContent).toBe('-');

    // Take Profit event - P&L should be shown
    const takeProfitRow = rows[2];
    const takeProfitCells = takeProfitRow?.querySelectorAll('td');
    expect(takeProfitCells?.[6]?.textContent).toContain('250.00');
  });

  it('renders retracement column before units', () => {
    render(<FloorLayerLog trades={[]} strategyEvents={mockStrategyEvents} />);

    const headerCells = Array.from(document.querySelectorAll('thead th')).map(
      (cell) => cell.textContent?.replace(/\s+/g, ' ').trim() || ''
    );

    const retracementIndex = headerCells.findIndex((text) =>
      text.includes('Retracement')
    );
    const unitsIndex = headerCells.findIndex((text) => text.includes('Units'));

    expect(retracementIndex).toBeGreaterThan(-1);
    expect(unitsIndex).toBeGreaterThan(retracementIndex);
  });

  it('calculates total P&L correctly', () => {
    const { container } = render(
      <FloorLayerLog trades={[]} strategyEvents={mockStrategyEvents} />
    );

    const totalRow = Array.from(container.querySelectorAll('tbody tr')).find(
      (row) => row.textContent?.includes('Layer 1 Total')
    );

    expect(totalRow).toBeTruthy();
    // Total row has colSpan=6 on first cell, so P&L is in index 1
    const totalCell = totalRow!.querySelectorAll('td')[1];
    expect(totalCell.textContent).toContain('250.00');
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

    // Each row should have a timestamp in the Time column (index 1)
    rows.forEach((row) => {
      const cells = row.querySelectorAll('td');
      const timeCell = cells[1];
      expect(timeCell?.textContent).not.toBe('');
      expect(timeCell?.textContent).not.toBe('-');
    });
  });

  it('displays retracement info in details column', () => {
    const { container } = render(
      <FloorLayerLog trades={[]} strategyEvents={mockStrategyEvents} />
    );

    const rows = Array.from(container.querySelectorAll('tbody tr')).filter(
      (row) => !row.textContent?.includes('Total')
    );

    // Add Layer event has retracement_count = 1, should show in details
    const scaleInRow = rows[1];
    expect(scaleInRow?.textContent).toContain('Retracement #1');
    const takeProfitRow = rows[2];
    expect(takeProfitRow?.textContent).toContain('Remaining Retracements: 0');
  });

  it('handles empty state correctly', () => {
    render(<FloorLayerLog trades={[]} strategyEvents={[]} />);

    expect(
      screen.getByText('No floor strategy events available for this backtest.')
    ).toBeInTheDocument();
  });

  it('groups events by layer', () => {
    const multiLayerEvents: BacktestStrategyEvent[] = [
      {
        event_type: 'initial_entry',
        timestamp: '2024-01-15T10:00:00Z',
        description: 'Initial LONG entry @ 149.50000',
        details: {
          layer: 1,
          retracement_count: 0,
          direction: 'long',
          units: 1000,
          entry_price: 149.5,
        },
      },
      {
        event_type: 'initial_entry',
        timestamp: '2024-01-15T10:05:00Z',
        description: 'Initial LONG entry @ 149.00000',
        details: {
          layer: 2,
          retracement_count: 0,
          direction: 'long',
          units: 1000,
          entry_price: 149.0,
        },
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
      screen.getByText('Floor Strategy Execution Log')
    ).toBeInTheDocument();
  });
});
