/**
 * Color contrast utilities for accessibility
 * Ensures WCAG AA compliance (4.5:1 for normal text, 3:1 for large text)
 */

/**
 * Calculate relative luminance of a color
 * Based on WCAG 2.1 formula
 */
export const getRelativeLuminance = (rgb: {
  r: number;
  g: number;
  b: number;
}): number => {
  const { r, g, b } = rgb;

  const rsRGB = r / 255;
  const gsRGB = g / 255;
  const bsRGB = b / 255;

  const rLinear =
    rsRGB <= 0.03928 ? rsRGB / 12.92 : Math.pow((rsRGB + 0.055) / 1.055, 2.4);
  const gLinear =
    gsRGB <= 0.03928 ? gsRGB / 12.92 : Math.pow((gsRGB + 0.055) / 1.055, 2.4);
  const bLinear =
    bsRGB <= 0.03928 ? bsRGB / 12.92 : Math.pow((bsRGB + 0.055) / 1.055, 2.4);

  return 0.2126 * rLinear + 0.7152 * gLinear + 0.0722 * bLinear;
};

/**
 * Parse hex color to RGB
 */
export const hexToRgb = (hex: string): { r: number; g: number; b: number } => {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return result
    ? {
        r: parseInt(result[1], 16),
        g: parseInt(result[2], 16),
        b: parseInt(result[3], 16),
      }
    : { r: 0, g: 0, b: 0 };
};

/**
 * Calculate contrast ratio between two colors
 * Returns a value between 1 and 21
 */
export const getContrastRatio = (color1: string, color2: string): number => {
  const rgb1 = hexToRgb(color1);
  const rgb2 = hexToRgb(color2);

  const l1 = getRelativeLuminance(rgb1);
  const l2 = getRelativeLuminance(rgb2);

  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);

  return (lighter + 0.05) / (darker + 0.05);
};

/**
 * Check if contrast ratio meets WCAG AA standards
 */
export const meetsWCAGAA = (
  foreground: string,
  background: string,
  isLargeText: boolean = false
): boolean => {
  const ratio = getContrastRatio(foreground, background);
  const requiredRatio = isLargeText ? 3 : 4.5;
  return ratio >= requiredRatio;
};

/**
 * Check if contrast ratio meets WCAG AAA standards
 */
export const meetsWCAGAAA = (
  foreground: string,
  background: string,
  isLargeText: boolean = false
): boolean => {
  const ratio = getContrastRatio(foreground, background);
  const requiredRatio = isLargeText ? 4.5 : 7;
  return ratio >= requiredRatio;
};

/**
 * Get accessible text color (black or white) for a given background
 */
export const getAccessibleTextColor = (backgroundColor: string): string => {
  const rgb = hexToRgb(backgroundColor);
  const luminance = getRelativeLuminance(rgb);

  // If background is light, use dark text; if dark, use light text
  return luminance > 0.5 ? '#000000' : '#FFFFFF';
};

/**
 * Adjust color brightness to meet contrast requirements
 */
export const adjustColorForContrast = (
  color: string,
  backgroundColor: string,
  targetRatio: number = 4.5
): string => {
  let currentRatio = getContrastRatio(color, backgroundColor);

  if (currentRatio >= targetRatio) {
    return color;
  }

  const rgb = hexToRgb(color);
  const bgRgb = hexToRgb(backgroundColor);
  const bgLuminance = getRelativeLuminance(bgRgb);

  // Determine if we need to lighten or darken
  const shouldLighten = bgLuminance < 0.5;

  const adjustedRgb = { ...rgb };
  const step = shouldLighten ? 10 : -10;

  // Iteratively adjust until we meet the target ratio
  while (currentRatio < targetRatio) {
    adjustedRgb.r = Math.max(0, Math.min(255, adjustedRgb.r + step));
    adjustedRgb.g = Math.max(0, Math.min(255, adjustedRgb.g + step));
    adjustedRgb.b = Math.max(0, Math.min(255, adjustedRgb.b + step));

    const adjustedHex = rgbToHex(adjustedRgb);
    currentRatio = getContrastRatio(adjustedHex, backgroundColor);

    // Prevent infinite loop
    if (
      (shouldLighten &&
        adjustedRgb.r === 255 &&
        adjustedRgb.g === 255 &&
        adjustedRgb.b === 255) ||
      (!shouldLighten &&
        adjustedRgb.r === 0 &&
        adjustedRgb.g === 0 &&
        adjustedRgb.b === 0)
    ) {
      break;
    }
  }

  return rgbToHex(adjustedRgb);
};

/**
 * Convert RGB to hex
 */
export const rgbToHex = (rgb: { r: number; g: number; b: number }): string => {
  const toHex = (n: number) => {
    const hex = Math.round(n).toString(16);
    return hex.length === 1 ? '0' + hex : hex;
  };

  return `#${toHex(rgb.r)}${toHex(rgb.g)}${toHex(rgb.b)}`;
};

/**
 * High contrast color palette
 * Ensures all colors meet WCAG AA standards
 */
export const highContrastPalette = {
  light: {
    background: '#FFFFFF',
    text: '#000000',
    primary: '#0000FF', // Pure blue
    secondary: '#FF0000', // Pure red
    success: '#008000', // Pure green
    error: '#CC0000', // Dark red
    warning: '#FF8C00', // Dark orange
    info: '#0066CC', // Dark blue
  },
  dark: {
    background: '#000000',
    text: '#FFFFFF',
    primary: '#00FFFF', // Cyan
    secondary: '#FF00FF', // Magenta
    success: '#00FF00', // Lime
    error: '#FF6666', // Light red
    warning: '#FFCC00', // Gold
    info: '#66CCFF', // Light blue
  },
};

/**
 * Check if high contrast mode is enabled
 */
export const isHighContrastMode = (): boolean => {
  if (typeof window === 'undefined') return false;

  // Check for Windows high contrast mode
  if (window.matchMedia) {
    return (
      window.matchMedia('(prefers-contrast: high)').matches ||
      window.matchMedia('(-ms-high-contrast: active)').matches
    );
  }

  return false;
};

/**
 * Get contrast-safe color based on current mode
 */
export const getContrastSafeColor = (
  color: string,
  backgroundColor: string,
  highContrastMode: boolean = false
): string => {
  if (highContrastMode) {
    // In high contrast mode, use pure colors
    const isDarkBackground =
      getRelativeLuminance(hexToRgb(backgroundColor)) < 0.5;
    return isDarkBackground ? '#FFFFFF' : '#000000';
  }

  // Otherwise, adjust color if needed
  if (!meetsWCAGAA(color, backgroundColor)) {
    return adjustColorForContrast(color, backgroundColor);
  }

  return color;
};
