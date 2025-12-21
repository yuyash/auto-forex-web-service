import { describe, expect, it } from 'vitest';

import { createFloorStrategyMarkers } from './floorStrategyMarkers';
import type { BacktestStrategyEvent } from '../types/execution';

describe('createFloorStrategyMarkers', () => {
  it('renders initial_entry SHORT as initial_entry marker with short styling', () => {
    const events: BacktestStrategyEvent[] = [
      {
        event_type: 'initial_entry',
        timestamp: '2024-01-15T10:00:00Z',
        description: 'Initial SHORT entry @ 149.50000',
        details: {
          direction: 'short',
          entry_price: 149.5,
          units: 1000,
        },
      },
    ];

    const markers = createFloorStrategyMarkers(events);
    expect(markers).toHaveLength(1);

    const marker = markers[0];
    expect(marker?.type).toBe('initial_entry');
    expect(marker?.shape).toBe('triangleDown');
    expect(marker?.label).toContain('S');
  });

  it('does not default missing direction to short', () => {
    const events: BacktestStrategyEvent[] = [
      {
        event_type: 'initial_entry',
        timestamp: '2024-01-15T10:00:00Z',
        description: 'Initial LONG entry @ 149.50000',
        details: {
          entry_price: 149.5,
          units: 1000,
        },
      },
    ];

    const markers = createFloorStrategyMarkers(events);
    expect(markers).toHaveLength(1);

    const marker = markers[0];
    expect(marker?.type).toBe('initial_entry');
    expect(marker?.shape).toBe('triangleUp');
    expect(marker?.label).toContain('L');
  });
});
