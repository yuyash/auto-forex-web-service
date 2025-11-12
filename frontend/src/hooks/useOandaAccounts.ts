// Shared hook for fetching OANDA accounts with caching
import { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { handleAuthErrorStatus } from '../utils/authEvents';

export interface OandaAccount {
  id: number;
  account_id: string;
  name: string;
  api_type?: 'practice' | 'live';
  is_practice?: boolean;
  is_active: boolean;
  is_default?: boolean;
  balance: number;
  margin_used?: string;
  margin_available?: string;
  unrealized_pnl?: string;
  currency: string;
}

// Global cache shared across all hook instances
const cache = {
  data: null as OandaAccount[] | null,
  timestamp: 0,
  promise: null as Promise<OandaAccount[]> | null,
};

const CACHE_DURATION = 60000; // 60 seconds - accounts don't change frequently

interface UseOandaAccountsResult {
  accounts: OandaAccount[];
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
  hasAccounts: boolean;
}

/**
 * Hook to fetch OANDA accounts with global caching and request deduplication
 * Multiple components can use this hook simultaneously without triggering duplicate requests
 */
export function useOandaAccounts(): UseOandaAccountsResult {
  const { token } = useAuth();
  const [accounts, setAccounts] = useState<OandaAccount[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const fetchData = useCallback(async () => {
    console.log('[useOandaAccounts] fetchData called', {
      hasToken: !!token,
      cacheAge: cache.data ? Date.now() - cache.timestamp : null,
      hasCachedData: !!cache.data,
      hasPendingRequest: !!cache.promise,
    });

    if (!token) {
      console.log('[useOandaAccounts] No token, clearing accounts');
      setAccounts([]);
      setIsLoading(false);
      return;
    }

    // Check cache first
    if (cache.data && Date.now() - cache.timestamp < CACHE_DURATION) {
      console.log('[useOandaAccounts] Using cached data', {
        accountCount: cache.data.length,
        cacheAge: Date.now() - cache.timestamp,
      });
      setAccounts(cache.data);
      setIsLoading(false);
      return;
    }

    // If there's already a pending request, wait for it instead of making a new one
    if (cache.promise) {
      console.log('[useOandaAccounts] Waiting for pending request');
      try {
        const result = await cache.promise;
        console.log('[useOandaAccounts] Pending request completed', {
          accountCount: result.length,
        });
        setAccounts(result);
        setIsLoading(false);
        return;
      } catch (err) {
        console.error('[useOandaAccounts] Pending request failed', err);
        setError(err as Error);
        setIsLoading(false);
        return;
      }
    }

    // Cancel any pending request from this instance
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    try {
      console.log('[useOandaAccounts] Fetching accounts from API');
      setIsLoading(true);
      setError(null);
      abortControllerRef.current = new AbortController();

      // Create and store the promise for request deduplication
      cache.promise = fetch('/api/accounts/', {
        headers: {
          Authorization: `Bearer ${token}`,
        },
        signal: abortControllerRef.current.signal,
      }).then(async (response) => {
        console.log('[useOandaAccounts] API response received', {
          status: response.status,
          ok: response.ok,
        });

        if (
          handleAuthErrorStatus(response.status, {
            context: 'oanda-accounts:fetch',
          })
        ) {
          console.log(
            '[useOandaAccounts] Auth error handled, returning empty array'
          );
          return [];
        }

        if (!response.ok) {
          const errorText = await response.text();
          console.error('[useOandaAccounts] API error', {
            status: response.status,
            statusText: response.statusText,
            body: errorText,
          });
          throw new Error(`Failed to fetch accounts: ${response.statusText}`);
        }
        const data = await response.json();
        console.log('[useOandaAccounts] API data parsed', {
          isArray: Array.isArray(data),
          dataType: typeof data,
          keys: data ? Object.keys(data) : null,
          data: data,
        });

        // Handle different response formats
        if (Array.isArray(data)) {
          return data;
        } else if (data && typeof data === 'object') {
          // Check for common pagination formats
          if (Array.isArray(data.results)) {
            return data.results;
          } else if (Array.isArray(data.data)) {
            return data.data;
          } else if (Array.isArray(data.accounts)) {
            return data.accounts;
          }
        }

        console.warn(
          '[useOandaAccounts] Unexpected API response format, returning empty array'
        );
        return [];
      });

      const result = await cache.promise;

      console.log('[useOandaAccounts] Processing accounts', {
        rawCount: result.length,
      });

      const normalizedAccounts: OandaAccount[] = result.map((account) => {
        const typedAccount = account as OandaAccount & {
          api_type?: 'practice' | 'live';
          is_practice?: boolean;
        };

        const isPractice =
          typeof typedAccount.is_practice === 'boolean'
            ? typedAccount.is_practice
            : typedAccount.api_type === 'practice';

        return {
          ...typedAccount,
          api_type: typedAccount.api_type ?? (isPractice ? 'practice' : 'live'),
          is_practice: isPractice,
        };
      });

      console.log('[useOandaAccounts] Accounts normalized', {
        count: normalizedAccounts.length,
        accounts: normalizedAccounts.map((a) => ({
          id: a.id,
          account_id: a.account_id,
          api_type: a.api_type,
          is_active: a.is_active,
        })),
      });

      // Update cache
      cache.data = normalizedAccounts;
      cache.timestamp = Date.now();

      setAccounts(normalizedAccounts);
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        const error = err as Error;
        console.error('[useOandaAccounts] Fetch failed', {
          error: error.message,
          name: error.name,
        });
        setError(error);

        // Only log non-abort errors once
        if (!error.message.includes('aborted')) {
          console.error('Failed to fetch OANDA accounts');
        }
      }
    } finally {
      setIsLoading(false);
      abortControllerRef.current = null;
      cache.promise = null;
    }
  }, [token]);

  useEffect(() => {
    fetchData();

    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [fetchData]);

  return {
    accounts,
    isLoading,
    error,
    refetch: fetchData,
    hasAccounts: accounts.length > 0,
  };
}
