import { createBackendHealthQuery } from './miscQueries';
import { mapQueryStateFields, useSimpleQueryState } from './useTaskCollections';

export function useBackendHealth(options?: { enabled?: boolean }) {
  return mapQueryStateFields(
    useSimpleQueryState(createBackendHealthQuery(options)),
    (data) => ({
      health: data,
    })
  );
}
