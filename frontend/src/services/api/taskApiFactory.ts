/**
 * Generic factory for task CRUD + lifecycle API services.
 *
 * Both backtestTasks and tradingTasks share identical list / get / create /
 * update / delete / start / stop / pause / resume / restart / copy /
 * getExecutions / getExecution methods.  This factory produces them from a
 * base URL and a backend→frontend transform function, eliminating ~150 lines
 * of duplication.
 */

import { api } from '../../api/apiClient';
import { withRetry } from '../../api/client';
import type { PaginatedResponse, TaskExecution } from '../../types';
import type { BackendTaskStopResponse } from './contracts';
import type { PaginatedApiResponse } from './pagination';

/** Minimal paginated backend shape. */
interface BackendPaginated<TBackend> {
  count: number;
  next?: string | null;
  previous?: string | null;
  results: TBackend[];
}

/** The set of methods every task API exposes. */
export interface TaskApi<TFrontend, TListParams, TCreateData, TUpdateData> {
  list: (params?: TListParams) => Promise<PaginatedResponse<TFrontend>>;
  get: (id: string) => Promise<TFrontend>;
  create: (data: TCreateData) => Promise<TFrontend>;
  update: (id: string, data: TCreateData) => Promise<TFrontend>;
  partialUpdate: (id: string, data: TUpdateData) => Promise<TFrontend>;
  delete: (id: string) => Promise<void>;
  start: (id: string) => Promise<TFrontend>;
  stop: (id: string, ...args: unknown[]) => Promise<BackendTaskStopResponse>;
  pause: (id: string) => Promise<TFrontend>;
  resume: (id: string) => Promise<TFrontend>;
  restart: (id: string) => Promise<TFrontend>;
  copy: (id: string, data: { new_name: string }) => Promise<TFrontend>;
  getExecutions: (
    id: string,
    params?: { page?: number; page_size?: number; include_metrics?: boolean }
  ) => Promise<PaginatedResponse<TaskExecution>>;
  getExecution: (
    id: string,
    executionId: string,
    params?: { include_metrics?: boolean }
  ) => Promise<TaskExecution>;
  deleteExecution: (id: string, executionId: string) => Promise<void>;
  updateExecutionNotes: (
    id: string,
    executionId: string,
    notes: string
  ) => Promise<TaskExecution>;
}

export function createTaskApi<
  TBackend,
  TFrontend,
  TListParams extends object | undefined,
  TCreateData,
  TUpdateData,
>(opts: {
  basePath: string;
  transform: (backend: TBackend) => TFrontend;
  /** Map frontend list params to the query object sent to the API. */
  mapListParams?: (params: TListParams) => Record<string, unknown>;
}): TaskApi<TFrontend, TListParams, TCreateData, TUpdateData> {
  const { basePath: BASE, transform } = opts;
  const mapParams =
    opts.mapListParams ??
    ((p: TListParams) => p as unknown as Record<string, unknown>);

  function toPaginated(
    result: BackendPaginated<TBackend>
  ): PaginatedResponse<TFrontend> {
    return {
      count: result.count,
      next: result.next ?? null,
      previous: result.previous ?? null,
      results: result.results.map(transform),
    };
  }

  return {
    list: async (params?: TListParams) => {
      const result = await withRetry(() =>
        api.get<BackendPaginated<TBackend>>(
          `${BASE}/`,
          params ? mapParams(params) : undefined
        )
      );
      return toPaginated(result);
    },

    get: async (id) => {
      const result = await withRetry(() => api.get<TBackend>(`${BASE}/${id}/`));
      return transform(result);
    },

    create: async (data) => {
      const result = await withRetry(() =>
        api.post<TBackend>(`${BASE}/`, data)
      );
      return transform(result);
    },

    update: async (id, data) => {
      const result = await withRetry(() =>
        api.put<TBackend>(`${BASE}/${id}/`, data)
      );
      return transform(result);
    },

    partialUpdate: async (id, data) => {
      const result = await withRetry(() =>
        api.patch<TBackend>(`${BASE}/${id}/`, data)
      );
      return transform(result);
    },

    delete: async (id) => withRetry(() => api.delete(`${BASE}/${id}/`)),

    start: async (id) =>
      transform(await api.post<TBackend>(`${BASE}/${id}/start/`, {})),

    stop: async (id: string) =>
      api.post<BackendTaskStopResponse>(`${BASE}/${id}/stop/`, {}),

    pause: async (id) =>
      transform(await api.post<TBackend>(`${BASE}/${id}/pause/`, {})),

    resume: async (id) =>
      transform(await api.post<TBackend>(`${BASE}/${id}/resume/`, {})),

    restart: async (id) =>
      transform(await api.post<TBackend>(`${BASE}/${id}/restart/`, {})),

    copy: async (id, data) => {
      const result = await withRetry(() =>
        api.post<TBackend>(`${BASE}/${id}/copy/`, data)
      );
      return transform(result);
    },

    getExecutions: async (id, params) => {
      const result = await withRetry(() =>
        api.get<PaginatedApiResponse<TaskExecution>>(
          `${BASE}/${id}/executions/`,
          {
            page: params?.page,
            page_size: params?.page_size,
            include_metrics: params?.include_metrics,
          }
        )
      );
      return {
        count: result.count,
        next: result.next ?? null,
        previous: result.previous ?? null,
        results: result.results ?? [],
      };
    },

    getExecution: async (id, executionId, params) =>
      withRetry(() =>
        api.get<TaskExecution>(`${BASE}/${id}/executions/${executionId}/`, {
          include_metrics: params?.include_metrics,
        })
      ),

    deleteExecution: async (id: string, executionId: string) =>
      withRetry(() =>
        api.delete(`${BASE}/${id}/executions/${executionId}/delete/`)
      ),

    updateExecutionNotes: async (
      id: string,
      executionId: string,
      notes: string
    ) =>
      withRetry(() =>
        api.patch<TaskExecution>(
          `${BASE}/${id}/executions/${executionId}/notes/`,
          { notes }
        )
      ),
  };
}
