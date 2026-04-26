import { beforeEach, describe, expect, it } from 'vitest';
import { queryClient, queryKeys } from '../../../src/config/reactQuery';
import {
  removeConfigurationCaches,
  upsertConfigurationCaches,
} from '../../../src/hooks/configurationMutationCache';
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

describe('configurationMutationCache', () => {
  beforeEach(() => {
    queryClient.clear();
  });

  it('removes updated configs from search-filtered caches they no longer match', () => {
    const listKey = queryKeys.configurations.list({ search: 'alpha' });
    queryClient.setQueryData<PaginatedResponse<StrategyConfig>>(
      listKey,
      buildPage([buildConfig()])
    );

    upsertConfigurationCaches(buildConfig({ name: 'Grid Beta' }));

    expect(
      queryClient.getQueryData<PaginatedResponse<StrategyConfig>>(listKey)
    ).toEqual(buildPage([], 0));
  });

  it('re-inserts matching configs into first-page filtered caches', () => {
    const listKey = queryKeys.configurations.list({
      search: 'beta',
      strategy_type: 'snowball',
    });
    const detailKey = queryKeys.configurations.detail('config-1');
    queryClient.setQueryData<PaginatedResponse<StrategyConfig>>(
      listKey,
      buildPage([], 0)
    );
    queryClient.setQueryData<StrategyConfig | null>(detailKey, null);

    upsertConfigurationCaches(buildConfig({ name: 'Snowball Beta' }));

    expect(
      queryClient
        .getQueryData<PaginatedResponse<StrategyConfig>>(listKey)
        ?.results.map((config) => config.name)
    ).toEqual(['Snowball Beta']);
    expect(queryClient.getQueryData<StrategyConfig>(detailKey)).toEqual(
      expect.objectContaining({ name: 'Snowball Beta' })
    );
  });

  it('removes deleted configs from list, detail, and linked-task caches', async () => {
    const listKey = queryKeys.configurations.list();
    const detailKey = queryKeys.configurations.detail('config-1');
    const tasksKey = queryKeys.configurations.tasks('config-1');
    queryClient.setQueryData<PaginatedResponse<StrategyConfig>>(
      listKey,
      buildPage([buildConfig()])
    );
    queryClient.setQueryData(detailKey, buildConfig());
    queryClient.setQueryData(tasksKey, [{ id: 'task-1' }]);

    await removeConfigurationCaches('config-1');

    expect(
      queryClient.getQueryData<PaginatedResponse<StrategyConfig>>(listKey)
    ).toEqual(buildPage([], 0));
    expect(queryClient.getQueryData(detailKey)).toBeUndefined();
    expect(queryClient.getQueryData(tasksKey)).toBeUndefined();
  });
});
