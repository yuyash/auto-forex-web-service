import { act, renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { usePollingPolicy } from '../../../src/hooks/usePollingPolicy';

vi.mock('../../../src/hooks/useDocumentVisibility', () => ({
  useDocumentVisibility: () => true,
}));

vi.mock('../../../src/hooks/useOnlineStatus', () => ({
  useOnlineStatus: () => true,
}));

describe('usePollingPolicy', () => {
  it('backs off after failures and resets after success', () => {
    const { result } = renderHook(() =>
      usePollingPolicy({
        enabled: true,
        baseIntervalMs: 1000,
        maxIntervalMs: 5000,
      })
    );

    expect(result.current.isActive).toBe(true);
    expect(result.current.intervalMs).toBe(1000);

    act(() => {
      result.current.registerFailure();
    });
    expect(result.current.intervalMs).toBe(2000);

    act(() => {
      result.current.registerFailure();
    });
    expect(result.current.intervalMs).toBe(4000);

    act(() => {
      result.current.resetFailures();
    });
    expect(result.current.intervalMs).toBe(1000);
  });
});
