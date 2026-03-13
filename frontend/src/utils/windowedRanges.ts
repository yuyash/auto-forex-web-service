export interface TimeRange {
  from: number;
  to: number;
}

export function normalizeRange(range: TimeRange): TimeRange {
  return range.from <= range.to ? range : { from: range.to, to: range.from };
}

export function expandRange(range: TimeRange, ratio: number): TimeRange {
  const normalized = normalizeRange(range);
  const span = Math.max(1, normalized.to - normalized.from);
  const buffer = Math.max(1, Math.floor(span * ratio));
  return {
    from: normalized.from - buffer,
    to: normalized.to + buffer,
  };
}

export function mergeRanges(ranges: TimeRange[]): TimeRange[] {
  if (ranges.length === 0) return [];
  const sorted = ranges
    .map(normalizeRange)
    .sort((a, b) => a.from - b.from || a.to - b.to);
  const merged: TimeRange[] = [sorted[0]];

  for (const current of sorted.slice(1)) {
    const last = merged[merged.length - 1];
    if (current.from <= last.to + 1) {
      last.to = Math.max(last.to, current.to);
    } else {
      merged.push({ ...current });
    }
  }

  return merged;
}

export function subtractLoadedRanges(
  target: TimeRange,
  loadedRanges: TimeRange[]
): TimeRange[] {
  const normalizedTarget = normalizeRange(target);
  let pending: TimeRange[] = [normalizedTarget];

  for (const loaded of mergeRanges(loadedRanges)) {
    pending = pending.flatMap((range) => {
      if (loaded.to < range.from || loaded.from > range.to) {
        return [range];
      }

      const next: TimeRange[] = [];
      if (loaded.from > range.from) {
        next.push({ from: range.from, to: loaded.from - 1 });
      }
      if (loaded.to < range.to) {
        next.push({ from: loaded.to + 1, to: range.to });
      }
      return next;
    });

    if (pending.length === 0) break;
  }

  return pending.filter((range) => range.to >= range.from);
}

export function clampRange(
  range: TimeRange,
  bounds?: Partial<TimeRange> | null
): TimeRange {
  const normalized = normalizeRange(range);
  const from =
    bounds?.from != null
      ? Math.max(bounds.from, normalized.from)
      : normalized.from;
  const to =
    bounds?.to != null ? Math.min(bounds.to, normalized.to) : normalized.to;
  return { from, to };
}
