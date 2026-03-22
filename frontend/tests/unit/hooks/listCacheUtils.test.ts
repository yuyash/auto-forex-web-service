import { describe, expect, it } from 'vitest';
import {
  removePaginatedEntity,
  upsertFilteredListEntity,
  upsertFilteredPaginatedEntity,
  upsertPaginatedEntity,
} from '../../../src/hooks/listCacheUtils';
import type { PaginatedResponse, StrategyConfig } from '../../../src/types';

function buildConfig(overrides?: Partial<StrategyConfig>): StrategyConfig {
  return {
    id: 'config-1',
    name: 'Snowball Alpha',
    description: 'Primary config',
    strategy_type: 'snowball',
    config: {},
    created_at: '2026-03-22T00:00:00Z',
    updated_at: '2026-03-22T00:00:00Z',
    ...overrides,
  };
}

function buildPage(
  results: StrategyConfig[],
  count = results.length
): PaginatedResponse<StrategyConfig> {
  return {
    count,
    next: null,
    previous: null,
    results,
  };
}

describe('listCacheUtils', () => {
  it('does not prepend into page>1 caches', () => {
    const cached = buildPage([buildConfig({ id: 'config-2', name: 'Second' })]);

    const next = upsertPaginatedEntity(cached, buildConfig(), {
      matches: true,
      page: 2,
    });

    expect(next).toEqual(cached);
  });

  it('removes entities that no longer match a filtered list', () => {
    const cached = buildPage([
      buildConfig({ id: 'config-1', strategy_type: 'snowball' }),
      buildConfig({ id: 'config-2', strategy_type: 'grid' }),
    ]);

    const next = upsertPaginatedEntity(
      cached,
      buildConfig({ id: 'config-1', strategy_type: 'mean_reversion' }),
      {
        matches: false,
        page: 1,
      }
    );

    expect(next).toEqual(
      buildPage([buildConfig({ id: 'config-2', strategy_type: 'grid' })], 1)
    );
  });

  it('removes paginated entities and decrements the count', () => {
    const cached = buildPage([
      buildConfig({ id: 'config-1' }),
      buildConfig({ id: 'config-2' }),
    ]);

    const next = removePaginatedEntity(cached, 'config-1');

    expect(next).toEqual(buildPage([buildConfig({ id: 'config-2' })], 1));
  });

  it('applies sorted filtered paginated updates', () => {
    const cached = buildPage([
      buildConfig({ id: 'config-2', name: 'Zulu' }),
      buildConfig({ id: 'config-1', name: 'Alpha' }),
    ]);

    const next = upsertFilteredPaginatedEntity(
      cached,
      buildConfig({ id: 'config-2', name: 'Beta' }),
      { page: 1, search: 'be' },
      {
        matches: (entity, params) =>
          entity.name.toLowerCase().includes(String(params?.search ?? '')),
        sort: (items) =>
          [...items].sort((left, right) => left.name.localeCompare(right.name)),
      }
    );

    expect(next?.results.map((item) => item.name)).toEqual(['Alpha', 'Beta']);
  });

  it('applies filtered list upserts without prepending on later pages', () => {
    const next = upsertFilteredListEntity(
      [{ id: 2, name: 'Zulu' }],
      { id: 1, name: 'Alpha' },
      { page: 2, search: 'a' },
      {
        matches: (entity, params) =>
          entity.name.toLowerCase().includes(String(params?.search ?? '')),
        sort: (items) =>
          [...items].sort((left, right) => left.name.localeCompare(right.name)),
      }
    );

    expect(next).toEqual([{ id: 2, name: 'Zulu' }]);
  });
});
