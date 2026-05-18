import { describe, expect, it } from 'vitest';

import type { StrategyCycle } from '../../../../../../src/types/strategyVisualization';
import {
  buildDisplayGridState,
  buildSlotBuildCounts,
} from '../../../../../../src/components/tasks/detail/strategy/gridState';

function makeCycle(
  overrides?: Partial<StrategyCycle>,
  trades: StrategyCycle['trades'] = []
): StrategyCycle {
  return {
    cycle_id: 'cycle-1',
    direction: 'long',
    status: 'completed',
    started_at: '2026-01-01T00:00:00Z',
    ended_at: '2026-01-01T01:00:00Z',
    trade_count: trades.length,
    open_count: 0,
    close_count: 0,
    grid_state: {
      layers: [
        {
          layer: 1,
          slots: [{ slot: 0, state: 'empty', position_id: null }],
        },
      ],
      summary: {
        filled: 0,
        stopped: 0,
        rebuilt: 0,
        empty: 1,
        layer_count: 1,
        slot_count_per_layer: 1,
      },
    },
    trades,
    ...overrides,
  };
}

describe('gridState helpers', () => {
  it('marks a slot as stopped after stop loss without rebuild', () => {
    const cycle = makeCycle(undefined, [
      {
        id: 'cycle-1',
        direction: 'buy',
        units: 1000,
        price: '150.000',
        execution_method: 'open_position',
        layer_index: 1,
        retracement_count: 0,
        timestamp: '2026-01-01T00:00:00Z',
        position_id: 'pos-1',
      },
      {
        id: 'close-1',
        direction: 'buy',
        units: -1000,
        price: '149.500',
        execution_method: 'stop_loss',
        layer_index: 1,
        retracement_count: 0,
        timestamp: '2026-01-01T00:10:00Z',
        position_id: 'pos-1',
      },
    ]);

    const grid = buildDisplayGridState(cycle);

    expect(grid?.layers[0].slots[0].state).toBe('stopped');
    expect(grid?.summary.stopped).toBe(1);
  });

  it('marks a rebuilt slot as empty after the rebuilt position closes', () => {
    const cycle = makeCycle(undefined, [
      {
        id: 'cycle-1',
        direction: 'buy',
        units: 1000,
        price: '150.000',
        execution_method: 'open_position',
        layer_index: 1,
        retracement_count: 0,
        timestamp: '2026-01-01T00:00:00Z',
        position_id: 'pos-1',
      },
      {
        id: 'close-1',
        direction: 'buy',
        units: -1000,
        price: '149.500',
        execution_method: 'stop_loss',
        layer_index: 1,
        retracement_count: 0,
        timestamp: '2026-01-01T00:10:00Z',
        position_id: 'pos-1',
      },
      {
        id: 'rebuild-1',
        direction: 'buy',
        units: 1000,
        price: '150.000',
        execution_method: 'rebuild_position',
        layer_index: 1,
        retracement_count: 0,
        timestamp: '2026-01-01T00:20:00Z',
        position_id: 'pos-2',
        is_rebuild: true,
      },
      {
        id: 'close-2',
        direction: 'buy',
        units: -1000,
        price: '150.300',
        execution_method: 'close_position',
        layer_index: 1,
        retracement_count: 0,
        timestamp: '2026-01-01T00:30:00Z',
        position_id: 'pos-2',
      },
    ]);

    const grid = buildDisplayGridState(cycle);

    expect(grid?.layers[0].slots[0].state).toBe('empty');
    expect(grid?.summary.empty).toBe(1);
  });

  it('marks a slot as rebuilt while the rebuilt position remains open', () => {
    const cycle = makeCycle(undefined, [
      {
        id: 'cycle-1',
        direction: 'buy',
        units: 1000,
        price: '150.000',
        execution_method: 'open_position',
        layer_index: 1,
        retracement_count: 0,
        timestamp: '2026-01-01T00:00:00Z',
        position_id: 'pos-1',
      },
      {
        id: 'close-1',
        direction: 'buy',
        units: -1000,
        price: '149.500',
        execution_method: 'stop_loss',
        layer_index: 1,
        retracement_count: 0,
        timestamp: '2026-01-01T00:10:00Z',
        position_id: 'pos-1',
      },
      {
        id: 'rebuild-1',
        direction: 'buy',
        units: 1000,
        price: '150.000',
        execution_method: 'rebuild_position',
        layer_index: 1,
        retracement_count: 0,
        timestamp: '2026-01-01T00:20:00Z',
        position_id: 'pos-2',
        is_rebuild: true,
      },
    ]);

    const grid = buildDisplayGridState(cycle);

    expect(grid?.layers[0].slots[0].state).toBe('rebuilt');
    expect(grid?.summary.rebuilt).toBe(1);
  });

  it('counts rebuilt positions in slot build counts', () => {
    const cycle = makeCycle(undefined, [
      {
        id: 'cycle-1',
        direction: 'buy',
        units: 1000,
        price: '150.000',
        execution_method: 'open_position',
        layer_index: 1,
        retracement_count: 0,
        timestamp: '2026-01-01T00:00:00Z',
        position_id: 'pos-1',
      },
      {
        id: 'rebuild-1',
        direction: 'buy',
        units: 1000,
        price: '150.000',
        execution_method: 'rebuild_position',
        layer_index: 1,
        retracement_count: 0,
        timestamp: '2026-01-01T00:20:00Z',
        position_id: 'pos-2',
        is_rebuild: true,
      },
    ]);

    expect(buildSlotBuildCounts(cycle)).toEqual({ '1:0': 2 });
  });

  it('uses persisted grid slot build counts when trades are omitted', () => {
    const cycle = makeCycle({
      grid_state: {
        layers: [
          {
            layer: 1,
            slots: [
              { slot: 0, state: 'empty', position_id: null, build_count: 2 },
              { slot: 1, state: 'empty', position_id: null, build_count: 1 },
            ],
          },
        ],
        summary: {
          filled: 0,
          stopped: 0,
          rebuilt: 0,
          empty: 2,
          layer_count: 1,
          slot_count_per_layer: 2,
        },
      },
      trades: [],
    });

    expect(buildSlotBuildCounts(cycle)).toEqual({ '1:0': 2, '1:1': 1 });
  });
});
