import { describe, expect, it } from 'vitest';
import {
  formatDateTimeInTimezone,
  getTimezoneAbbreviation,
} from '../../../src/utils/timezone';

describe('timezone formatting', () => {
  it('uses a short abbreviation instead of GMT offset for Japanese locale', () => {
    const formatted = formatDateTimeInTimezone(
      '2026-01-03T14:55:42Z',
      'America/Los_Angeles',
      'ja',
      { includeSeconds: true, includeTimezone: true }
    );

    expect(formatted).toContain('PST');
    expect(formatted).not.toContain('GMT-8');
  });

  it('maps fixed-offset Asian zones to abbreviations', () => {
    const formatted = formatDateTimeInTimezone(
      '2026-01-03T14:55:42Z',
      'Asia/Tokyo',
      'en',
      { includeSeconds: true, includeTimezone: true }
    );

    expect(formatted).toContain('JST');
    expect(formatted).not.toContain('GMT+9');
  });

  it('applies the configured date format', () => {
    const formatted = formatDateTimeInTimezone(
      '2026-01-03T14:55:42Z',
      'America/Los_Angeles',
      'en',
      {
        includeSeconds: true,
        includeTimezone: true,
        dateFormat: 'DD/MM/YYYY',
      }
    );

    expect(formatted).toMatch(/^03\/01\/2026 /);
  });

  it('uses daylight-aware abbreviations for mapped zones', () => {
    expect(
      getTimezoneAbbreviation('Europe/Paris', '2026-01-03T14:55:42Z')
    ).toBe('CET');
    expect(
      getTimezoneAbbreviation('Europe/Paris', '2026-07-03T14:55:42Z')
    ).toBe('CEST');
  });
});
