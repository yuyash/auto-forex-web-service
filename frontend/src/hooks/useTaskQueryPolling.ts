import type {
  QueryObserverResult,
  UseQueryResult,
} from '@tanstack/react-query';
import type { PollingPolicyState } from './usePollingPolicy';
import { useSequentialPolling } from './useSequentialPolling';

interface QueryPollingOptions<TData> {
  policy: PollingPolicyState;
  shouldPoll?: (data: TData | null) => boolean;
}

export function useTaskQueryPolling<TData>(
  query: UseQueryResult<TData, Error>,
  polling?: QueryPollingOptions<TData>
) {
  useSequentialPolling(
    async () => {
      if (query.isFetching) {
        return Promise.resolve();
      }

      const result = (await query.refetch()) as QueryObserverResult<
        TData,
        Error
      >;
      if (result.error) {
        polling?.policy.registerFailure();
      } else {
        polling?.policy.resetFailures();
      }
      return result;
    },
    {
      enabled:
        polling?.policy.isActive === true &&
        (polling.shouldPoll?.(query.data ?? null) ?? true),
      intervalMs: polling?.policy.intervalMs ?? 10_000,
    }
  );
}
