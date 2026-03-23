import type { CacheListParams } from './listCacheUtils';

export interface ExactEntityFilterSpec<TItem> {
  key: string;
  value: (item: TItem) => string | number | boolean | undefined | null;
}

export interface SearchEntityFilterSpec<TItem> {
  key?: string;
  haystack: (item: TItem) => Array<string | number | null | undefined>;
}

export interface EntityFilterSpec<TItem> {
  exact?: ExactEntityFilterSpec<TItem>[];
  search?: SearchEntityFilterSpec<TItem>;
}

export function readStringFilter(
  params: CacheListParams,
  key: string
): string | undefined {
  const value = params?.[key];
  if (typeof value !== 'string') {
    return undefined;
  }
  const normalized = value.trim();
  return normalized ? normalized : undefined;
}

export function matchesExactFilter(
  params: CacheListParams,
  key: string,
  value: string | number | boolean | undefined | null
): boolean {
  const expected = readStringFilter(params, key);
  if (!expected) {
    return true;
  }
  return String(value ?? '') === expected;
}

export function matchesSearchFilter(
  params: CacheListParams,
  haystackParts: Array<string | number | null | undefined>,
  key = 'search'
): boolean {
  const search = readStringFilter(params, key);
  if (!search) {
    return true;
  }
  const haystack = haystackParts
    .map((part) => String(part ?? ''))
    .join(' ')
    .toLowerCase();
  return haystack.includes(search.toLowerCase());
}

export function readOrderingFilter(
  params: CacheListParams
): string | undefined {
  return readStringFilter(params, 'ordering');
}

export function matchesEntityFilterSpec<TItem>(
  params: CacheListParams,
  item: TItem,
  spec: EntityFilterSpec<TItem>
): boolean {
  for (const filter of spec.exact ?? []) {
    if (!matchesExactFilter(params, filter.key, filter.value(item))) {
      return false;
    }
  }

  if (spec.search) {
    return matchesSearchFilter(
      params,
      spec.search.haystack(item),
      spec.search.key
    );
  }

  return true;
}
