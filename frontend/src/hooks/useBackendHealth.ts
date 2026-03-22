import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '../config/reactQuery';
import { healthApi } from '../services/api';

export function useBackendHealth(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: queryKeys.health.backend(),
    queryFn: () => healthApi.backend(),
    enabled: options?.enabled !== false,
    staleTime: 60_000,
  });
}
