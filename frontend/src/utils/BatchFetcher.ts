import type { OHLCData } from '../types/chart';

/**
 * Interface for fetch options
 */
interface FetchOptions {
  instrument: string;
  granularity: string;
  count: number;
  before?: number; // Unix timestamp
}

/**
 * Interface for API response
 */
interface CandleAPIResponse {
  instrument: string;
  granularity: string;
  candles: OHLCData[];
}

/**
 * BatchFetcher manages API requests for candle data with intelligent batching,
 * error handling, and rate limit detection.
 *
 * Features:
 * - Fetches large batches (5000 candles) from OANDA API
 * - Implements exponential backoff retry logic (1s, 2s, 4s)
 * - Detects rate limiting from 429 status or X-Rate-Limited header
 * - Enforces 60-second cooldown after rate limit
 */
export class BatchFetcher {
  private token: string;
  private rateLimitedUntil: number = 0;
  private readonly DEFAULT_BATCH_SIZE = 5000;
  private readonly RATE_LIMIT_COOLDOWN = 60000; // 60 seconds in milliseconds
  private readonly MAX_RETRIES = 3;
  private readonly RETRY_DELAYS = [1000, 2000, 4000]; // Exponential backoff: 1s, 2s, 4s

  constructor(token: string) {
    this.token = token;
  }

  /**
   * Updates the authentication token
   * @param token - New authentication token
   */
  updateToken(token: string): void {
    this.token = token;
  }

  /**
   * Checks if currently rate limited
   * @returns True if rate limited, false otherwise
   */
  isRateLimited(): boolean {
    return Date.now() < this.rateLimitedUntil;
  }

  /**
   * Gets the remaining time until rate limit expires
   * @returns Milliseconds until retry allowed, or 0 if not rate limited
   */
  getRetryDelay(): number {
    if (!this.isRateLimited()) {
      return 0;
    }
    return this.rateLimitedUntil - Date.now();
  }

  /**
   * Marks the fetcher as rate limited and sets cooldown period
   */
  private setRateLimited(): void {
    this.rateLimitedUntil = Date.now() + this.RATE_LIMIT_COOLDOWN;
    console.warn(
      `Rate limited. Cooldown until: ${new Date(this.rateLimitedUntil).toISOString()}`
    );
  }

  /**
   * Performs a fetch request with exponential backoff retry logic
   * @param url - API endpoint URL
   * @param options - Fetch options
   * @returns Response object
   * @throws Error if max retries exceeded or unrecoverable error
   */
  private async fetchWithRetry(
    url: string,
    options: RequestInit
  ): Promise<Response> {
    for (let attempt = 0; attempt < this.MAX_RETRIES; attempt++) {
      try {
        const response = await fetch(url, options);

        // Check for rate limiting
        if (
          response.status === 429 ||
          response.headers.get('X-Rate-Limited') === 'true'
        ) {
          this.setRateLimited();
          throw new Error('Rate limited by API');
        }

        // If response is not OK but not rate limited, throw error
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        return response;
      } catch (error) {
        const isLastAttempt = attempt === this.MAX_RETRIES - 1;

        // If rate limited, don't retry - just throw
        if (this.isRateLimited()) {
          throw error;
        }

        // If last attempt, throw the error
        if (isLastAttempt) {
          console.error(`Failed after ${this.MAX_RETRIES} attempts:`, error);
          throw error;
        }

        // Wait before retrying with exponential backoff
        const delay = this.RETRY_DELAYS[attempt];
        console.warn(
          `Attempt ${attempt + 1} failed, retrying in ${delay}ms...`,
          error
        );
        await this.sleep(delay);
      }
    }

    throw new Error('Max retries exceeded');
  }

  /**
   * Sleep utility for retry delays
   * @param ms - Milliseconds to sleep
   */
  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  /**
   * Fetches candle data from the API
   * @param options - Fetch options including instrument, granularity, count, and optional before timestamp
   * @returns Array of OHLC data
   * @throws Error if fetch fails or rate limited
   */
  private async fetchCandles(options: FetchOptions): Promise<OHLCData[]> {
    // Check if rate limited before making request
    if (this.isRateLimited()) {
      const delay = this.getRetryDelay();
      throw new Error(
        `Rate limited. Please wait ${Math.ceil(delay / 1000)} seconds before retrying.`
      );
    }

    // Build URL with query parameters
    let url = `/api/candles?instrument=${options.instrument}&granularity=${options.granularity}&count=${options.count}`;
    if (options.before) {
      url += `&before=${options.before}`;
    }

    try {
      const response = await this.fetchWithRetry(url, {
        headers: {
          Authorization: `Bearer ${this.token}`,
        },
      });

      const data: CandleAPIResponse = await response.json();
      return data.candles || [];
    } catch (error) {
      console.error('Error fetching candles:', error);
      throw error;
    }
  }

  /**
   * Fetches initial batch of candles (5000) on component mount
   * @param instrument - Trading instrument (e.g., "EUR_USD")
   * @param granularity - Candle granularity (e.g., "M5")
   * @returns Array of OHLC data
   */
  async fetchInitialBatch(
    instrument: string,
    granularity: string
  ): Promise<OHLCData[]> {
    try {
      const candles = await this.fetchCandles({
        instrument,
        granularity,
        count: this.DEFAULT_BATCH_SIZE,
      });

      return candles;
    } catch (error) {
      console.error('Failed to fetch initial batch:', error);
      throw error;
    }
  }

  /**
   * Fetches older batch of candles (5000) before a specific timestamp
   * @param instrument - Trading instrument
   * @param granularity - Candle granularity
   * @param before - Unix timestamp to fetch candles before
   * @returns Array of OHLC data
   */
  async fetchOlderBatch(
    instrument: string,
    granularity: string,
    before: number
  ): Promise<OHLCData[]> {
    try {
      const candles = await this.fetchCandles({
        instrument,
        granularity,
        count: this.DEFAULT_BATCH_SIZE,
        before,
      });

      return candles;
    } catch (error) {
      console.error('Failed to fetch older batch:', error);
      throw error;
    }
  }

  /**
   * Fetches newest batch of candles (5000) to get latest data
   * @param instrument - Trading instrument
   * @param granularity - Candle granularity
   * @returns Array of OHLC data
   */
  async fetchNewerBatch(
    instrument: string,
    granularity: string
  ): Promise<OHLCData[]> {
    try {
      const candles = await this.fetchCandles({
        instrument,
        granularity,
        count: this.DEFAULT_BATCH_SIZE,
      });

      return candles;
    } catch (error) {
      console.error('Failed to fetch newer batch:', error);
      throw error;
    }
  }
}
