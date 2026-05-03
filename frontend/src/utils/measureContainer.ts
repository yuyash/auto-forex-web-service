/**
 * Safari-safe container size measurement.
 *
 * Safari's WebKit engine sometimes returns 0 for `clientWidth` / `clientHeight`
 * on flex children whose intrinsic size hasn't been resolved yet. This helper
 * tries multiple measurement strategies in order of reliability and returns the
 * first non-zero result.
 *
 * The fallback chain is:
 *   1. `clientWidth` / `clientHeight` — fastest, works on Chrome/Firefox
 *   2. `getBoundingClientRect()` — works on Safari in most cases
 *   3. `offsetWidth` / `offsetHeight` — includes borders but still better than 0
 */

export interface ContainerSize {
  width: number;
  height: number;
}

/**
 * Measure the usable width and height of an element, with Safari-safe
 * fallbacks. Returns floored integer pixel values.
 */
export function measureContainer(el: HTMLElement): ContainerSize {
  let width = el.clientWidth;
  let height = el.clientHeight;

  if (width <= 0 || height <= 0) {
    const rect = el.getBoundingClientRect();
    if (width <= 0) width = rect.width;
    if (height <= 0) height = rect.height;
  }

  if (width <= 0 || height <= 0) {
    if (width <= 0) width = el.offsetWidth;
    if (height <= 0) height = el.offsetHeight;
  }

  return {
    width: Math.max(0, Math.floor(width)),
    height: Math.max(0, Math.floor(height)),
  };
}

/**
 * Measure only the width of an element (Safari-safe).
 */
export function measureContainerWidth(el: HTMLElement): number {
  return measureContainer(el).width;
}

/**
 * Measure only the height of an element (Safari-safe).
 */
export function measureContainerHeight(el: HTMLElement): number {
  return measureContainer(el).height;
}
