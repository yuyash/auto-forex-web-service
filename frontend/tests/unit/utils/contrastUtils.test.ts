/**
 * Unit tests for WCAG contrast utilities.
 */

import { describe, it, expect } from 'vitest';
import {
  hexToRgb,
  rgbToHex,
  getRelativeLuminance,
  getContrastRatio,
  meetsWCAGAA,
  meetsWCAGAAA,
  getAccessibleTextColor,
} from '../../../src/utils/contrastUtils';

describe('hexToRgb', () => {
  it('parses standard hex', () => {
    expect(hexToRgb('#FF0000')).toEqual({ r: 255, g: 0, b: 0 });
  });

  it('parses without hash', () => {
    expect(hexToRgb('00FF00')).toEqual({ r: 0, g: 255, b: 0 });
  });

  it('returns black for invalid input', () => {
    expect(hexToRgb('invalid')).toEqual({ r: 0, g: 0, b: 0 });
  });
});

describe('rgbToHex', () => {
  it('converts RGB to hex', () => {
    expect(rgbToHex({ r: 255, g: 0, b: 0 })).toBe('#ff0000');
  });

  it('pads single-digit hex values', () => {
    expect(rgbToHex({ r: 0, g: 0, b: 0 })).toBe('#000000');
  });
});

describe('getRelativeLuminance', () => {
  it('returns 0 for black', () => {
    expect(getRelativeLuminance({ r: 0, g: 0, b: 0 })).toBe(0);
  });

  it('returns 1 for white', () => {
    expect(getRelativeLuminance({ r: 255, g: 255, b: 255 })).toBe(1);
  });
});

describe('getContrastRatio', () => {
  it('returns 21 for black on white', () => {
    expect(getContrastRatio('#000000', '#FFFFFF')).toBe(21);
  });

  it('returns 1 for same color', () => {
    expect(getContrastRatio('#FF0000', '#FF0000')).toBe(1);
  });
});

describe('meetsWCAGAA', () => {
  it('passes for black on white (normal text)', () => {
    expect(meetsWCAGAA('#000000', '#FFFFFF')).toBe(true);
  });

  it('fails for light gray on white (normal text)', () => {
    expect(meetsWCAGAA('#CCCCCC', '#FFFFFF')).toBe(false);
  });

  it('uses lower threshold for large text', () => {
    expect(meetsWCAGAA('#767676', '#FFFFFF', true)).toBe(true);
  });
});

describe('meetsWCAGAAA', () => {
  it('passes for black on white', () => {
    expect(meetsWCAGAAA('#000000', '#FFFFFF')).toBe(true);
  });
});

describe('getAccessibleTextColor', () => {
  it('returns black for white background', () => {
    expect(getAccessibleTextColor('#FFFFFF')).toBe('#000000');
  });

  it('returns white for black background', () => {
    expect(getAccessibleTextColor('#000000')).toBe('#FFFFFF');
  });
});
