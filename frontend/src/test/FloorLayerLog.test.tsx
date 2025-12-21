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
      event_type: 'retracement',
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
    // Layer column should show layer number for each event
    expect(
      screen.getByRole('columnheader', { name: /Layer/i })
    ).toBeInTheDocument();
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

    // Get table rows (excluding Total row)
    const rows = Array.from(container.querySelectorAll('tbody tr')).filter(
      (row) => !row.textContent?.includes('Total')
    );

    // The component shows entry_price for entry events and exit_price for close events in the Price column (index 6, after Layer column)
    // Initial Entry event - should show entry price
    const initialRow = rows[0];
    const initialCells = initialRow?.querySelectorAll('td');
    expect(initialCells?.[6]?.textContent).toContain('149.5');

    // Take Profit event (row 2) - should show exit price
    const takeProfitRow = rows[2];
    const takeProfitCells = takeProfitRow?.querySelectorAll('td');
    expect(takeProfitCells?.[6]?.textContent).toContain('149.75');
  });

  it('shows P&L only for close events', () => {
    const { container } = render(
      <FloorLayerLog trades={[]} strategyEvents={mockStrategyEvents} />
    );

    const rows = Array.from(container.querySelectorAll('tbody tr')).filter(
      (row) => !row.textContent?.includes('Total')
    );

    // Initial Entry event - P&L should be dash (column index 7, after Layer column)
    const initialRow = rows[0];
    const initialCells = initialRow?.querySelectorAll('td');
    expect(initialCells?.[7]?.textContent).toBe('-');

    // Add Layer event - P&L should be dash
    const scaleInRow = rows[1];
    const scaleInCells = scaleInRow?.querySelectorAll('td');
    expect(scaleInCells?.[7]?.textContent).toBe('-');

    // Take Profit event - P&L should be shown
    const takeProfitRow = rows[2];
    const takeProfitCells = takeProfitRow?.querySelectorAll('td');
    expect(takeProfitCells?.[7]?.textContent).toContain('250.00');
  });

  it('renders retracement column before units', () => {
    render(<FloorLayerLog trades={[]} strategyEvents={mockStrategyEvents} />);

    const headerCells = Array.from(document.querySelectorAll('thead th')).map(
      (cell) => cell.textContent?.replace(/\s+/g, ' ').trim() || ''
    );

    const layerIndex = headerCells.findIndex((text) => text.includes('Layer'));
    const retracementIndex = headerCells.findIndex((text) =>
      text.includes('Retracement')
    );
    const unitsIndex = headerCells.findIndex((text) => text.includes('Units'));

    expect(layerIndex).toBeGreaterThan(-1);
    expect(retracementIndex).toBeGreaterThan(-1);
    expect(unitsIndex).toBeGreaterThan(retracementIndex);
  });

  it('calculates total P&L correctly', () => {
    const { container } = render(
      <FloorLayerLog trades={[]} strategyEvents={mockStrategyEvents} />
    );

    const totalRow = Array.from(container.querySelectorAll('tbody tr')).find(
      (row) => row.textContent?.includes('Total')
    );

    expect(totalRow).toBeTruthy();
    // Total P&L should be displayed in the header and in the total row
    expect(screen.getByText(/Total P&L:/)).toBeInTheDocument();
    // Total row shows P&L value
    expect(totalRow!.textContent).toContain('250.00');
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

  it('displays Layer column with layer numbers', () => {
    const { container } = render(
      <FloorLayerLog trades={[]} strategyEvents={mockStrategyEvents} />
    );

    // Check that Layer column header exists
    expect(
      screen.getByRole('columnheader', { name: /Layer/i })
    ).toBeInTheDocument();

    const rows = Array.from(container.querySelectorAll('tbody tr')).filter(
      (row) => !row.textContent?.includes('Total')
    );

    // Each row should have layer number in the Layer column (index 2)
    rows.forEach((row) => {
      const cells = row.querySelectorAll('td');
      const layerCell = cells[2];
      expect(layerCell?.textContent).toContain('1');
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

  it('shows events from multiple layers in a single table', () => {
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

    const { container } = render(
      <FloorLayerLog trades={[]} strategyEvents={multiLayerEvents} />
    );

    // Both events should be in a single table (no accordions)
    const tables = container.querySelectorAll('table');
    expect(tables.length).toBe(1);

    // Both layer numbers should appear in the Layer column
    const rows = Array.from(container.querySelectorAll('tbody tr')).filter(
      (row) => !row.textContent?.includes('Total')
    );
    expect(rows.length).toBe(2);

    // Check layer column values
    const layer1Row = rows[0];
    const layer2Row = rows[1];
    expect(layer1Row?.querySelectorAll('td')[2]?.textContent).toContain('1');
    expect(layer2Row?.querySelectorAll('td')[2]?.textContent).toContain('2');
  });

  it('can sort by layer column', () => {
    render(<FloorLayerLog trades={[]} strategyEvents={mockStrategyEvents} />);

    // Layer column header should be sortable
    const layerHeader = screen.getByRole('columnheader', { name: /Layer/i });
    expect(
      layerHeader.querySelector('span.MuiTableSortLabel-root')
    ).toBeInTheDocument();
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
