/**
 * Read candle colors from app settings in localStorage.
 */
import { z } from 'zod';
import { readStoredValue } from './persistentState';

const candleColorSettingsSchema = z.object({
  candleUpColor: z.string().optional(),
  candleDownColor: z.string().optional(),
});

export function getCandleColors(): { upColor: string; downColor: string } {
  const defaults = { upColor: '#16a34a', downColor: '#ef4444' };
  const parsed = readStoredValue('app_settings', candleColorSettingsSchema, {});
  return {
    upColor: parsed.candleUpColor || defaults.upColor,
    downColor: parsed.candleDownColor || defaults.downColor,
  };
}
