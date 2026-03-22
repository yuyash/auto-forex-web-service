import { useQuery } from '@tanstack/react-query';
import { createBackendHealthQuery } from './miscQueries';

export function useBackendHealth(options?: { enabled?: boolean }) {
  return useQuery(createBackendHealthQuery(options));
}
