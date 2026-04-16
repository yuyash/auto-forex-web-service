/**
 * Resolve localized parameter labels from a strategy JSON schema.
 *
 * Given a strategy type and the strategies list (which includes config_schema),
 * builds a map from raw parameter key → localized title string.
 */

import type { Strategy } from '../services/api/strategies';
import type { ConfigProperty } from '../types/strategy';

/**
 * Build a key→label map for strategy parameters using the JSON schema's
 * localized title fields (e.g. title_ja for Japanese).
 *
 * Falls back to the base `title`, then to a Title-Cased version of the key.
 */
export function buildParameterLabelMap(
  strategies: Strategy[],
  strategyType: string,
  language: string
): Map<string, string> {
  const map = new Map<string, string>();
  const strategy = strategies.find((s) => s.id === strategyType);
  if (!strategy?.config_schema) return map;

  const schema = strategy.config_schema as {
    properties?: Record<string, ConfigProperty>;
  };
  if (!schema.properties) return map;

  const langKey = `title_${language}` as keyof ConfigProperty;

  for (const [key, prop] of Object.entries(schema.properties)) {
    const localized = (prop[langKey] as string | undefined) ?? prop.title;
    if (localized) {
      map.set(key, localized);
    }
  }

  return map;
}

/**
 * Resolve a single parameter key to its localized label.
 * Returns the localized title if found, otherwise a Title-Cased version of the key.
 */
export function resolveParameterLabel(
  labelMap: Map<string, string>,
  key: string
): string {
  return (
    labelMap.get(key) ??
    key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
  );
}
