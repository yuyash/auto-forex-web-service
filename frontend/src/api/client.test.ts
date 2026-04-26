import { describe, expect, it, vi } from 'vitest';
import { ApiError } from './apiClient';
import { withRetry } from './client';

describe('withRetry', () => {
  it('does not retry rate-limited responses', async () => {
    const fn = vi.fn().mockRejectedValue(
      new ApiError('/api/trading/tasks/backtest/', 429, 'Too Many Requests', {
        detail: 'Request was throttled.',
      })
    );

    await expect(withRetry(fn)).rejects.toMatchObject({
      statusCode: 429,
    });
    expect(fn).toHaveBeenCalledTimes(1);
  });
});
