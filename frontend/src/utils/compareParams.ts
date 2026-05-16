export function parseCompareIds(searchParams: URLSearchParams): string[] {
  const raw = searchParams.get('compare') ?? searchParams.get('ids') ?? '';
  const seen = new Set<string>();
  const ids: string[] = [];

  for (const value of raw.split(',')) {
    const id = value.trim();
    if (!id || seen.has(id)) continue;
    seen.add(id);
    ids.push(id);
  }

  return ids;
}

export function buildCompareUrl(path: string, ids: string[]): string {
  const compare = ids.map((id) => encodeURIComponent(id)).join(',');
  return `${path}?compare=${compare}`;
}
