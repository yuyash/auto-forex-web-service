import { describe, expect, it } from 'vitest';
import { hasDirtyExecutionSettings } from './executionEditGuards';

describe('hasDirtyExecutionSettings', () => {
  it('returns false for metadata-only edits', () => {
    expect(hasDirtyExecutionSettings({ name: true, description: true })).toBe(
      false
    );
  });

  it('returns true for execution-shaping edits', () => {
    expect(hasDirtyExecutionSettings({ config_id: true })).toBe(true);
    expect(hasDirtyExecutionSettings({ tick_granularity: true })).toBe(true);
    expect(
      hasDirtyExecutionSettings({ live_tick_stale_guard_enabled: true })
    ).toBe(true);
  });
});
