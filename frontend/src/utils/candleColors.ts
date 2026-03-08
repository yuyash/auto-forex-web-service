/**
 * Read candle colors from app settings in localStorage.
 */
export function getCandleColors(): { upColor: string; downColor: string } {
  const defaults = { upColor: '#16a34a', downColor: '#ef4444' };
  try {
    const raw = localStorage.getItem('app_settings');
    if (raw) {
      const parsed = JSON.parse(raw);
      return {
        upColor: parsed.candleUpColor || defaults.upColor,
        downColor: parsed.candleDownColor || defaults.downColor,
      };
    }
  } catch {
    // ignore
  }
  return defaults;
}
