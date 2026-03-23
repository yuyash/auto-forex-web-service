import { apiConfig } from '../../api/apiConfig';
import { api } from '../../api/apiClient';

export interface PaginatedApiResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

function parseNextRequest(nextUrl: string): {
  path: string;
  query: Record<string, string>;
} {
  const fallbackBase =
    apiConfig.BASE ||
    (typeof window !== 'undefined'
      ? window.location.origin
      : 'http://localhost');
  const parsedUrl = new URL(nextUrl, fallbackBase);

  return {
    path: `${parsedUrl.pathname}${parsedUrl.hash ?? ''}`,
    query: Object.fromEntries(parsedUrl.searchParams.entries()),
  };
}

export async function fetchPaginatedResults<T>(
  path: string,
  params: Record<string, string | number | undefined>
): Promise<T[]> {
  const results: T[] = [];
  let nextRequest: {
    path: string;
    query?: Record<string, string | number | undefined>;
  } | null = {
    path,
    query: params,
  };

  while (nextRequest) {
    const response: PaginatedApiResponse<T> = await api.get<
      PaginatedApiResponse<T>
    >(nextRequest.path, nextRequest.query);
    results.push(...(response.results ?? []));
    nextRequest = response.next ? parseNextRequest(response.next) : null;
  }

  return results;
}
