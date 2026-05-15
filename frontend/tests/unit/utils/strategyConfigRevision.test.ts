import { describe, expect, it } from 'vitest';
import type { TaskExecution } from '../../../src/types/execution';
import { canEditDisplayedStrategyConfig } from '../../../src/utils/strategyConfigRevision';

const snapshot: NonNullable<TaskExecution['strategy_config']> = {
  id: 'config-1',
  name: 'Config',
  strategy_type: 'snowball',
  configuration_revision: 2,
  configuration_hash: 'hash-2',
  parameters: {},
};

describe('canEditDisplayedStrategyConfig', () => {
  it('allows editing the latest execution even when its snapshot is no longer current', () => {
    expect(
      canEditDisplayedStrategyConfig({
        configId: 'config-1',
        config: snapshot,
        isViewingHistorical: false,
        currentRevision: 3,
        currentHash: 'hash-3',
      })
    ).toBe(true);
  });

  it('requires historical executions to match the current configuration', () => {
    expect(
      canEditDisplayedStrategyConfig({
        configId: 'config-1',
        config: snapshot,
        isViewingHistorical: true,
        currentRevision: 3,
        currentHash: 'hash-3',
      })
    ).toBe(false);

    expect(
      canEditDisplayedStrategyConfig({
        configId: 'config-1',
        config: snapshot,
        isViewingHistorical: true,
        currentRevision: 2,
        currentHash: 'hash-2',
      })
    ).toBe(true);
  });

  it('does not expose an edit link without a live configuration id', () => {
    expect(
      canEditDisplayedStrategyConfig({
        configId: null,
        config: snapshot,
      })
    ).toBe(false);
  });
});
