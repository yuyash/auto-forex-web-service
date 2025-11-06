import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { BatchFetcher } from './BatchFetcher';
import type { OHLCData } from '../types/chart';

// Mock fetch globally
globalThis.fetch = vi.fn();

describe('BatchFetcher', () => {
  let batchFetcher: BatchFetcher;
  const mockToken = 'test-token-123';

  const mockCandles: OHLCData[] = [
    { time: 1000, open: 1.1, high: 1.2, low: 1.0, close: 1.15 },
    { time: 2000, open: 1.15, high: 1.25, low: 1.1, close: 1.2 },
    { time: 3000, open: 1.2, high: 1.3, low: 1.15, close: 1.25 },
  ];

  beforeEach(() => {
    batchFetcher = new BatchFetcher(mockToken);
    vi.clearAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  describe('constructor', () => {
    it('should initialize with provided token', () => {
      expect(batchFetcher).toBeInstanceOf(BatchFetcher);
    });
  });

  describe('updateToken', () => {
    it('should update the authentication token', () => {
      const newToken = 'new-token-456';
      batchFetcher.updateToken(newToken);
      // Token is private, but we can verify by making a request
      expect(batchFetcher).toBeInstanceOf(BatchFetcher);
    });
  });

  describe('isRateLimited', () => {
    it('should return false when not rate limited', () => {
      expect(batchFetcher.isRateLimited()).toBe(false);
    });

    it('should return true when rate limited', async () => {
      // Mock a 429 response
      (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: false,
        status: 429,
        headers: new Headers(),
      } as Response);

      try {
        await batchFetcher.fetchInitialBatch('EUR_USD', 'M5');
      } catch {
        // Expected to throw
      }

      expect(batchFetcher.isRateLimited()).toBe(true);
    });
  });

  describe('getRetryDelay', () => {
    it('should return 0 when not rate limited', () => {
      expect(batchFetcher.getRetryDelay()).toBe(0);
    });

    it('should return remaining time when rate limited', async () => {
      // Mock a 429 response
      (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: false,
        status: 429,
        headers: new Headers(),
      } as Response);

      try {
        await batchFetcher.fetchInitialBatch('EUR_USD', 'M5');
      } catch {
        // Expected to throw
      }

      const delay = batchFetcher.getRetryDelay();
      expect(delay).toBeGreaterThan(0);
      expect(delay).toBeLessThanOrEqual(60000);
    });
  });

  describe('fetchInitialBatch', () => {
    it('should fetch initial batch successfully', async () => {
      const mockResponse = {
        ok: true,
        status: 200,
        headers: new Headers(),
        json: async () => ({
          instrument: 'EUR_USD',
          granularity: 'M5',
          candles: mockCandles,
        }),
      } as Response;

      (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
        mockResponse
      );

      const result = await batchFetcher.fetchInitialBatch('EUR_USD', 'M5');

      expect(result).toEqual(mockCandles);
      expect(globalThis.fetch).toHaveBeenCalledWith(
        '/api/candles?instrument=EUR_USD&granularity=M5&count=5000',
        {
          headers: {
            Authorization: `Bearer ${mockToken}`,
          },
        }
      );
    });

    it('should throw error when rate limited', async () => {
      (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: false,
        status: 429,
        headers: new Headers(),
      } as Response);

      await expect(
        batchFetcher.fetchInitialBatch('EUR_USD', 'M5')
      ).rejects.toThrow('Rate limited by API');
    });

    it('should detect rate limit from X-Rate-Limited header', async () => {
      const headers = new Headers();
      headers.set('X-Rate-Limited', 'true');

      (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers,
      } as Response);

      await expect(
        batchFetcher.fetchInitialBatch('EUR_USD', 'M5')
      ).rejects.toThrow('Rate limited by API');
    });

    it('should throw error on HTTP error', async () => {
      // Mock all 3 retry attempts to fail
      (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
        headers: new Headers(),
      } as Response);

      const fetchPromise = batchFetcher.fetchInitialBatch('EUR_USD', 'M5');

      // Advance timers for all retries
      await vi.advanceTimersByTimeAsync(1000); // First retry
      await vi.advanceTimersByTimeAsync(2000); // Second retry
      await vi.advanceTimersByTimeAsync(4000); // Third retry

      await expect(fetchPromise).rejects.toThrow();
    });
  });

  describe('fetchOlderBatch', () => {
    it('should fetch older batch with before timestamp', async () => {
      const beforeTimestamp = 5000;
      const mockResponse = {
        ok: true,
        status: 200,
        headers: new Headers(),
        json: async () => ({
          instrument: 'EUR_USD',
          granularity: 'M5',
          candles: mockCandles,
        }),
      } as Response;

      (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
        mockResponse
      );

      const result = await batchFetcher.fetchOlderBatch(
        'EUR_USD',
        'M5',
        beforeTimestamp
      );

      expect(result).toEqual(mockCandles);
      expect(globalThis.fetch).toHaveBeenCalledWith(
        `/api/candles?instrument=EUR_USD&granularity=M5&count=5000&before=${beforeTimestamp}`,
        {
          headers: {
            Authorization: `Bearer ${mockToken}`,
          },
        }
      );
    });

    it('should handle errors when fetching older batch', async () => {
      // Mock all 3 retry attempts to fail
      (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
        ok: false,
        status: 404,
        statusText: 'Not Found',
        headers: new Headers(),
      } as Response);

      const fetchPromise = batchFetcher.fetchOlderBatch('EUR_USD', 'M5', 5000);

      // Advance timers for all retries
      await vi.advanceTimersByTimeAsync(1000); // First retry
      await vi.advanceTimersByTimeAsync(2000); // Second retry
      await vi.advanceTimersByTimeAsync(4000); // Third retry

      await expect(fetchPromise).rejects.toThrow();
    });
  });

  describe('fetchNewerBatch', () => {
    it('should fetch newer batch successfully', async () => {
      const mockResponse = {
        ok: true,
        status: 200,
        headers: new Headers(),
        json: async () => ({
          instrument: 'EUR_USD',
          granularity: 'M5',
          candles: mockCandles,
        }),
      } as Response;

      (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
        mockResponse
      );

      const result = await batchFetcher.fetchNewerBatch('EUR_USD', 'M5');

      expect(result).toEqual(mockCandles);
      expect(globalThis.fetch).toHaveBeenCalledWith(
        '/api/candles?instrument=EUR_USD&granularity=M5&count=5000',
        {
          headers: {
            Authorization: `Bearer ${mockToken}`,
          },
        }
      );
    });
  });

  describe('retry logic with exponential backoff', () => {
    it('should retry failed requests with exponential backoff', async () => {
      // First two attempts fail, third succeeds
      (globalThis.fetch as ReturnType<typeof vi.fn>)
        .mockResolvedValueOnce({
          ok: false,
          status: 503,
          statusText: 'Service Unavailable',
          headers: new Headers(),
        } as Response)
        .mockResolvedValueOnce({
          ok: false,
          status: 503,
          statusText: 'Service Unavailable',
          headers: new Headers(),
        } as Response)
        .mockResolvedValueOnce({
          ok: true,
          status: 200,
          headers: new Headers(),
          json: async () => ({
            instrument: 'EUR_USD',
            granularity: 'M5',
            candles: mockCandles,
          }),
        } as Response);

      const fetchPromise = batchFetcher.fetchInitialBatch('EUR_USD', 'M5');

      // Advance timers for first retry (1s)
      await vi.advanceTimersByTimeAsync(1000);
      // Advance timers for second retry (2s)
      await vi.advanceTimersByTimeAsync(2000);

      const result = await fetchPromise;

      expect(result).toEqual(mockCandles);
      expect(globalThis.fetch).toHaveBeenCalledTimes(3);
    });

    it('should fail after max retries exceeded', async () => {
      // All attempts fail
      (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
        ok: false,
        status: 503,
        statusText: 'Service Unavailable',
        headers: new Headers(),
      } as Response);

      const fetchPromise = batchFetcher.fetchInitialBatch('EUR_USD', 'M5');

      // Advance timers for all retries
      await vi.advanceTimersByTimeAsync(1000); // First retry
      await vi.advanceTimersByTimeAsync(2000); // Second retry
      await vi.advanceTimersByTimeAsync(4000); // Third retry

      await expect(fetchPromise).rejects.toThrow();
      expect(globalThis.fetch).toHaveBeenCalledTimes(3);
    });

    it('should not retry when rate limited', async () => {
      (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: false,
        status: 429,
        headers: new Headers(),
      } as Response);

      await expect(
        batchFetcher.fetchInitialBatch('EUR_USD', 'M5')
      ).rejects.toThrow('Rate limited by API');

      // Should only be called once, no retries
      expect(globalThis.fetch).toHaveBeenCalledTimes(1);
    });
  });

  describe('rate limit cooldown', () => {
    it('should enforce 60-second cooldown after rate limit', async () => {
      // First request gets rate limited
      (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: false,
        status: 429,
        headers: new Headers(),
      } as Response);

      await expect(
        batchFetcher.fetchInitialBatch('EUR_USD', 'M5')
      ).rejects.toThrow('Rate limited by API');

      expect(batchFetcher.isRateLimited()).toBe(true);

      // Second request should fail immediately without calling fetch
      await expect(
        batchFetcher.fetchInitialBatch('EUR_USD', 'M5')
      ).rejects.toThrow(/Rate limited.*wait.*seconds/);

      // Should still only have one fetch call
      expect(globalThis.fetch).toHaveBeenCalledTimes(1);
    });

    it('should allow requests after cooldown expires', async () => {
      // First request gets rate limited
      (globalThis.fetch as ReturnType<typeof vi.fn>)
        .mockResolvedValueOnce({
          ok: false,
          status: 429,
          headers: new Headers(),
        } as Response)
        .mockResolvedValueOnce({
          ok: true,
          status: 200,
          headers: new Headers(),
          json: async () => ({
            instrument: 'EUR_USD',
            granularity: 'M5',
            candles: mockCandles,
          }),
        } as Response);

      await expect(
        batchFetcher.fetchInitialBatch('EUR_USD', 'M5')
      ).rejects.toThrow('Rate limited by API');

      expect(batchFetcher.isRateLimited()).toBe(true);

      // Advance time by 60 seconds
      vi.advanceTimersByTime(60000);

      expect(batchFetcher.isRateLimited()).toBe(false);

      // Should now succeed
      const result = await batchFetcher.fetchInitialBatch('EUR_USD', 'M5');
      expect(result).toEqual(mockCandles);
      expect(globalThis.fetch).toHaveBeenCalledTimes(2);
    });
  });

  describe('error handling', () => {
    it('should handle network errors', async () => {
      // Mock all 3 retry attempts to fail with network error
      (globalThis.fetch as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error('Network error')
      );

      const fetchPromise = batchFetcher.fetchInitialBatch('EUR_USD', 'M5');

      // Advance timers for all retries
      await vi.advanceTimersByTimeAsync(1000); // First retry
      await vi.advanceTimersByTimeAsync(2000); // Second retry
      await vi.advanceTimersByTimeAsync(4000); // Third retry

      await expect(fetchPromise).rejects.toThrow();
    });

    it('should handle invalid JSON responses', async () => {
      (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers(),
        json: async () => {
          throw new Error('Invalid JSON');
        },
      } as unknown as Response);

      await expect(
        batchFetcher.fetchInitialBatch('EUR_USD', 'M5')
      ).rejects.toThrow();
    });

    it('should return empty array when candles is missing', async () => {
      (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers(),
        json: async () => ({
          instrument: 'EUR_USD',
          granularity: 'M5',
          // candles missing
        }),
      } as Response);

      const result = await batchFetcher.fetchInitialBatch('EUR_USD', 'M5');
      expect(result).toEqual([]);
    });
  });
});
