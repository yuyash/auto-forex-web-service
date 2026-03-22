import { describe, expect, it } from 'vitest';
import {
  removePaginatedEntity,
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
});
