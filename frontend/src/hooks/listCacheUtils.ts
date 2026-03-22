import type { PaginatedResponse } from '../types';

export type CacheListParams = Record<string, unknown> | undefined;

export function getListParams(queryKey: readonly unknown[]): CacheListParams {
  const candidate = queryKey[2];
  return candidate && typeof candidate === 'object'
    ? (candidate as Record<string, unknown>)
    : undefined;
}

export function upsertPaginatedEntity<T extends { id: string }>(
  cached: PaginatedResponse<T> | undefined,
  entity: T,
  options: {
    matches: boolean;
    page?: number;
    sort?: (items: T[]) => T[];
  }
): PaginatedResponse<T> | undefined {
  if (!cached) {
    return cached;
  }

  const index = cached.results.findIndex((entry) => entry.id === entity.id);
  const sort = options.sort ?? ((items: T[]) => items);

  if (index >= 0) {
    if (!options.matches) {
      return {
        ...cached,
        count: Math.max(0, cached.count - 1),
        results: cached.results.filter((entry) => entry.id !== entity.id),
      };
    }
    const nextResults = [...cached.results];
    nextResults[index] = { ...nextResults[index], ...entity };
    return { ...cached, results: sort(nextResults) };
  }

  if (!options.matches || (options.page ?? 1) > 1) {
    return cached;
  }

  return {
    ...cached,
    count: cached.count + 1,
    results: sort([entity, ...cached.results]),
  };
}

export function removePaginatedEntity<T extends { id: string }>(
  cached: PaginatedResponse<T> | undefined,
  entityId: string
): PaginatedResponse<T> | undefined {
  if (!cached) {
    return cached;
  }
  const nextResults = cached.results.filter((entry) => entry.id !== entityId);
  if (nextResults.length === cached.results.length) {
    return cached;
  }
  return {
    ...cached,
    count: Math.max(0, cached.count - 1),
    results: nextResults,
  };
}
