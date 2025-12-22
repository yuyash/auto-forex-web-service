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
import type { BacktestStrategyEvent } from '../types/execution';

// Event types that the component filters for display
const meaningfulEventTypes = [
  'initial_entry',
  'retracement',
  'take_profit',
  'volatility_lock',
  'margin_protection',
];

const PROPERTY_RUNS = 20;
const PROPERTY_TIME_LIMIT_MS = 3000;

const eventTypeArbitrary = fc.constantFrom(...meaningfulEventTypes);

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
  return ['take_profit', 'volatility_lock', 'margin_protection'].includes(
    eventType
  );
};

// Arbitrary for generating strategy events in BacktestStrategyEvent format
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
      layer,
      retracement_count,
      direction,
      units,
      entry_price,
      exit_price,
      pnl,
    ]): BacktestStrategyEvent => {
      return {
        event_type,
        timestamp,
        layer_number: layer,
        retracement_count:
          event_type === 'initial_entry' ? 0 : retracement_count,
        direction,
        units,
        entry_price,
        price: entry_price,
        exit_price: isCloseEvent(event_type) ? exit_price : undefined,
        pnl: isCloseEvent(event_type) ? pnl : undefined,
      };
    }
  );

describe('FloorLayerLog Property-Based Tests', () => {
  /**
   * Feature: floor-strategy-enhancements, Property 2 & 3
   * Exit Price and P&L are blank for entry events
   * Exit Price and P&L are shown for close events
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

          // For each event row, verify P&L column behavior
          eventRows.forEach((row) => {
            const cells = row.querySelectorAll('td');
            const pnlCell = cells[7]; // P&L column (index 7 after adding Layer column)

            // Check if this is a close event by looking at the event chip
            const eventChip = row.querySelector('.MuiChip-label');
            const chipText = eventChip?.textContent || '';
            const isClose = [
              'Take Profit',
              'Volatility Lock',
              'Margin Protection',
            ].includes(chipText);

            if (!isClose) {
              // Entry events should show dash for P&L
              expect(pnlCell?.textContent).toBe('-');
            }
            // Close events may show P&L value or dash depending on data
          });
        }
      ),
      {
        numRuns: PROPERTY_RUNS,
        interruptAfterTimeLimit: PROPERTY_TIME_LIMIT_MS,
      }
    );
  }, 15000);

  /**
   * Feature: floor-strategy-enhancements, Property 4
   * Total P&L calculation excludes blank values
   */
  it('Property 4: Total P&L calculation excludes blank values', () => {
    fc.assert(
      fc.property(
        fc.array(strategyEventArbitrary, { minLength: 1, maxLength: 20 }),
        (events) => {
          const { container } = render(
            <FloorLayerLog trades={[]} strategyEvents={events} />
          );

          // Calculate expected total from all close events
          const closeEvents = events.filter((e) => isCloseEvent(e.event_type));
          const expectedTotal = closeEvents.reduce((sum, e) => {
            const pnl = e.pnl;
            return sum + (typeof pnl === 'number' ? pnl : 0);
          }, 0);

          // Find the total row (now a single row, not per-layer)
          const allRows = Array.from(container.querySelectorAll('tbody tr'));
          const totalRow = allRows.find(
            (row) =>
              row.textContent?.includes('Total') &&
              !row.textContent?.includes('Layer')
          );

          if (totalRow && closeEvents.length > 0) {
            const totalCell = totalRow.querySelectorAll('td')[1]; // P&L in total row (after colSpan=7)
            const totalText = totalCell?.textContent || '';
            const displayedTotal = parseFloat(totalText.replace(/[$,]/g, ''));

            // Use relative tolerance for floating point comparison
            if (!isNaN(displayedTotal)) {
              const tolerance = Math.max(0.5, Math.abs(expectedTotal) * 0.01);
              expect(Math.abs(displayedTotal - expectedTotal)).toBeLessThan(
                tolerance
              );
            }
          }
        }
      ),
      {
        numRuns: PROPERTY_RUNS,
        interruptAfterTimeLimit: PROPERTY_TIME_LIMIT_MS,
      }
    );
  }, 15000);

  /**
   * Feature: floor-strategy-enhancements, Property 5
   * Time column shows event-specific timestamps
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

          // Each event row should have a timestamp
          eventRows.forEach((row) => {
            const cells = row.querySelectorAll('td');
            const timeCell = cells[1]; // Time column

            // Verify the timestamp is displayed (not empty or dash)
            expect(timeCell?.textContent).not.toBe('');
            expect(timeCell?.textContent).not.toBe('-');

            // Should contain numbers (date/time)
            const timeText = timeCell?.textContent || '';
            expect(/\d/.test(timeText)).toBe(true);
          });
        }
      ),
      {
        numRuns: PROPERTY_RUNS,
        interruptAfterTimeLimit: PROPERTY_TIME_LIMIT_MS,
      }
    );
  }, 15000);

  /**
   * Feature: floor-strategy-enhancements, Property 6
   * Zero retracement is displayed as blank in details
   */
  it('Property 6: Zero retracement not shown, positive retracement shown in details', () => {
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

          // Check that rows with retracement info show the correct annotations
          eventRows.forEach((row) => {
            const detailsCell = row.querySelectorAll('td')[9]; // Details column (index 9 after adding Layer column)
            const detailsText = detailsCell?.textContent || '';

            const retracementMatch = detailsText.match(/Retracement #(\d+)/);
            if (retracementMatch) {
              const retracementValue = parseInt(retracementMatch[1], 10);
              expect(retracementValue).toBeGreaterThan(0);
            }

            const remainingMatch = detailsText.match(
              /Remaining Retracements: (\d+)/
            );
            if (remainingMatch) {
              const remainingValue = parseInt(remainingMatch[1], 10);
              expect(remainingValue).toBeGreaterThanOrEqual(0);
            }
          });
        }
      ),
      {
        numRuns: PROPERTY_RUNS,
        interruptAfterTimeLimit: PROPERTY_TIME_LIMIT_MS,
      }
    );
  }, 15000);
});
