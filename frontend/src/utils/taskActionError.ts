import { ApiError } from '../api/apiClient';

type CapacityItem = {
  queue?: unknown;
  used?: unknown;
  limit?: unknown;
};

type RequiredStopItem = {
  message?: unknown;
};

export function formatTaskActionError(
  error: unknown,
  fallback: string
): string {
  if (
    !(error instanceof ApiError) ||
    !error.body ||
    typeof error.body !== 'object'
  ) {
    return error instanceof Error ? error.message : fallback;
  }

  const body = error.body as {
    error?: unknown;
    detail?: unknown;
    capacity?: CapacityItem[];
    required_stops?: RequiredStopItem[];
  };

  const parts: string[] = [];
  if (typeof body.detail === 'string' && body.detail.trim()) {
    parts.push(body.detail.trim());
  } else if (typeof body.error === 'string' && body.error.trim()) {
    parts.push(body.error.trim());
  }

  if (Array.isArray(body.capacity) && body.capacity.length > 0) {
    const capacityText = body.capacity
      .map((item) => {
        const queue = typeof item.queue === 'string' ? item.queue : 'queue';
        const used = typeof item.used === 'number' ? item.used : item.used;
        const limit = typeof item.limit === 'number' ? item.limit : item.limit;
        return `${queue}: ${String(used)}/${String(limit)}`;
      })
      .join(', ');
    if (capacityText) {
      parts.push(`Capacity ${capacityText}`);
    }
  }

  if (Array.isArray(body.required_stops) && body.required_stops.length > 0) {
    const recommendations = body.required_stops
      .map((item) =>
        typeof item.message === 'string' && item.message.trim()
          ? item.message.trim()
          : null
      )
      .filter((item): item is string => item !== null);
    if (recommendations.length > 0) {
      parts.push(recommendations.join(' '));
    }
  }

  if (parts.length > 0) {
    return parts.join(' ');
  }

  return error.message || fallback;
}
