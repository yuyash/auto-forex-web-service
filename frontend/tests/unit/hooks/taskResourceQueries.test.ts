import { describe, expect, it } from 'vitest';

import {
  shouldEnableRealtimeTaskUpdates,
  shouldPollTaskStatus,
} from '../../../src/hooks/taskResourceQueries';

describe('taskResourceQueries polling helpers', () => {
  it('polls task status while task is transitioning or paused', () => {
    expect(shouldPollTaskStatus('starting')).toBe(true);
    expect(shouldPollTaskStatus('running')).toBe(true);
    expect(shouldPollTaskStatus('paused')).toBe(true);
    expect(shouldPollTaskStatus('stopping')).toBe(true);
    expect(shouldPollTaskStatus('stopped')).toBe(false);
  });

  it('keeps realtime updates active until stop transition settles', () => {
    expect(shouldEnableRealtimeTaskUpdates('starting')).toBe(true);
    expect(shouldEnableRealtimeTaskUpdates('running')).toBe(true);
    expect(shouldEnableRealtimeTaskUpdates('stopping')).toBe(true);
    expect(shouldEnableRealtimeTaskUpdates('paused')).toBe(false);
    expect(shouldEnableRealtimeTaskUpdates('completed')).toBe(false);
  });
});
