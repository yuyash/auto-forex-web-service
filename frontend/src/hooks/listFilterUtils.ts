import type { CacheListParams } from './listCacheUtils';

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
