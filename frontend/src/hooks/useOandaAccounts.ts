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
  active_strategy?: string;
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
    if (!token) {
      setAccounts([]);
      setIsLoading(false);
      return;
    }

    // Check cache first
    if (cache.data && Date.now() - cache.timestamp < CACHE_DURATION) {
      setAccounts(cache.data);
      setIsLoading(false);
      return;
    }

    // If there's already a pending request, wait for it instead of making a new one
    if (cache.promise) {
      try {
        const result = await cache.promise;
        setAccounts(result);
        setIsLoading(false);
        return;
      } catch (err) {
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
        if (
          handleAuthErrorStatus(response.status, {
            context: 'oanda-accounts:fetch',
          })
        ) {
          return [];
        }

        if (!response.ok) {
          throw new Error(`Failed to fetch accounts: ${response.statusText}`);
        }
        const data = await response.json();
        return Array.isArray(data) ? data : [];
      });

      const result = await cache.promise;

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

      // Update cache
      cache.data = normalizedAccounts;
      cache.timestamp = Date.now();

      setAccounts(normalizedAccounts);
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        setError(err as Error);
        console.error('Error fetching OANDA accounts:', err);
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
