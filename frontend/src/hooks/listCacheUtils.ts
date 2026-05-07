import { queryClient } from '../config/reactQuery';
import type { PaginatedResponse } from '../types';

export type CacheListParams = Record<string, unknown> | undefined;

export function getListParams(queryKey: readonly unknown[]): CacheListParams {
  const candidate = queryKey[2];
  return candidate && typeof candidate === 'object'
    ? (candidate as Record<string, unknown>)
    : undefined;
}

export function patchListQueries<TCached>(
  listQueryKey: readonly unknown[],
  updater: (
    cached: TCached | undefined,
    params: CacheListParams
  ) => TCached | undefined
): void {
  for (const query of queryClient
    .getQueryCache()
    .findAll({ queryKey: listQueryKey })) {
    const params = getListParams(query.queryKey);
    queryClient.setQueryData<TCached | undefined>(query.queryKey, (cached) =>
      updater(cached, params)
    );
  }
}

export function removeFromListQueries<TCached>(
  listQueryKey: readonly unknown[],
  updater: (cached: TCached | undefined) => TCached | undefined
): void {
  queryClient.setQueriesData<TCached | undefined>(
    { queryKey: listQueryKey },
    updater
  );
}

export function upsertPaginatedEntity<T extends { id: string | number }>(
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

export function upsertFilteredPaginatedEntity<
  T extends { id: string | number },
  TParams extends CacheListParams = CacheListParams,
>(
  cached: PaginatedResponse<T> | undefined,
  entity: T,
  params: TParams,
  options: {
    matches: (entity: T, params: TParams) => boolean;
    sort?: (items: T[], params: TParams) => T[];
  }
): PaginatedResponse<T> | undefined {
  return upsertPaginatedEntity(cached, entity, {
    matches: options.matches(entity, params),
    page: Number((params as Record<string, unknown> | undefined)?.page ?? 1),
    sort: options.sort ? (items) => options.sort!(items, params) : undefined,
  });
}

export function upsertFilteredListEntity<
  T extends { id: string | number },
  TParams extends CacheListParams = CacheListParams,
>(
  cached: T[] | undefined,
  entity: T,
  params: TParams,
  options: {
    matches: (entity: T, params: TParams) => boolean;
    sort?: (items: T[], params: TParams) => T[];
  }
): T[] | undefined {
  if (!cached) {
    return cached;
  }

  const matches = options.matches(entity, params);
  const index = cached.findIndex((entry) => entry.id === entity.id);
  const sort = options.sort ?? ((items: T[]) => items);

  if (index >= 0) {
    if (!matches) {
      return cached.filter((entry) => entry.id !== entity.id);
    }
    const nextItems = [...cached];
    nextItems[index] = { ...nextItems[index], ...entity };
    return sort(nextItems, params);
  }

  if (
    !matches ||
    Number((params as Record<string, unknown> | undefined)?.page ?? 1) > 1
  ) {
    return cached;
  }

  return sort([entity, ...cached], params);
}

export function removePaginatedEntity<T extends { id: string | number }>(
  cached: PaginatedResponse<T> | undefined,
  entityId: string | number
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
