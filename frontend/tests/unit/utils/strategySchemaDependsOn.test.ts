/**
 * Unit tests for strategy schema dependsOn helpers.
 */

import { describe, it, expect } from 'vitest';
import {
  normalizeComparableValue,
  conditionMatchesValue,
  matchesDependsOn,
  isParameterVisible,
} from '../../../src/utils/strategySchemaDependsOn';
import type {
  ConfigProperty,
  DependsOnCondition,
} from '../../../src/types/strategy';

describe('normalizeComparableValue', () => {
  it('normalises booleans in string form', () => {
    expect(normalizeComparableValue('true')).toBe(true);
    expect(normalizeComparableValue(' False ')).toBe(false);
  });

  it('normalises numeric strings', () => {
    expect(normalizeComparableValue('1.5')).toBe(1.5);
    expect(normalizeComparableValue('-3')).toBe(-3);
  });

  it('leaves non-numeric strings alone', () => {
    expect(normalizeComparableValue('weighted_avg')).toBe('weighted_avg');
  });

  it('returns null for nullish and empty input', () => {
    expect(normalizeComparableValue(null)).toBeNull();
    expect(normalizeComparableValue(undefined)).toBeNull();
    expect(normalizeComparableValue('   ')).toBeNull();
  });
});

describe('conditionMatchesValue', () => {
  it('treats string "true"/"false" as booleans', () => {
    expect(conditionMatchesValue('true', true)).toBe(true);
    expect(conditionMatchesValue('false', false)).toBe(true);
    expect(conditionMatchesValue(true, true)).toBe(true);
  });

  it('fails when the normalised value does not match', () => {
    expect(conditionMatchesValue('false', true)).toBe(false);
  });

  it('compares normalised numbers', () => {
    expect(conditionMatchesValue('1.5', 1.5)).toBe(true);
    expect(conditionMatchesValue('2', 3)).toBe(false);
  });
});

describe('matchesDependsOn', () => {
  const schemaProps: Record<string, ConfigProperty> = {
    stop_loss_enabled: { type: 'boolean', default: false },
    rebuild_price_adjustment_enabled: { type: 'boolean', default: true },
  };

  it('returns true when the field matches a listed value', () => {
    const cond: DependsOnCondition = {
      field: 'stop_loss_enabled',
      values: [true],
    };
    expect(
      matchesDependsOn({ stop_loss_enabled: true }, cond, schemaProps)
    ).toBe(true);
  });

  it('returns false when the field does not match', () => {
    const cond: DependsOnCondition = {
      field: 'stop_loss_enabled',
      values: [true],
    };
    expect(
      matchesDependsOn({ stop_loss_enabled: false }, cond, schemaProps)
    ).toBe(false);
  });

  it('falls back to the schema default when the field is missing', () => {
    const cond: DependsOnCondition = {
      field: 'rebuild_price_adjustment_enabled',
      values: [true],
    };
    // empty params — default true satisfies the condition
    expect(matchesDependsOn({}, cond, schemaProps)).toBe(true);
  });

  it('respects "and" sub-conditions', () => {
    const cond: DependsOnCondition = {
      field: 'stop_loss_enabled',
      values: [true],
      and: [
        {
          field: 'rebuild_price_adjustment_enabled',
          values: [true],
        },
      ],
    };
    expect(
      matchesDependsOn(
        {
          stop_loss_enabled: true,
          rebuild_price_adjustment_enabled: true,
        },
        cond,
        schemaProps
      )
    ).toBe(true);
    expect(
      matchesDependsOn(
        {
          stop_loss_enabled: true,
          rebuild_price_adjustment_enabled: false,
        },
        cond,
        schemaProps
      )
    ).toBe(false);
  });

  it('respects "or" alternative branches', () => {
    const cond: DependsOnCondition = {
      field: 'stop_loss_enabled',
      values: [true],
      or: [
        {
          field: 'rebuild_price_adjustment_enabled',
          values: [true],
        },
      ],
    };
    // Root fails, alternative matches
    expect(
      matchesDependsOn(
        {
          stop_loss_enabled: false,
          rebuild_price_adjustment_enabled: true,
        },
        cond,
        schemaProps
      )
    ).toBe(true);
  });

  it('requires dependency fields to be visible before matching their defaults', () => {
    const props: Record<string, ConfigProperty> = {
      stop_loss_enabled: { type: 'boolean', default: false },
      rebuild_price_adjustment_enabled: {
        type: 'boolean',
        default: true,
        dependsOn: { field: 'stop_loss_enabled', values: [true] },
      },
    };
    const cond: DependsOnCondition = {
      field: 'rebuild_price_adjustment_enabled',
      values: [true],
    };

    expect(matchesDependsOn({ stop_loss_enabled: false }, cond, props)).toBe(
      false
    );
  });

  it('returns true when dependsOn is undefined', () => {
    expect(matchesDependsOn({}, undefined)).toBe(true);
  });

  it('handles snapshot payloads with stringified booleans', () => {
    const cond: DependsOnCondition = {
      field: 'stop_loss_enabled',
      values: [true],
    };
    expect(
      matchesDependsOn({ stop_loss_enabled: 'true' }, cond, schemaProps)
    ).toBe(true);
  });
});

describe('isParameterVisible', () => {
  const schemaProps: Record<string, ConfigProperty> = {
    stop_loss_enabled: { type: 'boolean', default: false },
    rebuild_price_adjustment_enabled: {
      type: 'boolean',
      default: true,
      dependsOn: { field: 'stop_loss_enabled', values: [true] },
    },
    rebuild_exit_price_buffer_pips: {
      type: 'number',
      default: 0,
      dependsOn: {
        field: 'rebuild_price_adjustment_enabled',
        values: [true],
      },
    },
    base_units: { type: 'integer', default: 1000 },
  };

  it('returns true for parameters without dependsOn', () => {
    expect(isParameterVisible('base_units', {}, schemaProps)).toBe(true);
  });

  it('hides a field when its dependency is not met', () => {
    expect(
      isParameterVisible(
        'rebuild_price_adjustment_enabled',
        { stop_loss_enabled: false },
        schemaProps
      )
    ).toBe(false);
  });

  it('shows a field whose dependency is met in params', () => {
    expect(
      isParameterVisible(
        'rebuild_price_adjustment_enabled',
        { stop_loss_enabled: true },
        schemaProps
      )
    ).toBe(true);
  });

  it('cascades visibility through nested dependsOn chains', () => {
    // rebuild_exit_price_buffer_pips depends on
    // rebuild_price_adjustment_enabled, which in turn depends on
    // stop_loss_enabled (via its own dependsOn).  When stop_loss is
    // off, the buffer field should stay hidden because its direct
    // dependency resolves to the schema default (true) unless the
    // params explicitly turn it off.
    expect(
      isParameterVisible(
        'rebuild_exit_price_buffer_pips',
        { stop_loss_enabled: false },
        schemaProps
      )
    ).toBe(false);
    expect(
      isParameterVisible(
        'rebuild_exit_price_buffer_pips',
        { stop_loss_enabled: true },
        schemaProps
      )
    ).toBe(true);
    // Explicitly disabling the feature hides the buffer.
    expect(
      isParameterVisible(
        'rebuild_exit_price_buffer_pips',
        {
          stop_loss_enabled: true,
          rebuild_price_adjustment_enabled: false,
        },
        schemaProps
      )
    ).toBe(false);
  });

  it('returns true when the schema is unknown', () => {
    expect(isParameterVisible('base_units', {}, undefined)).toBe(true);
  });
});
