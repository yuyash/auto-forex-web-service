import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useDebouncedValue } from '../../../src/hooks/useDebouncedValue';

describe('useDebouncedValue', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('updates only after the debounce interval', async () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebouncedValue(value, 400),
      { initialProps: { value: 'EUR_USD' } }
    );

    rerender({ value: 'GBP_USD' });

    expect(result.current).toBe('EUR_USD');

    await act(async () => {
      await vi.advanceTimersByTimeAsync(399);
    });
    expect(result.current).toBe('EUR_USD');

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(result.current).toBe('GBP_USD');
  });
});
