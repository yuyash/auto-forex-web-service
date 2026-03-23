import { describe, expect, it } from 'vitest';
import {
  matchesEntityFilterSpec,
  matchesExactFilter,
  matchesSearchFilter,
  readOrderingFilter,
} from '../../../src/hooks/listFilterUtils';

describe('listFilterUtils', () => {
  it('matches exact filter when param is absent', () => {
    expect(matchesExactFilter(undefined, 'status', 'running')).toBe(true);
  });

  it('matches exact filter against stringified values', () => {
    expect(matchesExactFilter({ config_id: '42' }, 'config_id', 42)).toBe(true);
    expect(matchesExactFilter({ config_id: '24' }, 'config_id', 42)).toBe(
      false
    );
  });

  it('matches search filter against normalized haystack text', () => {
    expect(
      matchesSearchFilter({ search: 'eur_usd' }, [
        'Primary Account',
        'EUR_USD',
        'USD',
      ])
    ).toBe(true);
    expect(matchesSearchFilter({ search: 'gbp' }, ['EUR_USD', 'USD'])).toBe(
      false
    );
  });

  it('reads ordering filter with trimming', () => {
    expect(readOrderingFilter({ ordering: ' -updated_at ' })).toBe(
      '-updated_at'
    );
  });

  it('matches entity filter specs with exact and search filters', () => {
    expect(
      matchesEntityFilterSpec(
        { status: 'running', search: 'alpha' },
        { status: 'running', name: 'Alpha Task' },
        {
          exact: [{ key: 'status', value: (item) => item.status }],
          search: { haystack: (item) => [item.name] },
        }
      )
    ).toBe(true);
    expect(
      matchesEntityFilterSpec(
        { status: 'stopped', search: 'alpha' },
        { status: 'running', name: 'Alpha Task' },
        {
          exact: [{ key: 'status', value: (item) => item.status }],
          search: { haystack: (item) => [item.name] },
        }
      )
    ).toBe(false);
  });
});
