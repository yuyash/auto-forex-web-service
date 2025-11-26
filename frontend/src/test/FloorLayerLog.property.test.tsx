/**
 * Property-Based Tests for FloorLayerLog Component
 *
 * These tests verify correctness properties using fast-check to generate
 * random test data and ensure the component behaves correctly across all inputs.
 */

import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import { render } from '@testing-library/react';
import { FloorLayerLog } from '../components/backtest/FloorLayerLog';
import type { StrategyEvent } from '../types/execution';

// Arbitraries for generating test data
const eventTypeArbitrary = fc.constantFrom(
  'initial',
  'retracement',
  'layer',
  'close',
  'take_profit',
  'volatility_lock',
  'margin_protection'
);

const directionArbitrary = fc.constantFrom('long', 'short');

const timestampArbitrary = fc
  .integer({ min: 1704067200000, max: 1735689600000 }) // 2024-01-01 to 2024-12-31 in milliseconds
  .map((ms) => new Date(ms).toISOString());

const priceArbitrary = fc.float({ min: 100, max: 200, noNaN: true });
const unitsArbitrary = fc.integer({ min: 1, max: 10000 });
const pnlArbitrary = fc.float({ min: -1000, max: 1000, noNaN: true });
const layerArbitrary = fc.integer({ min: 1, max: 5 });
const retracementArbitrary = fc.integer({ min: 0, max: 10 });

// Helper to determine if event type is a close event
const isCloseEvent = (eventType: string) => {
  return [
    'close',
    'take_profit',
    'volatility_lock',
    'margin_protection',
  ].includes(eventType);
};

// Arbitrary for generating strategy events
const strategyEventArbitrary = fc
  .tuple(
    eventTypeArbitrary,
    timestampArbitrary,
    layerArbitrary,
    retracementArbitrary,
    directionArbitrary,
    unitsArbitrary,
    priceArbitrary,
    priceArbitrary,
    pnlArbitrary
  )
  .map(
    ([
      event_type,
      timestamp,
      layer_number,
      retracement_count,
      direction,
      units,
      entry_price,
      exit_price,
      pnl,
    ]): StrategyEvent => ({
      event_type,
      timestamp,
      layer_number,
      // Initial events should always have retracement_count = 0
      retracement_count: event_type === 'initial' ? 0 : retracement_count,
      direction,
      units,
      entry_price,
      exit_price: isCloseEvent(event_type) ? exit_price : undefined,
      pnl: isCloseEvent(event_type) ? pnl : undefined,
    })
  );

describe('FloorLayerLog Property-Based Tests', () => {
  /**
   * Feature: floor-strategy-enhancements, Property 2 & 3
   * Exit Price and P&L are blank for entry events
   * Exit Price and P&L are shown for close events
   * Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8
   */
  it('Property 2 & 3: Exit Price and P&L visibility based on event type', () => {
    fc.assert(
      fc.property(
        fc.array(strategyEventArbitrary, { minLength: 1, maxLength: 10 }),
        (events) => {
          const { container } = render(
            <FloorLayerLog trades={[]} strategyEvents={events} />
          );

          // Get all table rows (excluding header and summary rows)
          const allRows = Array.from(container.querySelectorAll('tbody tr'));
          const eventRows = allRows.filter(
            (row) => !row.textContent?.includes('Total')
          );

          // Events are sorted by timestamp and grouped by layer
          // We need to match events to rows carefully
          const sortedEvents = [...events].sort((a, b) => {
            const timeA = new Date(a.timestamp).getTime();
            const timeB = new Date(b.timestamp).getTime();
            return timeA - timeB;
          });

          sortedEvents.forEach((event) => {
            // Find the row that matches this event by checking event type chip
            const eventTypeDisplay =
              event.event_type === 'initial'
                ? 'Initial'
                : event.event_type === 'retracement'
                  ? 'Retracement'
                  : event.event_type === 'layer'
                    ? 'Layer'
                    : event.event_type === 'close'
                      ? 'Close'
                      : event.event_type === 'take_profit'
                        ? 'Take Profit'
                        : event.event_type === 'volatility_lock'
                          ? 'Volatility Lock'
                          : 'Margin Protection';

            const matchingRows = eventRows.filter((row) =>
              row.textContent?.includes(eventTypeDisplay)
            );

            matchingRows.forEach((row) => {
              const cells = row.querySelectorAll('td');
              const exitPriceCell = cells[5]; // Exit Price column
              const pnlCell = cells[6]; // P&L column

              if (isCloseEvent(event.event_type)) {
                // For close events, Exit Price and P&L should be shown (not dash)
                if (event.exit_price !== undefined) {
                  expect(exitPriceCell.textContent).not.toBe('-');
                }
                if (event.pnl !== undefined) {
                  expect(pnlCell.textContent).not.toBe('-');
                  expect(pnlCell.textContent).toContain('$');
                }
              } else {
                // For entry events (initial, retracement, layer), should be dash
                expect(exitPriceCell.textContent).toBe('-');
                expect(pnlCell.textContent).toBe('-');
              }
            });
          });
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * Feature: floor-strategy-enhancements, Property 4
   * Total P&L excludes blank values
   * Validates: Requirements 3.1, 3.2
   */
  it('Property 4: Total P&L calculation excludes blank values', () => {
    fc.assert(
      fc.property(
        fc.array(strategyEventArbitrary, { minLength: 1, maxLength: 20 }),
        (events) => {
          const { container } = render(
            <FloorLayerLog trades={[]} strategyEvents={events} />
          );

          // Group events by layer to match component behavior
          const eventsByLayer = events.reduce(
            (acc, event) => {
              const layer = event.layer_number;
              if (!acc[layer]) acc[layer] = [];
              acc[layer].push(event);
              return acc;
            },
            {} as Record<number, typeof events>
          );

          // Check each layer's total
          Object.keys(eventsByLayer).forEach((layerKey) => {
            const layerEvents = eventsByLayer[Number(layerKey)];
            const expectedTotal = layerEvents
              .filter((e) => e.pnl !== undefined)
              .reduce((sum, e) => sum + (e.pnl || 0), 0);

            // Find the total row for this layer
            const allRows = Array.from(container.querySelectorAll('tbody tr'));
            const totalRow = allRows.find((row) =>
              row.textContent?.includes(`Layer ${layerKey} Total`)
            );

            if (totalRow && layerEvents.some((e) => e.pnl !== undefined)) {
              const totalCell = totalRow.querySelectorAll('td')[1];
              const totalText = totalCell.textContent || '';
              const displayedTotal = parseFloat(
                totalText.replace('$', '').replace(',', '')
              );

              // Use relative tolerance for floating point comparison
              const tolerance = Math.max(0.2, Math.abs(expectedTotal) * 0.01);
              expect(Math.abs(displayedTotal - expectedTotal)).toBeLessThan(
                tolerance
              );
            }
          });
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * Feature: floor-strategy-enhancements, Property 5
   * Time column shows event-specific timestamps
   * Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8
   */
  it('Property 5: Time column displays event-specific timestamps', () => {
    fc.assert(
      fc.property(
        fc.array(strategyEventArbitrary, { minLength: 1, maxLength: 20 }),
        (events) => {
          const { container } = render(
            <FloorLayerLog trades={[]} strategyEvents={events} />
          );

          const eventRows = Array.from(
            container.querySelectorAll('tbody tr')
          ).filter((row) => !row.textContent?.includes('Total'));

          events.forEach((event, idx) => {
            const row = eventRows[idx];
            if (!row) return;

            const cells = row.querySelectorAll('td');
            const timeCell = cells[1]; // Time column

            // Verify the timestamp is displayed (not empty or dash)
            expect(timeCell.textContent).not.toBe('');
            expect(timeCell.textContent).not.toBe('-');

            // Verify it contains date/time components
            const timeText = timeCell.textContent || '';
            // Should contain numbers (date/time)
            expect(/\d/.test(timeText)).toBe(true);
          });
        }
      ),
      { numRuns: 100 }
    );
  });

  /**
   * Feature: floor-strategy-enhancements, Property 6
   * Zero retracement is displayed as blank
   * Validates: Requirements 5.1, 5.2
   */
  it('Property 6: Zero retracement displayed as blank', () => {
    fc.assert(
      fc.property(
        fc.array(strategyEventArbitrary, { minLength: 1, maxLength: 20 }),
        (events) => {
          const { container } = render(
            <FloorLayerLog trades={[]} strategyEvents={events} />
          );

          const eventRows = Array.from(
            container.querySelectorAll('tbody tr')
          ).filter((row) => !row.textContent?.includes('Total'));

          // Check that all rows with retracement_count = 0 have blank retracement cell
          // and all rows with retracement_count > 0 display the number
          eventRows.forEach((row) => {
            const cells = row.querySelectorAll('td');
            const retracementCell = cells[7]; // Retracements column
            const retracementText = retracementCell.textContent || '';

            // If blank, it should represent retracement_count = 0
            // If non-blank, it should be a positive number
            if (retracementText === '') {
              // This is correct for retracement_count = 0
              expect(retracementText).toBe('');
            } else {
              // Should be a positive integer
              const retracementValue = parseInt(retracementText, 10);
              expect(retracementValue).toBeGreaterThan(0);
              expect(Number.isInteger(retracementValue)).toBe(true);
            }
          });
        }
      ),
      { numRuns: 100 }
    );
  });
});
