import { createBackendHealthQuery } from './miscQueries';
import { useSimpleQueryState } from './useTaskCollections';

export function useBackendHealth(options?: { enabled?: boolean }) {
  return useSimpleQueryState(createBackendHealthQuery(options));
}
