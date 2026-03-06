/**
 * Unit tests for ARIA utility functions.
 */

import { describe, it, expect } from 'vitest';
import {
  getStatusAriaLabel,
  getProgressAriaLabel,
  getActionAriaLabel,
  getNavigationAriaLabel,
  getFormFieldAriaLabel,
  getAriaLive,
  getAriaRole,
  getChartAriaLabel,
  getTableAriaLabel,
  getPaginationAriaLabel,
  getSortAriaLabel,
  getFilterAriaLabel,
  createAriaDescription,
} from '../../../src/utils/ariaUtils';

describe('getStatusAriaLabel', () => {
  it('returns descriptive label for known statuses', () => {
    expect(getStatusAriaLabel('running')).toContain('running');
    expect(getStatusAriaLabel('completed')).toContain('completed');
    expect(getStatusAriaLabel('failed')).toContain('failed');
  });

  it('returns raw status for unknown values', () => {
    expect(getStatusAriaLabel('custom')).toBe('custom');
  });
});

describe('getProgressAriaLabel', () => {
  it('includes percentage for running tasks', () => {
    expect(getProgressAriaLabel(50, 'running')).toContain('50%');
  });

  it('returns completed label', () => {
    expect(getProgressAriaLabel(100, 'completed')).toContain('100%');
  });

  it('returns failed label', () => {
    expect(getProgressAriaLabel(30, 'failed')).toContain('failed');
  });
});

describe('getActionAriaLabel', () => {
  it('returns action label without item name', () => {
    expect(getActionAriaLabel('start')).toBe('Start');
  });

  it('includes item name when provided', () => {
    expect(getActionAriaLabel('delete', 'Task 1')).toBe('Delete Task 1');
  });
});

describe('getNavigationAriaLabel', () => {
  it('marks active page', () => {
    expect(getNavigationAriaLabel('Dashboard', true)).toContain('current page');
  });

  it('returns plain label for inactive', () => {
    expect(getNavigationAriaLabel('Settings', false)).toBe('Settings');
  });
});

describe('getFormFieldAriaLabel', () => {
  it('adds required indicator', () => {
    expect(getFormFieldAriaLabel('Email', true)).toContain('required');
  });

  it('adds error message', () => {
    expect(getFormFieldAriaLabel('Email', false, 'Invalid')).toContain(
      'Invalid'
    );
  });
});

describe('getAriaLive', () => {
  it('returns assertive for errors', () => {
    expect(getAriaLive('error')).toBe('assertive');
  });

  it('returns polite for info', () => {
    expect(getAriaLive('info')).toBe('polite');
  });
});

describe('getAriaRole', () => {
  it('maps known component types', () => {
    expect(getAriaRole('dialog')).toBe('dialog');
    expect(getAriaRole('alert')).toBe('alert');
  });

  it('returns undefined for unknown types', () => {
    expect(getAriaRole('unknown')).toBeUndefined();
  });
});

describe('getChartAriaLabel', () => {
  it('includes chart type and data points', () => {
    const label = getChartAriaLabel('OHLC', 200);
    expect(label).toContain('OHLC');
    expect(label).toContain('200');
  });

  it('includes summary when provided', () => {
    const label = getChartAriaLabel('Line', 100, 'Upward trend');
    expect(label).toContain('Upward trend');
  });
});

describe('getTableAriaLabel', () => {
  it('includes table name, rows, and columns', () => {
    const label = getTableAriaLabel('Trades', 50, 8);
    expect(label).toContain('Trades');
    expect(label).toContain('50');
    expect(label).toContain('8');
  });
});

describe('getPaginationAriaLabel', () => {
  it('formats page info', () => {
    expect(getPaginationAriaLabel(3, 10)).toBe('Page 3 of 10');
  });
});

describe('getSortAriaLabel', () => {
  it('returns sort prompt without direction', () => {
    expect(getSortAriaLabel('Name')).toBe('Sort by Name');
  });

  it('includes direction when provided', () => {
    expect(getSortAriaLabel('Date', 'asc')).toContain('ascending');
  });
});

describe('getFilterAriaLabel', () => {
  it('indicates no active filters', () => {
    expect(getFilterAriaLabel('Status', 0)).toContain('no filters');
  });

  it('indicates active filter count', () => {
    expect(getFilterAriaLabel('Status', 2)).toContain('2 filters');
  });
});

describe('createAriaDescription', () => {
  it('joins non-empty parts', () => {
    expect(createAriaDescription(['Part 1', '', 'Part 2'])).toBe(
      'Part 1. Part 2'
    );
  });
});
