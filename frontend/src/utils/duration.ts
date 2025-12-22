const safeDateMs = (value: string | null | undefined): number | null => {
  if (!value) return null;
  const d = new Date(value);
  const ms = d.getTime();
  return Number.isNaN(ms) ? null : ms;
};

export const durationMsBetween = (
  start: string | null | undefined,
  end: string | null | undefined
): number | null => {
  const startMs = safeDateMs(start);
  const endMs = safeDateMs(end);
  if (startMs === null || endMs === null) return null;
  const diff = endMs - startMs;
  return diff >= 0 ? diff : null;
};

export const formatDurationMs = (durationMs: number): string => {
  const totalSeconds = Math.floor(durationMs / 1000);
  const seconds = totalSeconds % 60;
  const totalMinutes = Math.floor(totalSeconds / 60);
  const minutes = totalMinutes % 60;
  const totalHours = Math.floor(totalMinutes / 60);

  if (totalHours >= 24) {
    const days = Math.floor(totalHours / 24);
    const hours = totalHours % 24;
    return `${days}d ${hours}h`;
  }

  if (totalHours > 0) {
    return `${totalHours}h ${minutes}m`;
  }

  if (totalMinutes > 0) {
    return `${totalMinutes}m ${seconds}s`;
  }

  return `${seconds}s`;
};
